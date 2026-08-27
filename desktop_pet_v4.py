import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QMessageBox

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None

BASE = Path(__file__).resolve().parent
HTML = BASE / 'dashboard_v4.html'


class DashboardV4(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Desktop Pet')
        self.resize(1280, 820)
        self.setMinimumSize(980, 680)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.view = QWebEngineView(self)
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        self.view.settings().setAttribute(self.view.settings().WebAttribute.FullScreenSupportEnabled, True)
        self.setCentralWidget(self.view)
        self.view.load(QUrl.fromLocalFile(str(HTML)))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Desktop Pet')
    app.setQuitOnLastWindowClosed(False)

    if QWebEngineView is None:
        QMessageBox.critical(
            None,
            'Desktop Pet',
            '缺少 Qt WebEngine。請先執行：\n\npython -m pip install PySide6-Addons',
        )
        return 1

    if not HTML.exists():
        QMessageBox.critical(None, 'Desktop Pet', f'找不到：{HTML.name}')
        return 1

    dash = DashboardV4()
    tray = QSystemTrayIcon(app.style().standardIcon(1), dash)
    menu = QMenu()
    menu.addAction('開啟 Dashboard', dash.show)
    menu.addAction('隱藏 Dashboard', dash.hide)
    menu.addSeparator()
    menu.addAction('結束', app.quit)
    tray.setContextMenu(menu)
    tray.show()
    dash.show()
    dash.raise_()
    dash.activateWindow()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
