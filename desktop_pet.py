import sys
import os
import json
import math
import time
import random
import webbrowser
from datetime import datetime
import requests
import feedparser
from dotenv import load_dotenv

from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QPoint, QRectF, QSize, QSharedMemory, QUrl,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QListWidget, QListWidgetItem, QComboBox,
    QCheckBox, QLineEdit, QStackedWidget, QFrame, QGraphicsDropShadowEffect,
    QSystemTrayIcon, QMenu, QMessageBox, QProgressBar, QGridLayout, QSizePolicy,
    QStyle, QGraphicsOpacityEffect, QSlider, QScrollArea
)
from PySide6.QtGui import (
    QIcon, QFont, QColor, QPainter, QBrush, QPen, QAction, QPainterPath, QDesktopServices
)

load_dotenv()

# ==========================================
# 01. 設計系統 (Design Tokens & Styles)
# ==========================================
class DesignTokens:
    # 顏色系統
    BG_DARK = "#121212"
    SURFACE_DARK = "#1E1E1E"
    SURFACE_LIGHT = "#2A2A2A"
    PRIMARY = "#3B82F6"
    PRIMARY_HOVER = "#60A5FA"
    SUCCESS = "#22C55E"
    WARNING = "#EAB308"
    DANGER = "#EF4444"
    TEXT_MAIN = "#FFFFFF"
    TEXT_MUTED = "#A0A0A0"
    BORDER = "rgba(255, 255, 255, 0.08)"

    # 間距系統 (Specification #83)
    SPACING_XS = 8
    SPACING_SM = 12
    SPACING_MD = 16
    SPACING_LG = 20
    SPACING_XL = 24
    SPACING_XXL = 32

    # 圓角系統 (Specification #15)
    RADIUS_DASHBOARD = 24
    RADIUS_CARD = 18
    RADIUS_BTN = 12

    # 字體系統
    FONT_FAMILY = "Microsoft JhengHei UI"

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet_config.json")
DEFAULT_CONFIG = {
    "location": {"name": "臺中市"},
    "favorite_stocks": ["2330", "2317", "2454"],
    "theme": "dark",
    "pet_scale": 1.0,
    "opacity": 1.0,
    "sound": True,
    "animation": True,
    "autostart": True,
    "demo_mode": os.getenv("DEMO_MODE", "true").lower() == "true"
}

TAIWAN_CITIES = [
    "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市",
    "基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣",
    "雲林縣", "嘉義市", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣",
    "臺東縣", "澎湖縣", "金門縣", "連江縣"
]

# ==========================================
# 02. 自訂元件 (Custom Components)
# ==========================================
class CustomCard(QFrame):
    """具備 18px 圓角與懸停浮升動畫 (Lift Effect) 的卡片 (Specification #38, #76)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignTokens.SURFACE_DARK};
                border-radius: {DesignTokens.RADIUS_CARD}px;
                border: 1px solid {DesignTokens.BORDER};
            }}
        """)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 60))
        self.shadow.setOffsetY(4)
        self.setGraphicsEffect(self.shadow)

    def enterEvent(self, event):
        self.shadow.setOffsetY(8)
        self.shadow.setBlurRadius(25)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow.setOffsetY(4)
        self.shadow.setBlurRadius(15)
        super().leaveEvent(event)

class ToastNotification(QFrame):
    """右上角淡入與下滑 Toast 通知系統 (Specification #73, #74)"""
    def __init__(self, parent, text, is_error=False):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setFixedHeight(50)
        bg_color = "#321c1c" if is_error else "#1c2b1e"
        border_color = DesignTokens.DANGER if is_error else DesignTokens.SUCCESS

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {DesignTokens.RADIUS_BTN}px;
            }}
            QLabel {{
                color: {DesignTokens.TEXT_MAIN};
                font-family: "{DesignTokens.FONT_FAMILY}";
                font-size: 13px;
                font-weight: bold;
            }}
        """)

        layout = QHBoxLayout(self)
        icon = "⚠️" if is_error else "ℹ️"
        label = QLabel(f"{icon} {text}")
        layout.addWidget(label)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        # 動畫設定
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

        QTimer.singleShot(3000, self.fadeOut)

    def fadeOut(self):
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()

class ToastManager:
    @staticmethod
    def show(parent, text, is_error=False):
        toast = ToastNotification(parent, text, is_error)
        toast.move(parent.width() - toast.width() - 20, 80)
        toast.show()

class SegmentedNav(QWidget):
    """無縫分頁切換導覽列 (Specification #19, #20)"""
    tab_changed = Signal(int)

    def __init__(self, tabs):
        super().__init__()
        self.tabs = tabs
        self.buttons = []
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DesignTokens.SURFACE_DARK};
                border-radius: 14px;
            }}
        """)

        for idx, text in enumerate(self.tabs):
            btn = QPushButton(text)
            btn.setFont(QFont(DesignTokens.FONT_FAMILY, 11, QFont.Weight.Bold))
            btn.setFixedHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self.set_active_tab(i))
            self.buttons.append(btn)
            layout.addWidget(btn)

        self.set_active_tab(0)

    def set_active_tab(self, index):
        for idx, btn in enumerate(self.buttons):
            if idx == index:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {DesignTokens.PRIMARY};
                        color: white;
                        border-radius: 10px;
                        border: none;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {DesignTokens.TEXT_MUTED};
                        border-radius: 10px;
                        border: none;
                    }}
                    QPushButton:hover {{
                        color: white;
                        background-color: rgba(255, 255, 255, 0.05);
                    }}
                """)
        self.tab_changed.emit(index)

class SkeletonWidget(QWidget):
    """載入中骨架屏 (Specification #62)"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        for _ in range(3):
            bar = QFrame()
            bar.setFixedHeight(24)
            bar.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.06);
                    border-radius: 6px;
                }
            """)
            layout.addWidget(bar)

# ==========================================
# 03. API 服務層 (Data Services)
# ==========================================
class APIWorker(QThread):
    data_loaded = Signal(dict)

    def __init__(self, city, favorites, demo_mode, news_cat="general"):
        super().__init__()
        self.city = city
        self.favorites = favorites
        self.demo_mode = demo_mode
        self.news_cat = news_cat

    def run(self):
        weather = self.fetch_weather()
        news = self.fetch_news()
        stocks = self.fetch_stocks()
        self.data_loaded.emit({"weather": weather, "news": news, "stocks": stocks})

    def fetch_weather(self):
        cwa_key = os.getenv("CWA_API_KEY", "")
        if self.demo_mode or not cwa_key:
            return {
                "location": self.city, "temperature": 29.0, "weather": "多雲晴朗",
                "humidity": 72, "wind_speed": 2.1, "rain_probability": 20,
                "max_temperature": 32.0, "min_temperature": 25.0, "aqi": 42,
                "aqi_status": "良好", "pm25": 12, "updated_at": datetime.now().strftime("%H:%M"),
                "hourly": [
                    {"time": "18:00", "icon": "☀️", "temp": "29°"},
                    {"time": "19:00", "icon": "☀️", "temp": "28°"},
                    {"time": "20:00", "icon": "☁️", "temp": "27°"},
                    {"time": "21:00", "icon": "🌧️", "temp": "26°"},
                    {"time": "22:00", "icon": "🌧️", "temp": "25°"}
                ],
                "is_demo": True
            }

        try:
            fc_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?format=JSON&Authorization={cwa_key}&locationName={self.city}"
            res = requests.get(fc_url, timeout=5).json()
            loc_data = res.get("records", {}).get("location", [])
            wx, pop, min_t, max_t = "晴", "10", "24", "31"
            if loc_data:
                for e in loc_data[0].get("weatherElement", []):
                    name = e.get("elementName")
                    val = e.get("time", [{}])[0].get("parameter", {}).get("parameterName", "")
                    if name == "Wx": wx = val
                    elif name == "PoP": pop = val
                    elif name == "MinT": min_t = val
                    elif name == "MaxT": max_t = val

            return {
                "location": self.city, "temperature": (float(min_t) + float(max_t)) / 2,
                "weather": wx, "humidity": 68, "wind_speed": 2.4, "rain_probability": int(pop),
                "max_temperature": float(max_t), "min_temperature": float(min_t),
                "aqi": 38, "aqi_status": "良好", "pm25": 9,
                "updated_at": datetime.now().strftime("%H:%M"),
                "hourly": [
                    {"time": "18:00", "icon": "☀️", "temp": f"{max_t}°"},
                    {"time": "21:00", "icon": "☁️", "temp": f"{min_t}°"}
                ],
                "is_demo": False
            }
        except Exception:
            return self.fetch_weather()

    def fetch_news(self):
        if self.demo_mode:
            return [
                {
                    "title": "🔥 2026 科技趨勢論壇今日盛大登場 AI 應用成全球焦點",
                    "source": "科技日報", "time": "18 分鐘前",
                    "desc": "專家預估邊緣運算與智慧桌寵終端裝置將進入年成長黃金期...",
                    "url": "https://news.google.com", "is_hero": True
                },
                {
                    "title": "台股表現強勁 科技產業鏈指數持續突破新高",
                    "source": "財經時報", "time": "1 小時前",
                    "desc": "受惠全球半導體需求熱絡，加權指數盤中再度走高...",
                    "url": "https://news.google.com", "is_hero": False
                }
            ]
        try:
            rss_url = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            feed = feedparser.parse(rss_url)
            items = []
            for idx, entry in enumerate(feed.entries[:6]):
                items.append({
                    "title": entry.get("title", "無標題新聞"),
                    "source": entry.get("source", {}).get("title", "Google 新聞"),
                    "time": entry.get("published", "")[:16],
                    "desc": "點擊開啟瀏覽器查看新聞完整詳細報導內容...",
                    "url": entry.get("link", "https://news.google.com"),
                    "is_hero": (idx == 0)
                })
            return items if items else self.fetch_news()
        except Exception:
            return self.fetch_news()

    def fetch_stocks(self):
        return {
            "market": {"name": "加權指數", "price": "22,850.12", "change": "+145.30", "pct": "+0.64%", "is_up": True, "status": "🟢 交易中"},
            "items": [
                {"code": "2330", "name": "台積電", "price": "980.0", "change": "+12.0", "pct": "+1.24%", "is_up": True},
                {"code": "2317", "name": "鴻海", "price": "185.5", "change": "-1.5", "pct": "-0.80%", "is_up": False},
                {"code": "2454", "name": "聯發科", "price": "1220.0", "change": "+15.0", "pct": "+1.24%", "is_up": True}
            ],
            "updated_at": datetime.now().strftime("%H:%M")
        }

# ==========================================
# 04. 頁面模組 (Pages)
# ==========================================
class WeatherPage(QWidget):
    """天氣資訊頁面 (Specification #22~#30)"""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignTokens.SPACING_MD)

        # Header
        top_layout = QHBoxLayout()
        self.city_label = QLabel("🌤️ 臺中市")
        self.city_label.setFont(QFont(DesignTokens.FONT_FAMILY, 16, QFont.Weight.Bold))
        self.city_label.setStyleSheet(f"color: {DesignTokens.TEXT_MAIN};")

        self.update_time_label = QLabel("資料更新於 --:--")
        self.update_time_label.setStyleSheet(f"color: {DesignTokens.TEXT_MUTED}; font-size: 12px;")

        top_layout.addWidget(self.city_label)
        top_layout.addStretch()
        top_layout.addWidget(self.update_time_label)
        layout.addLayout(top_layout)

        # 主卡片區域 (2 Columns)
        cards_layout = QHBoxLayout()

        # 左側天氣主卡 (Specification #24, #25)
        self.hero_card = CustomCard()
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(20, 20, 20, 20)

        self.wx_icon_label = QLabel("☀️ 晴朗")
        self.wx_icon_label.setFont(QFont(DesignTokens.FONT_FAMILY, 14, QFont.Weight.Bold))

        self.temp_label = QLabel("29°C")
        self.temp_label.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold)) # Large temperature #25
        self.temp_label.setStyleSheet(f"color: {DesignTokens.TEXT_MAIN};")

        self.sub_info_label = QLabel("濕度 72%  |  風速 2.1m/s\n降雨機率 20%  |  今日 25° / 32°")
        self.sub_info_label.setStyleSheet(f"color: {DesignTokens.TEXT_MUTED}; line-height: 1.4;")

        hero_layout.addWidget(self.wx_icon_label)
        hero_layout.addWidget(self.temp_label)
        hero_layout.addWidget(self.sub_info_label)

        # 右側 AQI 卡片 (Specification #27, #28)
        self.aqi_card = CustomCard()
        aqi_layout = QVBoxLayout(self.aqi_card)
        aqi_layout.setContentsMargins(20, 20, 20, 20)

        aqi_title = QLabel("🌫️ 空氣品質 (AQI)")
        aqi_title.setFont(QFont(DesignTokens.FONT_FAMILY, 13, QFont.Weight.Bold))

        self.aqi_val = QLabel("42")
        self.aqi_val.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self.aqi_val.setStyleSheet(f"color: {DesignTokens.SUCCESS};")

        self.aqi_desc = QLabel("狀態：良好\nPM2.5: 12 μg/m³\n\n資料來源：環境部")
        self.aqi_desc.setStyleSheet(f"color: {DesignTokens.TEXT_MUTED}; font-size: 11px;")

        aqi_layout.addWidget(aqi_title)
        aqi_layout.addWidget(self.aqi_val)
        aqi_layout.addWidget(self.aqi_desc)

        cards_layout.addWidget(self.hero_card, 3)
        cards_layout.addWidget(self.aqi_card, 2)
        layout.addLayout(cards_layout)

        # 逐小時預報 (Specification #29)
        hourly_title = QLabel("未來小時預報")
        hourly_title.setFont(QFont(DesignTokens.FONT_FAMILY, 12, QFont.Weight.Bold))
        layout.addWidget(hourly_title)

        self.hourly_layout = QHBoxLayout()
        self.hourly_layout.setSpacing(10)
        layout.addLayout(self.hourly_layout)

    def update_data(self, data):
        demo_str = " (DEMO)" if data.get("is_demo") else ""
        self.city_label.setText(f"🌤️ {data['location']}{demo_str}")
        self.update_time_label.setText(f"資料更新於 {data['updated_at']}")
        self.wx_icon_label.setText(f"☀️ {data['weather']}")
        self.temp_label.setText(f"{int(data['temperature'])}°C")
        self.sub_info_label.setText(
            f"濕度 {data['humidity']}%  |  風速 {data['wind_speed']}m/s\n"
            f"降雨機率 {data['rain_probability']}%  |  今日 {int(data['min_temperature'])}° / {int(data['max_temperature'])}°"
        )
        self.aqi_val.setText(str(data['aqi']))

        # 清除並重建 Hourly forecast
        while self.hourly_layout.count():
            item = self.hourly_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for h in data.get("hourly", []):
            card = CustomCard()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 10, 10, 10)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            t_lbl = QLabel(h["time"])
            t_lbl.setStyleSheet(f"color: {DesignTokens.TEXT_MUTED}; font-size: 11px;")
            i_lbl = QLabel(h["icon"])
            i_lbl.setFont(QFont("Segoe UI Emoji", 16))
            v_lbl = QLabel(h["temp"])
            v_lbl.setFont(QFont(DesignTokens.FONT_FAMILY, 12, QFont.Weight.Bold))

            cl.addWidget(t_lbl)
            cl.addWidget(i_lbl)
            cl.addWidget(v_lbl)
            self.hourly_layout.addWidget(card)

class NewsPage(QWidget):
    """新聞瀏覽頁面 (Specification #31~#39)"""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignTokens.SPACING_MD)

        # 分類標籤 (Specification #33)
        cat_layout = QHBoxLayout()
        categories = ["🔥 熱門", "🇹🇼 國內", "🌎 國際", "💻 科技", "🎬 娛樂"]
        for cat in categories:
            btn = QPushButton(cat)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DesignTokens.SURFACE_DARK};
                    color: {DesignTokens.TEXT_MUTED};
                    border-radius: 8px;
                    padding: 6px 12px;
                    border: 1px solid {DesignTokens.BORDER};
                }}
                QPushButton:hover {{
                    color: white;
                    border-color: {DesignTokens.PRIMARY};
                }}
            """)
            cat_layout.addWidget(btn)
        cat_layout.addStretch()
        layout.addLayout(cat_layout)

        # 滾動新聞列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_content = QWidget()
        self.news_list_layout = QVBoxLayout(self.scroll_content)
        self.news_list_layout.setSpacing(12)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    def update_data(self, news_items):
        while self.news_list_layout.count():
            item = self.news_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for item in news_items:
            card = CustomCard()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 16, 16, 16)

            title_prefix = "🔥 " if item.get("is_hero") else ""
            title = QLabel(f"{title_prefix}{item['title']}")
            title.setFont(QFont(DesignTokens.FONT_FAMILY, 12, QFont.Weight.Bold))
            title.setWordWrap(True)

            sub = QLabel(f"{item['source']} · {item['time']}")
            sub.setStyleSheet(f"color: {DesignTokens.TEXT_MUTED}; font-size: 11px;")

            desc = QLabel(item['desc'])
            desc.setStyleSheet(f"color: #CCCCCC; font-size: 12px;")
            desc.setWordWrap(True)

            cl.addWidget(title)
            cl.addWidget(sub)
            cl.addWidget(desc)

            # 點擊直接以系統瀏覽器開啟原始連結 (Specification #39)
            url = item["url"]
            card.mousePressEvent = lambda e, u=url: QDesktopServices.openUrl(QUrl(u))

            self.news_list_layout.addWidget(card)

class StocksPage(QWidget):
    """股市大盤與自選股頁面 (Specification #40~#48)"""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignTokens.SPACING_MD)

        # 大盤 Hero 卡片 (Specification #41)
        self.hero_card = CustomCard()
        hl = QVBoxLayout(self.hero_card)
        hl.setContentsMargins(20, 20, 20, 20)

        top_row = QHBoxLayout()
        title = QLabel("📈 加權指數")
        title.setFont(QFont(DesignTokens.FONT_FAMILY, 14, QFont.Weight.Bold))
        self.status_badge = QLabel("🟢 交易中")
        self.status_badge.setStyleSheet(f"color: {DesignTokens.SUCCESS}; font-size: 12px;")
        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(self.status_badge)

        self.price_label = QLabel("22,850.12")
        self.price_label.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))

        self.change_label = QLabel("▲ +145.30 (+0.64%)")
        self.change_label.setStyleSheet(f"color: {DesignTokens.DANGER}; font-size: 14px; font-weight: bold;") # 台灣慣用紅漲綠跌

        hl.addLayout(top_row)
        hl.addWidget(self.price_label)
        hl.addWidget(self.change_label)

        layout.addWidget(self.hero_card)

        # 自選股標頭與新增按鈕
        sub_hdr = QHBoxLayout()
        sub_title = QLabel("⭐ 我的自選股")
        sub_title.setFont(QFont(DesignTokens.FONT_FAMILY, 13, QFont.Weight.Bold))

        add_btn = QPushButton("＋ 新增股票")
        add_btn.setStyleSheet(f"background: {DesignTokens.PRIMARY}; color: white; border-radius: 8px; padding: 4px 12px;")
        sub_hdr.addWidget(sub_title)
        sub_hdr.addStretch()
        sub_hdr.addWidget(add_btn)
        layout.addLayout(sub_hdr)

        # 股票列表
        self.stocks_layout = QVBoxLayout()
        layout.addLayout(self.stocks_layout)
        layout.addStretch()

    def update_data(self, stock_data):
        m = stock_data["market"]
        self.price_label.setText(m["price"])
        self.change_label.setText(f"{m['change']} ({m['pct']})")
        self.status_badge.setText(m["status"])

        while self.stocks_layout.count():
            item = self.stocks_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for s in stock_data["items"]:
            card = CustomCard()
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)

            name_lbl = QLabel(f"<b>{s['name']}</b> <font color='#A0A0A0'>{s['code']}</font>")
            name_lbl.setFont(QFont(DesignTokens.FONT_FAMILY, 12))

            price_lbl = QLabel(s["price"])
            price_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))

            color = DesignTokens.DANGER if s["is_up"] else DesignTokens.SUCCESS
            change_lbl = QLabel(f"{s['change']} ({s['pct']})")
            change_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

            cl.addWidget(name_lbl)
            cl.addStretch()
            cl.addWidget(price_lbl)
            cl.addSpacing(20)
            cl.addWidget(change_lbl)

            self.stocks_layout.addWidget(card)

class GamesPage(QWidget):
    """無聊小遊戲頁面 (Specification #49~#54)"""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("🎮 無聊嗎？來玩一下小遊戲吧！")
        header.setFont(QFont(DesignTokens.FONT_FAMILY, 13, QFont.Weight.Bold))
        layout.addWidget(header)

        # 三款遊戲分頁 (Specification #51)
        game_sub_tabs = QTabWidget()
        game_sub_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; }}
            QTabBar::tab {{
                background: {DesignTokens.SURFACE_DARK};
                color: {DesignTokens.TEXT_MUTED};
                padding: 8px 16px;
                border-radius: 8px;
                margin-right: 6px;
            }}
            QTabBar::tab:selected {{
                background: {DesignTokens.PRIMARY};
                color: white;
            }}
        """)

        # 遊戲 1: 反應力
        self.reaction_widget = QWidget()
        rw_layout = QVBoxLayout(self.reaction_widget)
        self.react_btn = QPushButton("🎯 開始測試反應力")
        self.react_btn.setFixedHeight(120)
        self.react_btn.setStyleSheet(f"background: {DesignTokens.SURFACE_DARK}; color: white; border-radius: 14px; font-size: 16px; font-weight: bold;")
        self.react_btn.clicked.connect(self.start_reaction_test)
        rw_layout.addWidget(self.react_btn)

        # 遊戲 2: 記憶挑戰
        self.memory_widget = QWidget()
        mw_layout = QVBoxLayout(self.memory_widget)
        self.mem_label = QLabel("🧠 記住順序： ❓ ❓ ❓")
        self.mem_label.setFont(QFont(DesignTokens.FONT_FAMILY, 14, QFont.Weight.Bold))
        self.mem_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mem_start_btn = QPushButton("▶ 開始記憶挑戰")
        mem_start_btn.setStyleSheet(f"background: {DesignTokens.PRIMARY}; color: white; padding: 10px; border-radius: 8px;")
        mem_start_btn.clicked.connect(self.start_memory_game)
        mw_layout.addWidget(self.mem_label)
        mw_layout.addWidget(mem_start_btn)

        game_sub_tabs.addTab(self.reaction_widget, "🎯 反應力")
        game_sub_tabs.addTab(self.memory_widget, "🧠 記憶挑戰")

        layout.addWidget(game_sub_tabs)

    def start_reaction_test(self):
        self.react_btn.setText("準備... 當顏色變綠時立刻點擊！")
        self.react_btn.setStyleSheet(f"background: {DesignTokens.WARNING}; color: black; border-radius: 14px; font-size: 16px; font-weight: bold;")
        self.react_start_time = 0
        QTimer.singleShot(random.randint(2000, 4000), self.trigger_reaction_target)

    def trigger_reaction_target(self):
        self.react_start_time = time.time()
        self.react_btn.setText("點擊！！！")
        self.react_btn.setStyleSheet(f"background: {DesignTokens.SUCCESS}; color: white; border-radius: 14px; font-size: 20px; font-weight: bold;")
        self.react_btn.clicked.disconnect()
        self.react_btn.clicked.connect(self.finish_reaction_test)

    def finish_reaction_test(self):
        if self.react_start_time > 0:
            elapsed = int((time.time() - self.react_start_time) * 1000)
            self.react_btn.setText(f"🎉 反應時間：{elapsed} ms！\n點擊重新開始")
            self.react_btn.setStyleSheet(f"background: {DesignTokens.SURFACE_DARK}; color: white; border-radius: 14px; font-size: 16px; font-weight: bold;")
            self.react_start_time = 0
            self.react_btn.clicked.disconnect()
            self.react_btn.clicked.connect(self.start_reaction_test)

    def start_memory_game(self):
        icons = ["🍎", "⭐", "💎", "🐾", "🌈"]
        self.seq = [random.choice(icons) for _ in range(3)]
        self.mem_label.setText(f"🧠 記住順序： {' '.join(self.seq)}")
        QTimer.singleShot(2000, lambda: self.mem_label.setText("🧠 請在腦中回想剛才的圖示！"))

class SettingsPage(QWidget):
    """設定頁面 (Specification #55~#60)"""
    def __init__(self, config, save_callback):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignTokens.SPACING_MD)

        # 城市選擇
        c_layout = QHBoxLayout()
        c_layout.addWidget(QLabel("預設縣市:"))
        self.city_combo = QComboBox()
        self.city_combo.addItems(TAIWAN_CITIES)
        self.city_combo.setCurrentText(self.config["location"]["name"])
        self.city_combo.setStyleSheet(f"background: {DesignTokens.SURFACE_DARK}; color: white; padding: 6px; border-radius: 6px;")
        c_layout.addWidget(self.city_combo)
        layout.addLayout(c_layout)

        # DEMO 模式開關
        self.demo_cb = QCheckBox("啟用 DEMO 測試模式 (不浪費真實 API)")
        self.demo_cb.setChecked(self.config.get("demo_mode", True))
        layout.addWidget(self.demo_cb)

        # 儲存按鈕
        save_btn = QPushButton("💾 儲存設定")
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet(f"background: {DesignTokens.SUCCESS}; color: white; font-weight: bold; border-radius: {DesignTokens.RADIUS_BTN}px;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        # 關於區塊 (Specification #60)
        about_card = CustomCard()
        al = QVBoxLayout(about_card)
        al.addWidget(QLabel("<b>🐾 Desktop Pet</b> v1.0.0"))
        al.addWidget(QLabel("<font color='#A0A0A0'>一隻住在你桌面上的資訊小夥伴。<br>Made with Python + PySide6 (2026)</font>"))
        layout.addWidget(about_card)

        layout.addStretch()

    def save_settings(self):
        self.config["location"]["name"] = self.city_combo.currentText()
        self.config["demo_mode"] = self.demo_cb.isChecked()
        self.save_callback(self.config)

# ==========================================
# 05. Dashboard 主視窗 (Frameless & Custom Header)
# ==========================================
class DashboardWindow(QMainWindow):
    def __init__(self, config, on_config_save, on_refresh_req):
        super().__init__()
        self.config = config
        self.on_config_save = on_config_save
        self.on_refresh_req = on_refresh_req

        # 24px 圓角無邊框主視窗 (Specification #14, #15, #16)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(900, 650)
        self.setMinimumSize(760, 540) # Specification #87

        self.drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        # 圓角底板
        self.bg_frame = QFrame(self)
        self.bg_frame.setObjectName("BgFrame")
        self.bg_frame.setStyleSheet(f"""
            QFrame#BgFrame {{
                background-color: {DesignTokens.BG_DARK};
                border-radius: {DesignTokens.RADIUS_DASHBOARD}px;
                border: 1px solid {DesignTokens.BORDER};
            }}
        """)

        main_layout = QVBoxLayout(self.bg_frame)
        main_layout.setContentsMargins(24, 20, 24, 24)

        # 自訂 Header (Specification #16, #17, #18)
        header = QHBoxLayout()

        title_box = QVBoxLayout()
        title_lbl = QLabel("🐾 Desktop Pet")
        title_lbl.setFont(QFont(DesignTokens.FONT_FAMILY, 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {DesignTokens.TEXT_MAIN};")

        subtitle_lbl = QLabel(f"Good evening · 2026/08/26") # Current year 2026
        subtitle_lbl.setStyleSheet(f"color: {DesignTokens.TEXT_MUTED}; font-size: 11px;")

        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)

        # 右上角視窗控制項
        ctrl_box = QHBoxLayout()
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"background: {DesignTokens.SURFACE_DARK}; color: white; border-radius: 16px;")
        refresh_btn.clicked.connect(self.on_refresh_req)

        min_btn = QPushButton("−")
        min_btn.setFixedSize(32, 32)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setStyleSheet(f"background: {DesignTokens.SURFACE_DARK}; color: white; border-radius: 16px;")
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"background: rgba(239, 68, 68, 0.2); color: {DesignTokens.DANGER}; border-radius: 16px;")
        close_btn.clicked.connect(self.hide)

        ctrl_box.addWidget(refresh_btn)
        ctrl_box.addWidget(min_btn)
        ctrl_box.addWidget(close_btn)

        header.addLayout(title_box)
        header.addStretch()
        header.addLayout(ctrl_box)

        main_layout.addLayout(header)
        main_layout.addSpacing(10)

        # Segmented Navigation (Specification #19)
        self.nav = SegmentedNav(["🌤️ 天氣", "📰 新聞", "📈 股市", "🎮 遊戲", "⚙️ 設定"])
        self.nav.tab_changed.connect(self.switch_page)
        main_layout.addWidget(self.nav)
        main_layout.addSpacing(10)

        # Stacked Pages
        self.pages_stack = QStackedWidget()

        self.weather_page = WeatherPage()
        self.news_page = NewsPage()
        self.stocks_page = StocksPage()
        self.games_page = GamesPage()
        self.settings_page = SettingsPage(self.config, self.on_config_save)

        self.pages_stack.addWidget(self.weather_page)
        self.pages_stack.addWidget(self.news_page)
        self.pages_stack.addWidget(self.stocks_page)
        self.pages_stack.addWidget(self.games_page)
        self.pages_stack.addWidget(self.settings_page)

        main_layout.addWidget(self.pages_stack)

        self.setCentralWidget(self.bg_frame)

    def switch_page(self, index):
        self.pages_stack.setCurrentIndex(index)

    def update_all_data(self, data):
        self.weather_page.update_data(data["weather"])
        self.news_page.update_data(data["news"])
        self.stocks_page.update_data(data["stocks"])
        ToastManager.show(self, "資料已成功更新！")

    # 視窗拖曳支援
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

# ==========================================
# 06. 桌寵本體視窗 (Pet Layer & Animations)
# ==========================================
class PetWindow(QWidget):
    """透明無邊框桌寵 (Specification #03~#13)"""
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.dashboard = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(160, 160)

        self.init_ui()
        self.init_tray()
        self.init_float_animation()

        # 初始資料抓取
        self.refresh_data()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    res = DEFAULT_CONFIG.copy()
                    res.update(cfg)
                    return res
            except Exception: pass
        return DEFAULT_CONFIG.copy()

    def save_config(self, cfg):
        self.config = cfg
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
        except Exception: pass
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 文字氣泡 (Specification #11, #12)
        self.bubble = QLabel("早安！喵~", self)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setFont(QFont(DesignTokens.FONT_FAMILY, 9, QFont.Weight.Bold))
        self.bubble.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.95);
            color: #121212;
            border-radius: 10px;
            padding: 6px 10px;
        """)
        self.bubble.hide()

        # 桌寵角色標籤
        self.pet_avatar = QLabel("🐾", self)
        self.pet_avatar.setFont(QFont("Segoe UI Emoji", 56))
        self.pet_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 柔和陰影 (Specification #05)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffsetY(6)
        self.pet_avatar.setGraphicsEffect(shadow)

        layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.pet_avatar, 0, Qt.AlignmentFlag.AlignCenter)

        # 預設定位於右下角 (Specification #04)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 190, screen.height() - 230)

    def init_float_animation(self):
        """微幅上下浮動動畫 (Specification #06)"""
        self.float_offset = 0
        self.float_direction = 1
        self.float_timer = QTimer(self)
        self.float_timer.timeout.connect(self.update_float)
        self.float_timer.start(80) # 週期約 2~4 秒

    def update_float(self):
        self.float_offset += 0.5 * self.float_direction
        if abs(self.float_offset) > 6:
            self.float_direction *= -1
        self.pet_avatar.move(self.pet_avatar.x(), 30 + int(self.float_offset))

    def init_tray(self):
        """系統託盤選單 (Specification #13)"""
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()
        open_act = QAction("🐾 開啟資訊 Dashboard", self)
        open_act.triggered.connect(self.open_dashboard)
        refresh_act = QAction("🔄 更新資料", self)
        refresh_act.triggered.connect(self.refresh_data)
        quit_act = QAction("❌ 關閉桌寵", self)
        quit_act.triggered.connect(QApplication.quit)

        tray_menu.addAction(open_act)
        tray_menu.addAction(refresh_act)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_act)

        self.tray.setContextMenu(tray_menu)
        self.tray.show()

    def refresh_data(self):
        self.worker = APIWorker(
            self.config["location"]["name"],
            self.config["favorite_stocks"],
            self.config.get("demo_mode", True)
        )
        self.worker.data_loaded.connect(self.on_data_loaded)
        self.worker.start()

    def on_data_loaded(self, data):
        self.cached_data = data
        if self.dashboard and self.dashboard.isVisible():
            self.dashboard.update_all_data(data)

    def show_bubble(self, text):
        self.bubble.setText(text)
        self.bubble.show()
        QTimer.singleShot(2500, self.bubble.hide)

    # 點擊與雙擊事件處理 (Specification #09, #10)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            msgs = ["今天也要加油喔！", "雙擊我可以看最新新聞！", "外面天氣如何呢？", "記得多喝水喔~"]
            self.show_bubble(random.choice(msgs))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pet_avatar.setText("😮") # 驚喜表情
            QTimer.singleShot(600, lambda: self.pet_avatar.setText("🐾"))
            self.open_dashboard()

    def open_dashboard(self):
        if not self.dashboard:
            self.dashboard = DashboardWindow(self.config, self.save_config, self.refresh_data)

        if hasattr(self, 'cached_data'):
            self.dashboard.update_all_data(self.cached_data)

        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

# ==========================================
# 07. 主程式進入點 (Main Entry Point)
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 單一執行實例防護
    shared_mem = QSharedMemory("DesktopPet_Unique_Key_2026")
    if not shared_mem.create(1):
        print("桌寵程式已在運行中！")
        sys.exit(0)

    pet = PetWindow()
    pet.show()

    sys.exit(app.exec())
