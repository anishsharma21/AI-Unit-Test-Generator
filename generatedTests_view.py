import configparser
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QWidget,
    QMessageBox,
    QInputDialog,
    QTextEdit,
    QListWidgetItem,
    QListWidget,
    QPushButton,
    QStyledItemDelegate,
)
from PyQt6.QtGui import (
    QMovie,
    QGuiApplication,
    QTextCharFormat,
    QColor,
    QFont,
    QTextCursor,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread
from openai import OpenAI
import time
from collections import deque
import re
import os
import sys


class CodeView(QWidget):
    def __init__(self, code):
        super().__init__()

        self.resize(800, 600)

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setFixedHeight(40)

        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)

        code = code.replace("```csharp", "").replace("```", "").strip()

        self.code_edit.setPlainText(code)

        layout = QVBoxLayout()
        layout.addWidget(self.copy_button)
        layout.addWidget(self.code_edit)
        self.setLayout(layout)

        self.format_code()

    def copy_to_clipboard(self):

        QGuiApplication.clipboard().setText(self.code_edit.toPlainText())

    def format_code(self):

        using_format = QTextCharFormat()
        using_format.setForeground(QColor("red"))
        using_format.setFontWeight(QFont.Weight.Bold)

        fact_theory_format = QTextCharFormat()
        fact_theory_format.setForeground(QColor("yellow"))
        fact_theory_format.setFontWeight(QFont.Weight.Bold)

        self.highlight_pattern(r"\busing\b", using_format)

        self.highlight_pattern(r"\[Fact\]", fact_theory_format)
        self.highlight_pattern(r"\[Theory\]", fact_theory_format)

    def highlight_pattern(self, pattern, format):

        regex = re.compile(pattern)

        document = self.code_edit.document()

        for match in regex.finditer(document.toPlainText()):

            start = match.start()
            end = match.end()

            cursor = self.code_edit.textCursor()

            cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

            cursor.setCharFormat(format)


class CustomDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(50)
        return size


class RunStatusThread(QThread):
    status_updated = pyqtSignal(str)

    def __init__(self, client, thread_id, run_id, test_name):
        super().__init__()
        self.client = client
        self.thread_id = thread_id
        self.run_id = run_id
        self.test_name = test_name

    def run(self):
        delay = 1
        run = self.client.beta.threads.runs.retrieve(
            thread_id=self.thread_id, run_id=self.run_id
        )
        while run.status in ["queued", "in_progress", "cancelling"]:
            time.sleep(delay)
            run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread_id, run_id=self.run_id
            )
            self.status_updated.emit(run.status)
            delay = min(delay * 2, 15)


class ChatAPIThread(QThread):
    response_received = pyqtSignal(object)

    def __init__(self, client, content, test_name):
        super().__init__()
        self.client = client
        self.content = content
        self.test_name = test_name

    def run(self):
        chat_response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You need to extract only the unit test code from the content and send only the unit test code back and nothing else.",
                },
                {
                    "role": "user",
                    "content": f"""return only the unit test code from the following content, do not include namespace, classes or anything but the unit test definition:
                    
                    {self.content}""",
                },
            ],
            temperature=1,
            max_tokens=1000,
        )
        self.response_received.emit(chat_response)


class GeneratedTestsView(QWidget):
    def generate_tests(self):

        self.loading_label.hide()
        self.layout.addWidget(self.loading_label)

        self.loading_label.show()
        self.loading_movie.start()

        self.client = OpenAI(api_key=self.api_key)

        self.generate_next_test()

    def generate_next_test(self):

        if self.tests_queue:

            test = self.tests_queue.popleft()
            print(f"Generating test: {test['test-name']}")

            assistant = self.client.beta.assistants.retrieve(
                "asst_GpfjUzQuQhp1DwF86auMjxMY"
            )

            thread = self.client.beta.threads.create()

            message_content = f"""Here are sections of the code that have been modified in the current commit:

    \\`\\`\\`
    {self.formatted_changes}
    \\`\\`\\`

    Your task is to write the following unit test (either with Fact or Theory as you see fit in the xUnit framework):

    {test["test-description"]}

    Reference the TestsBase.cs file and especially the {self.test_file_name} file to ensure the same conventions, approach and style is used to write this single unit test that integrates well into the {self.test_file_name} file. If at any point you are unsure of what needs to be written in any part of the unit test, provide INLINE comments for guidance in order to avoid false and confusing code. Again if you are unsure, provide inline comments.
"""

            thread_message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_content,
                file_ids=[self.initial_file.id, self.test_file.id],
            )

            run = self.client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=assistant.id
            )

            print(f"Run status after creation: {run.status}")

            self.run_status_thread = RunStatusThread(
                self.client, thread.id, run.id, test["test-name"]
            )
            self.run_status_thread.status_updated.connect(self.run_status_updated)
            self.run_status_thread.start()

    def run_status_updated(self, status):
        print(f"Run status during polling: {status}")

        if status not in ["queued", "in_progress", "cancelling"]:

            if status == "completed":
                messages = self.client.beta.threads.messages.list(
                    thread_id=self.run_status_thread.thread_id
                )

                last_message = None
                for message in reversed(messages.data):
                    if message.role == "assistant":
                        last_message = message
                        break

                if last_message is not None:
                    for content_block in last_message.content:
                        pass

                    self.chat_api_thread = ChatAPIThread(
                        self.client,
                        content_block.text.value,
                        self.run_status_thread.test_name,
                    )
                    self.chat_api_thread.response_received.connect(
                        self.chat_api_response_received
                    )
                    self.chat_api_thread.start()
            else:
                print(status)

    def chat_api_response_received(self, chat_response):

        self.loading_movie.stop()
        self.loading_label.hide()

        test_code = chat_response.choices[0].message.content

        test_name = self.sender().test_name

        item = QListWidgetItem(test_name)
        item.setData(Qt.ItemDataRole.UserRole, test_code)

        item.setSizeHint(QSize(item.sizeHint().width(), 50))

        font = item.font()
        font.setPointSize(14)
        item.setFont(font)

        self.unit_test_list.addItem(item)

        self.unit_test_list.show()

        self.generate_next_test()

    def handle_item_double_clicked(self, item):

        test_code = item.data(Qt.ItemDataRole.UserRole)

        code_view = CodeView(test_code)
        code_view.show()

        self.code_views.append(code_view)

    def __init__(
        self, selected_tests, initial_file, test_file, formatted_changes, test_file_name
    ):
        super().__init__()

        self.code_views = []

        self.selected_tests = selected_tests
        self.initial_file = initial_file
        self.test_file = test_file
        self.formatted_changes = formatted_changes
        self.test_file_name = test_file_name

        self.setWindowTitle("Generated Tests")
        self.resize(800, 600)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(self.layout)

        if getattr(sys, "frozen", False):

            bundle_dir = sys._MEIPASS
        else:

            bundle_dir = os.path.dirname(os.path.abspath(__file__))

        loading_gif_path = os.path.join(bundle_dir, "loading.gif")

        self.loading_label = QLabel(self)

        self.loading_movie = QMovie(loading_gif_path)
        self.loading_movie.setScaledSize(QSize(100, 100))
        self.loading_label.setMovie(self.loading_movie)

        self.loading_label.hide()
        self.layout.addWidget(self.loading_label)

        self.unit_test_list = QListWidget()
        self.unit_test_list.setItemDelegate(CustomDelegate(self))
        self.unit_test_list.itemDoubleClicked.connect(self.handle_item_double_clicked)

        self.unit_test_list.setStyleSheet(
            """
            QListWidget::item {
                border: 1px solid white;
                margin: 5px;
            }
            QListWidget::item:selected {
                background: blue;
            }
        """
        )

        self.unit_test_list.hide()
        self.layout.addWidget(self.unit_test_list)

        self.loading_label.show()
        self.loading_movie.start()

        config = configparser.ConfigParser()

        config.read("config.ini")

        if "OPENAI" not in config or "API_KEY" not in config["OPENAI"]:

            api_key, ok = QInputDialog.getText(
                self, "Input Dialog", "Please enter your OpenAI API key:"
            )
            if ok:

                if "OPENAI" not in config:
                    config.add_section("OPENAI")
                config.set("OPENAI", "API_KEY", api_key)
                with open("config.ini", "w") as configfile:
                    config.write(configfile)
                QMessageBox.information(self, "Success", "API key set successfully")
            else:
                QMessageBox.warning(self, "Error", "API key not set")
        else:
            print("API key found in configuration file")

        self.api_key = config["OPENAI"]["API_KEY"]

        self.client = OpenAI(api_key=self.api_key)

        self.files = self.client.files.list().data

        if self.initial_file and not any(
            file.id == self.initial_file.id for file in self.files
        ):
            QMessageBox.warning(self, "Error", "Initial file not found")

        if self.test_file and not any(
            file.id == self.test_file.id for file in self.files
        ):
            QMessageBox.warning(self, "Error", "Test file not found")

        self.tests_queue = deque(self.selected_tests)
        self.generate_tests()

    def delete_files(self):
        client = OpenAI(api_key=self.api_key)

        try:

            time.sleep(1)

            files = client.files.list().data

            if self.initial_file and any(
                file.id == self.initial_file.id for file in files
            ):
                try:

                    client.files.delete(self.initial_file.id)
                    print(f"Deleted initial file: {self.initial_file.id}")
                except Exception as e:
                    if "Not Found" in str(e):
                        print("Initial file already deleted")
                    else:
                        raise
                self.initial_file = None

            time.sleep(3)

            files = client.files.list().data

            if self.test_file and any(file.id == self.test_file.id for file in files):
                try:

                    client.files.delete(self.test_file.id)
                    print(f"Deleted test file: {self.test_file.id}")
                except Exception as e:
                    if "Not Found" in str(e):
                        print("Test file already deleted")
                    else:
                        raise
                self.test_file = None

        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"An error occurred while deleting the files: {e}"
            )

        self.close()

    def closeEvent(self, event):
        self.delete_files()
        event.accept()
