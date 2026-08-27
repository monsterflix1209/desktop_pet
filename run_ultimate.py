import sys
import traceback
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle

import desktop_pet_ultimate as ultimate

# Keep every active RSS worker referenced until it finishes. The previous
# implementation suppressed the first load during NewsPage construction,
# but could still replace a running worker when changing categories quickly.
def _safe_load_feed(self, url, name):
    if not hasattr(self, "_rss_workers"):
        self._rss_workers = []

    worker = ultimate.RSSWorker(url, self.demo)
    self._rss_workers.append(worker)

    def cleanup():
        try:
            self._rss_workers.remove(worker)
        except ValueError:
            pass
        worker.deleteLater()

    worker.done.connect(lambda items: self.populate(items, name))
    worker.failed.connect(lambda error: self.show_error(str(error)))
    worker.finished.connect(cleanup)
    worker.start()


# Suppress the automatic NewsPage load during __init__; Dashboard.refresh_all()
# is responsible for the first real load.
_original_news_init = ultimate.NewsPage.__init__
_original_load_feed = ultimate.NewsPage.load_feed


def _news_init_without_duplicate_load(self, demo=False):
    ultimate.NewsPage.load_feed = lambda *args, **kwargs: None
    try:
        _original_news_init(self, demo)
    finally:
        ultimate.NewsPage.load_feed = _safe_load_feed


ultimate.NewsPage.load_feed = _safe_load_feed
ultimate.NewsPage.__init__ = _news_init_without_duplicate_load

load_config = ultimate.load_config
Pet = ultimate.Pet


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    pet = Pet(config)
    pet.show()

    tray = QSystemTrayIcon(
        app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
        pet,
    )
    menu = QMenu()
    menu.addAction("🖥️ 開啟資訊", pet.open_dashboard)
    menu.addAction("❌ 結束", app.quit)
    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
