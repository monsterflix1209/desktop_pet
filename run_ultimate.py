import os
import sys
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle

from desktop_pet_ultimate import load_config, Pet


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    pet = Pet(config)
    pet.show()

    tray = QSystemTrayIcon(app.style().standardIcon(QStyle.SP_ComputerIcon), pet)
    menu = QMenu()
    menu.addAction("🖥️ 開啟資訊", pet.open_dashboard)
    menu.addAction("❌ 結束", app.quit)
    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
