import os
from functools import partial
from git import Repo, InvalidGitRepositoryError
from PyQt6.QtCore import QTimer

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QMessageBox,
    QFileDialog,
)

from change_view import ChangeView
from unitTest_view import UnitTestView


class RepositoryView(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Git Repository")
        self.resize(800, 600)

        self.layout = QVBoxLayout()

        self.select_button_layout = QHBoxLayout()
        self.select_button = QPushButton("Select Repository")
        self.select_button.clicked.connect(self.select_clicked)
        self.select_button.setFixedHeight(40)
        self.select_button.setFixedWidth(400)
        self.select_button_layout.addStretch(1)
        self.select_button_layout.addWidget(self.select_button)
        self.select_button_layout.addStretch(1)
        self.layout.addLayout(self.select_button_layout)

        self.previous_repos = QListWidget()
        self.previous_repos.itemClicked.connect(self.previous_repo_clicked)
        self.layout.addWidget(self.previous_repos)

        self.change_list = QListWidget()
        self.change_list.itemDoubleClicked.connect(self.select_change_clicked)
        self.layout.addWidget(self.change_list)

        self.file_pair_list = QListWidget()
        self.layout.addWidget(self.file_pair_list)

        self.test_button_layout = QHBoxLayout()
        self.test_button = QPushButton("Continue")
        self.test_button.clicked.connect(self.find_associated_test_files)
        self.test_button.setFixedHeight(40)
        self.test_button.setFixedWidth(400)
        self.test_button_layout.addStretch(1)
        self.test_button_layout.addWidget(self.test_button)
        self.test_button_layout.addStretch(1)
        self.layout.addLayout(self.test_button_layout)

        self.confirm_button = QPushButton("Upload files")
        self.confirm_button.clicked.connect(self.confirm_clicked)
        self.confirm_button.setFixedHeight(40)
        self.confirm_button.setFixedWidth(400)
        self.confirm_button.setEnabled(False)
        self.confirm_button.hide()
        self.confirm_button_layout = QHBoxLayout()
        self.confirm_button_layout.addStretch(1)
        self.confirm_button_layout.addWidget(self.confirm_button)
        self.confirm_button_layout.addStretch(1)
        self.layout.addLayout(self.confirm_button_layout)

        self.setLayout(self.layout)

        self.repos = []

        self.confirmed_file_pairs = []

    def find_associated_test_files(self):

        if not self.repos:
            QMessageBox.warning(
                self,
                "No Repository",
                "No repository selected. Please select a repository first.",
            )
            return

        modified_files = self.repo.git.diff(None, name_only=True).split("\n")

        self.file_pairs = []

        for file in modified_files:

            base_name = os.path.splitext(os.path.basename(file))[0]

            test_file_name = base_name + "Tests.cs"

            for root, dirs, files in os.walk(
                os.path.join(self.repo.working_dir, "test")
            ):
                if test_file_name in files:

                    self.file_pairs.append(
                        (
                            os.path.join(self.repo.working_dir, file),
                            os.path.join(root, test_file_name),
                        )
                    )

        self.display_file_pairs()

        self.test_button.hide()
        self.confirm_button.show()

    def display_file_pairs(self):

        self.file_pair_list.clear()

        for file_pair in self.file_pairs:

            relative_file_pair = (
                file_pair[0].replace(self.repo.working_dir + "/", ""),
                file_pair[1].replace(self.repo.working_dir + "/", ""),
            )

            radiobutton = QRadioButton(
                f"{relative_file_pair[0]} - {relative_file_pair[1]}"
            )

            radiobutton.toggled.connect(
                partial(self.radiobutton_state_changed, file_pair=file_pair)
            )

            item = QListWidgetItem()
            item.setSizeHint(radiobutton.sizeHint())
            self.file_pair_list.addItem(item)
            self.file_pair_list.setItemWidget(item, radiobutton)

    def radiobutton_state_changed(self, checked, file_pair):

        if checked:
            self.confirmed_file_pairs.clear()
            self.confirmed_file_pairs.append(file_pair)

        self.confirm_button.setEnabled(len(self.confirmed_file_pairs) > 0)

    def select_change_clicked(self):
        if self.change_list.currentItem() is None:
            QMessageBox.warning(
                self,
                "No Change Selected",
                "Please select a file before clicking 'See Changes in file'.",
            )
            return

        selected_change = self.change_list.currentItem().text()
        try:
            change = self.repo.git.diff("HEAD", selected_change)
            self.change_view = ChangeView(change)
            self.change_view.show()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to display change: {e}")

    def previous_repo_clicked(self, item):
        path = item.text()
        try:
            self.repo = Repo(path)
            print(f"Opened repository at {path}")
            self.display_changes(self.repo)
        except InvalidGitRepositoryError:
            QMessageBox.warning(
                self,
                "Invalid Repository",
                f"The directory at {path} is not a Git repository.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {e}")

    def select_clicked(self):
        path = QFileDialog.getExistingDirectory(self, "Select Repository")
        if not path:
            return

        if path in self.repos:
            QMessageBox.information(
                self,
                "Duplicate Repository",
                f"The repository at {path} is already in the list.",
            )
            return

        try:
            self.repo = Repo(path)
            print(f"Opened repository at {path}")
            self.display_changes(self.repo)
            self.repos.append(path)
            self.previous_repos.addItem(QListWidgetItem(path))
        except InvalidGitRepositoryError:
            QMessageBox.warning(
                self,
                "Invalid Repository",
                f"The directory at {path} is not a Git repository.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {e}")

    def display_changes(self, repo):
        self.change_list.clear()
        changes = repo.git.diff(None, name_only=True).split("\n")
        untracked_files = repo.untracked_files
        for change in changes:
            self.change_list.addItem(QListWidgetItem(change))
        for untracked_file in untracked_files:
            self.change_list.addItem(QListWidgetItem(untracked_file))

    def confirm_clicked(self):

        self.confirm_button.setEnabled(False)

        self.unit_test_view = UnitTestView(self.confirmed_file_pairs, self.repo)
        self.unit_test_view.show()

        QTimer.singleShot(5000, lambda: self.confirm_button.setEnabled(True))
