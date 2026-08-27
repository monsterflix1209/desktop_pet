import os
import sys
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle

# Prevent NewsPage from starting an RSS worker twice during Dashboard construction.
# The original NewsPage.__init__ auto-loads the feed, and Dashboard.refresh_all()
# immediately loaded it again, replacing a still-running QThread.
import desktop_pet_ultimate as ultimate

_original_news_init = ultimate.NewsPage.__init__
_original_load_feed = ultimate.NewsPage.load_feed


def _news_init_without_duplicate_load(self, demo=False):
    original_loader = ultimate.NewsPage.load_feed
    ultimate.NewsPage.load_feed = lambda *args, **kwargs: None
    try:
        _original_news_init(self, demo)
    finally:
        ultimate.NewsPage.load_feed = original_loader


ultimate.NewsPage.__init__ = _news_init_without_duplicate_load

from desktop_pet_ultimate import load_config, Pet


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    pet = Pet(config)
    pet.show()

    # Keep a strong Python reference so the tray icon cannot be garbage-collected.
    tray = QSystemTrayIcon(app.style().standardIcon(QStyle.SP_ComputerIcon), pet)
    menu = QMenu()
    menu.addAction("🖥️ 開啟資訊", pet.open_dashboard)
    menu.addAction("❌ 結束", app.quit)
    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
