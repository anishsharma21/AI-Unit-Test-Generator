from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QMessageBox,
    QInputDialog,
    QLabel,
    QCheckBox,
)
from PyQt6.QtGui import QMovie
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread
import os
import sys
from openai import OpenAI
import configparser
import time
import json

from generatedTests_view import GeneratedTestsView


class UnitTestView(QWidget):

    tests_confirmed = pyqtSignal(list)

    def __init__(self, file_pairs, repo):
        super().__init__()

        self.repo = repo
        self.selected_tests = []

        self.confirm_pressed = False

        for file_pair in file_pairs:
            print(f"Initial file: {file_pair[0]}, Test file: {file_pair[1]}")

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

        client = OpenAI(api_key=self.api_key)

        try:

            self.initial_file_path = file_pairs[0][0]
            self.test_file_path = file_pairs[0][1]

            with open(self.initial_file_path, "rb") as f:
                start_time = time.time()
                self.initial_file = client.files.create(file=f, purpose="assistants")
                end_time = time.time()
                print(f"Initial file uploaded in {end_time - start_time} seconds")

            with open(self.test_file_path, "rb") as f:
                start_time = time.time()
                self.test_file = client.files.create(file=f, purpose="assistants")
                end_time = time.time()
                print(f"Test file uploaded in {end_time - start_time} seconds")

            print("Files uploaded successfully")
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"An error occurred while uploading the files: {e}"
            )

        self.setWindowTitle("Generate Unit Test Ideas")
        self.resize(800, 600)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.generate_button = QPushButton("Generate Unit Test Ideas")
        self.generate_button.clicked.connect(self.generate_unit_test_ideas_clicked)
        self.generate_button.setFixedHeight(40)
        self.generate_button.setFixedWidth(400)
        self.layout.addWidget(self.generate_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(40)
        self.cancel_button.setFixedWidth(400)
        self.cancel_button.clicked.connect(self.cancel_clicked)
        self.layout.addWidget(self.cancel_button)

        self.generate_button.show()
        self.cancel_button.show()

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
        self.unit_test_list.hide()
        self.layout.addWidget(self.unit_test_list)

        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.clicked.connect(self.confirm_selection)
        self.confirm_button.hide()
        self.layout.addWidget(self.confirm_button)

        self.setLayout(self.layout)

    def cancel_clicked(self):

        self.delete_files()

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

            time.sleep(1)

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

    def generate_unit_test_ideas_clicked(self):

        self.generate_button.hide()
        self.cancel_button.hide()
        self.loading_label.show()
        self.loading_movie.start()

        client = OpenAI(api_key=self.api_key)

        try:

            changes = self.repo.git.diff(None, self.initial_file_path)

            self.formatted_changes = self.format_changes(changes)

            assistant = client.beta.assistants.retrieve("asst_XW9b1pA7W2aExEWEFnp69xVq")

            thread = client.beta.threads.create()

            message_content = f"""Here are sections of the code that have been modified in the current commit:

    \\`\\`\\`
    {self.formatted_changes}
    \\`\\`\\`

    Reference the {os.path.basename(self.initial_file_path)} and especially the {os.path.basename(self.test_file_path)} file to determine the NEW unit tests that need to be written to address the above code modifications. There is no minimum or maximum number of unit tests but for each one you must specify the name and provide a description. Make sure the suggested tests align correctly with the testing approach and examples already established."""

            thread_message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_content,
                file_ids=[self.initial_file.id, self.test_file.id],
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id, assistant_id=assistant.id
            )

            print(f"Run status after creation: {run.status}")

            self.run_status_thread = RunStatusThread(client, thread.id, run.id)
            self.run_status_thread.status_updated.connect(self.run_status_updated)
            self.run_status_thread.start()

        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"An error occurred while generating unit test ideas: {e}",
            )

    def run_status_updated(self, status):
        print(f"Run status during polling: {status}")

        if status not in ["queued", "in_progress", "cancelling"]:

            client = OpenAI(api_key=self.api_key)

            if status == "completed":
                messages = client.beta.threads.messages.list(
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
                        client, content_block.text.value
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

        self.unit_test_list.clear()

        content = json.loads(chat_response.choices[0].message.content)

        for test in content["tests"]:

            widget = QWidget()
            layout = QVBoxLayout()
            widget.setLayout(layout)

            checkbox = QCheckBox(test["test-name"])
            checkbox.stateChanged.connect(
                lambda state, test=test: self.handle_checkbox_state_changed(state, test)
            )
            layout.addWidget(checkbox)

            label = QLabel(test["test-description"])
            label.setWordWrap(True)
            layout.addWidget(label)

            item = QListWidgetItem(self.unit_test_list)
            self.unit_test_list.setItemWidget(item, widget)

            widget.adjustSize()
            item.setSizeHint(widget.size())

        self.unit_test_list.show()
        self.confirm_button.show()

    def handle_checkbox_state_changed(self, state, test):

        if state == 2:

            self.selected_tests.append(test)
        else:

            self.selected_tests = [t for t in self.selected_tests if t != test]

        print(self.selected_tests)

    def format_changes(self, changes):
        lines = changes.split("\n")
        formatted_changes = []
        for line in lines:
            if line.startswith("diff") or line.startswith("index"):
                continue
            elif line.startswith("+") or line.startswith("-"):
                formatted_changes.append(line)
        return "\n".join(formatted_changes)

    def closeEvent(self, event):

        if not self.confirm_pressed:
            self.delete_files()
        event.accept()

    def confirm_selection(self):

        if not self.selected_tests:
            QMessageBox.warning(
                self, "Warning", "Please select at least one test to generate."
            )
            return

        self.confirm_pressed = True

        self.tests_confirmed.emit(self.selected_tests)

        self.generated_tests_view = GeneratedTestsView(
            self.selected_tests,
            self.initial_file,
            self.test_file,
            self.formatted_changes,
            os.path.basename(self.test_file_path),
        )
        self.generated_tests_view.show()

        self.close()


class RunStatusThread(QThread):
    status_updated = pyqtSignal(str)

    def __init__(self, client, thread_id, run_id):
        super().__init__()
        self.client = client
        self.thread_id = thread_id
        self.run_id = run_id

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

    def __init__(self, client, content):
        super().__init__()
        self.client = client
        self.content = content

    def run(self):
        chat_response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You need to find the test name and test description for each unit test described in a section of content and return them in a JSON format.",
                },
                {
                    "role": "user",
                    "content": f"return json format for the following information with fields tests, test-name and test-description:\n\n{self.content}",
                },
            ],
            temperature=1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        self.response_received.emit(chat_response)
