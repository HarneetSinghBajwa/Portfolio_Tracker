
import sys

from PySide6.QtWidgets import QApplication, QMainWindow
from ui import PortfolioUI


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle("NSE Portfolio Tracker")
    window.resize(1400, 800)
    window.setMinimumSize(950, 600)

    dashboard = PortfolioUI()
    window.setCentralWidget(dashboard)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
