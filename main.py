from PyQt6.QtWidgets import QApplication

from repository_view import RepositoryView

if __name__ == "__main__":
    app = QApplication([])
    repo_view = RepositoryView()
    repo_view.show()
    app.exec()
