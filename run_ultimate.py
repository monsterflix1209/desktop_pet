import sys
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle

from desktop_pet_ultimate_v2 import cfg_load, Pet


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cfg = cfg_load()
    pet = Pet(cfg)
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
