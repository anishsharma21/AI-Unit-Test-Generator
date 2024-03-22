from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton
from PyQt6.QtGui import QColor


class ChangeView(QWidget):
    def __init__(self, change):
        super().__init__()

        self.setWindowTitle("Change Details")
        self.resize(800, 600)

        self.layout = QVBoxLayout()

        self.change_text = QTextEdit()
        self.change_text.setReadOnly(True)

        lines = change.split("\n")
        for line in lines:
            if line.startswith("diff --git") or line.startswith("index"):
                continue

            if line.startswith("+"):
                self.change_text.setTextColor(QColor("green"))
            elif line.startswith("-"):
                self.change_text.setTextColor(QColor("red"))
            else:
                self.change_text.setTextColor(QColor("white"))
            self.change_text.append(line)

        self.layout.addWidget(self.change_text)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        self.layout.addWidget(self.close_button)

        self.setLayout(self.layout)
