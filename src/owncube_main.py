import sys

from PyQt6.QtWidgets import QApplication

from src.controllers.owncube_controller import OwnCubeController


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    controller = OwnCubeController()
    controller.show_main_window()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
