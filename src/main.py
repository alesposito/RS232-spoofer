import sys
from PyQt6.QtWidgets import QApplication
from src.controllers.main_controller import MainController

def main():
    app = QApplication(sys.argv)
    
    # Set a dark theme for the application
    app.setStyle("Fusion")
    
    controller = MainController()
    controller.show_main_window()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
