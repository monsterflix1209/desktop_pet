import os
import sys
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle

import desktop_pet_ultimate as ultimate


# --- Runtime compatibility fixes for the current Ultimate build ---
# 1) NewsPage.__init__ and Dashboard.refresh_all() both start an RSS worker.
#    Prevent the first automatic load so one RSS QThread is active at a time.
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


# 2) The current Dashboard creates the page widgets and the QStackedWidget,
#    but does not add the pages to the stack. That makes the navigation appear
#    unresponsive because the stack contains zero widgets.
_original_dashboard_init = ultimate.Dashboard.__init__


def _dashboard_init_with_pages(self, config):
    _original_dashboard_init(self, config)

    pages = [
        getattr(self, "weather_page", None),
        getattr(self, "news_page", None),
        getattr(self, "stock_page", None),
        getattr(self, "games_page", None),
        getattr(self, "settings_page", None),
    ]

    # Avoid duplicates if this compatibility patch is ever applied twice.
    if self.stack.count() == 0:
        for page in pages:
            if page is not None:
                self.stack.addWidget(page)

        if self.stack.count() > 0:
            self.stack.setCurrentIndex(0)


ultimate.Dashboard.__init__ = _dashboard_init_with_pages


from desktop_pet_ultimate import load_config, Pet


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = load_config()
    pet = Pet(config)
    pet.show()

    tray = QSystemTrayIcon(
        app.style().standardIcon(QStyle.SP_ComputerIcon),
        pet,
    )

    menu = QMenu()
    menu.addAction("🖥️ 開啟資訊", pet.open_dashboard)
    menu.addAction("❌ 結束", app.quit)
    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
