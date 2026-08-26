import json
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPoint, QSharedMemory, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QFrame, QGraphicsDropShadowEffect,
    QSystemTrayIcon, QMenu, QComboBox, QCheckBox, QLineEdit, QMessageBox, QStyle
)

load_dotenv()

APP_NAME = "Desktop Pet"
CONFIG_PATH = Path.home() / ".desktop_pet_config.json"
CACHE_DIR = Path.home() / ".desktop_pet_cache"
CACHE_DIR.mkdir(exist_ok=True)

CWA_KEY = os.getenv("CWA_API_KEY", "").strip()
MOENV_KEY = os.getenv("MOENV_API_KEY", "").strip()
GNEWS_KEY = os.getenv("GNEWS_API_KEY", "").strip()
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

CWA_BASE = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
MOENV_AQI_URL = "https://data.moenv.gov.tw/api/v2/AQX_P_432"
GNEWS_URL = "https://gnews.io/api/v4/top-headlines"
TWSE_BASE = "https://openapi.twse.com.tw/v1"

CITIES = [
    "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市",
    "基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣",
    "雲林縣", "嘉義市", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣",
    "臺東縣", "澎湖縣", "金門縣", "連江縣"
]

class T:
    BG = "#101114"
    CARD = "#1A1D23"
    CARD_2 = "#20242B"
    PRIMARY = "#7C8CFF"
    PRIMARY_2 = "#99A5FF"
    TEXT = "#F6F7FB"
    MUTED = "#9DA3B4"
    SUCCESS = "#35D07F"
    DANGER = "#FF6076"
    WARNING = "#FFC857"
    BORDER = "rgba(255,255,255,0.07)"
    FONT = "Microsoft JhengHei UI"

DEFAULT_CONFIG = {
    "city": "臺中市",
    "favorites": ["2330", "2317", "2454"],
    "theme": "dark",
    "pet_scale": 1.0,
    "opacity": 1.0,
    "autostart": True,
    "animation": True,
    "sound": True,
    "demo_mode": DEMO_MODE,
}


def load_config():
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_write(name: str, data: Any):
    try:
        (CACHE_DIR / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def cache_read(name: str):
    try:
        p = CACHE_DIR / f"{name}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def api_get(url: str, *, params=None, headers=None, timeout=10):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def safe_first(value, default=None):
    if isinstance(value, list) and value:
        return value[0]
    return default


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class WeatherData:
    location: str
    temperature: float | None
    weather: str
    humidity: float | None
    wind_speed: float | None
    rain_probability: int | None
    max_temperature: float | None
    min_temperature: float | None
    comfort_index: str
    aqi: int | None
    aqi_status: str
    pm25: float | None
    updated_at: str
    source: str
    is_demo: bool = False


class WeatherService:
    def __init__(self, city: str, demo=False):
        self.city = city
        self.demo = demo

    def get(self):
        if self.demo:
            return self.demo_data()
        if not CWA_KEY:
            cached = cache_read("weather")
            if cached:
                return WeatherData(**cached)
            raise RuntimeError("尚未設定 CWA_API_KEY")

        headers = {"Authorization": CWA_KEY}
        obs = api_get(f"{CWA_BASE}/O-A0003-001", headers=headers, params={"format": "JSON"})
        fc = api_get(f"{CWA_BASE}/F-C0032-001", headers=headers, params={"format": "JSON", "locationName": self.city})

        stations = obs.get("records", {}).get("Station", [])
        if not stations:
            stations = obs.get("records", {}).get("station", [])
        station = self._pick_station(stations)
        if not station:
            raise RuntimeError(f"找不到 {self.city} 的 CWA 觀測站")

        element = station.get("WeatherElement", station.get("weatherElement", {})) or {}
        weather = element.get("Weather") or element.get("weather") or ""
        temp = parse_float(element.get("AirTemperature", element.get("airTemperature")))
        humidity = parse_float(element.get("RelativeHumidity", element.get("relativeHumidity")))
        wind = parse_float(element.get("WindSpeed", element.get("windSpeed")))

        loc = self._pick_forecast_location(fc)
        wx = pop = mint = maxt = ci = None
        if loc:
            elements = loc.get("weatherElement", loc.get("WeatherElement", [])) or []
            for e in elements:
                name = e.get("elementName") or e.get("ElementName")
                times = e.get("time", e.get("Time", [])) or []
                param = safe_first(times, {}).get("parameter", {}) if times else {}
                value = param.get("parameterName") if param else None
                if name == "Wx" and wx is None:
                    wx = value
                elif name == "PoP" and pop is None:
                    pop = parse_float(value)
                elif name == "MinT" and mint is None:
                    mint = parse_float(value)
                elif name == "MaxT" and maxt is None:
                    maxt = parse_float(value)
                elif name == "CI" and ci is None:
                    ci = value

        result = WeatherData(
            location=self.city,
            temperature=temp,
            weather=weather or wx or "未知",
            humidity=humidity,
            wind_speed=wind,
            rain_probability=int(pop) if pop is not None else None,
            max_temperature=maxt,
            min_temperature=mint,
            comfort_index=ci or "—",
            aqi=None,
            aqi_status="—",
            pm25=None,
            updated_at=datetime.now().strftime("%H:%M"),
            source="中央氣象署 CWA",
        )
        cache_write("weather", asdict(result))
        return result

    def _pick_station(self, stations):
        candidates = [s for s in stations if s.get("CountyName") == self.city or s.get("County") == self.city]
        if not candidates:
            short = self.city.replace("臺", "台")
            candidates = [s for s in stations if s.get("CountyName", "").replace("臺", "台") == short]
        return next((s for s in candidates if self._station_has_temp(s)), None) or safe_first(candidates)

    @staticmethod
    def _station_has_temp(station):
        e = station.get("WeatherElement", station.get("weatherElement", {})) or {}
        return parse_float(e.get("AirTemperature", e.get("airTemperature"))) is not None

    def _pick_forecast_location(self, data):
        locs = data.get("records", {}).get("location", [])
        if not locs:
            locs = data.get("records", {}).get("Location", [])
        return next((x for x in locs if x.get("locationName") == self.city or x.get("LocationName") == self.city), safe_first(locs))

    def demo_data(self):
        return WeatherData(self.city, 29.0, "多雲時晴", 72, 2.1, 20, 32, 25, "舒適", 42, "良好", 12, datetime.now().strftime("%H:%M"), "DEMO", True)


class AQIService:
    def __init__(self, city: str, demo=False):
        self.city = city
        self.demo = demo

    def get(self):
        if self.demo:
            return {"aqi": 42, "status": "良好", "pm25": 12, "source": "DEMO"}
        if not MOENV_KEY:
            cached = cache_read("aqi")
            if cached:
                return cached
            raise RuntimeError("尚未設定 MOENV_API_KEY")
        data = api_get(MOENV_AQI_URL, params={"api_key": MOENV_KEY, "format": "json", "offset": 0, "limit": 1000})
        rows = data.get("records", [])
        candidates = [r for r in rows if r.get("County") == self.city]
        row = next((r for r in candidates if str(r.get("AQI", "")).strip().isdigit()), None)
        if not row:
            raise RuntimeError(f"找不到 {self.city} 的有效 AQI 測站")
        result = {"aqi": int(row["AQI"]), "status": row.get("Status", ""), "pm25": parse_float(row.get("PM2.5")), "site": row.get("SiteName", ""), "source": "環境部"}
        cache_write("aqi", result)
        return result


class NewsService:
    CATEGORIES = {"熱門": "general", "國內": "nation", "國際": "world", "科技": "technology", "娛樂": "entertainment"}

    def __init__(self, category="general", demo=False):
        self.category = category
        self.demo = demo

    def get(self):
        if self.demo:
            return self.demo_data()
        if not GNEWS_KEY:
            cached = cache_read("news")
            if cached:
                return cached
            raise RuntimeError("尚未設定 GNEWS_API_KEY")
        data = api_get(GNEWS_URL, params={"apikey": GNEWS_KEY, "category": self.category, "lang": "zh", "country": "tw", "max": 10})
        items = []
        for i, article in enumerate(data.get("articles", [])):
            source = article.get("source", {}) or {}
            items.append({
                "title": article.get("title") or "無標題",
                "desc": article.get("description") or "",
                "url": article.get("url") or "",
                "image": article.get("image") or "",
                "source": source.get("name") or "未知媒體",
                "time": article.get("publishedAt") or "",
                "hero": i == 0,
            })
        if not items:
            raise RuntimeError("新聞 API 沒有回傳文章")
        cache_write("news", items)
        return items

    @staticmethod
    def demo_data():
        return [
            {"title": "2026 科技趨勢：AI 應用持續成為焦點", "desc": "這是開發測試用的示範新聞。", "url": "https://news.google.com/", "image": "", "source": "Demo News", "time": "現在", "hero": True},
            {"title": "今日國際焦點新聞示例", "desc": "這是開發測試用的示範新聞。", "url": "https://news.google.com/", "image": "", "source": "Demo News", "time": "今天", "hero": False},
        ]


class StockService:
    def __init__(self, favorites, demo=False):
        self.favorites = favorites
        self.demo = demo

    def get(self):
        if self.demo:
            return {
                "market": {"price": "22,850.12", "change": "+145.30", "pct": "+0.64%", "status": "🟢 測試資料"},
                "items": [
                    {"code": "2330", "name": "台積電", "price": "980.0", "change": "+12.0", "pct": "+1.24%"},
                    {"code": "2317", "name": "鴻海", "price": "185.5", "change": "-1.5", "pct": "-0.80%"},
                    {"code": "2454", "name": "聯發科", "price": "1220.0", "change": "+15.0", "pct": "+1.24%"},
                ],
                "updated_at": datetime.now().strftime("%H:%M"),
                "source": "DEMO",
            }
        rows = api_get(f"{TWSE_BASE}/exchangeReport/STOCK_DAY_ALL", timeout=10)
        wanted = set(self.favorites)
        items = []
        for row in rows:
            code = str(row.get("Code", ""))
            if code in wanted:
                items.append({
                    "code": code,
                    "name": row.get("Name", code),
                    "price": row.get("ClosingPrice", "—"),
                    "change": row.get("Change", "—"),
                    "pct": "",
                })
        data = {"market": {"price": "—", "change": "—", "pct": "", "status": "⚪ 最新市場資料"}, "items": items, "updated_at": datetime.now().strftime("%H:%M"), "source": "TWSE"}
        cache_write("stocks", data)
        return data


class Worker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        try:
            city = self.config["city"]
            demo = self.config.get("demo_mode", True)
            weather = WeatherService(city, demo).get()
            aqi = AQIService(city, demo).get()
            weather.aqi = aqi.get("aqi")
            weather.aqi_status = aqi.get("status", "—")
            weather.pm25 = aqi.get("pm25")
            news = NewsService("general", demo).get()
            stocks = StockService(self.config.get("favorites", []), demo).get()
            self.done.emit({"weather": asdict(weather), "news": news, "stocks": stocks})
        except Exception as exc:
            self.failed.emit(str(exc))


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame{{background:{T.CARD};border:1px solid {T.BORDER};border-radius:18px;}}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0,0,0,70))
        self.setGraphicsEffect(shadow)


class WeatherPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setSpacing(16)
        self.title = QLabel("🌤️ 臺中市")
        self.title.setFont(QFont(T.FONT, 17, QFont.Weight.Bold))
        self.time = QLabel("等待資料…"); self.time.setStyleSheet(f"color:{T.MUTED}")
        head = QHBoxLayout(); head.addWidget(self.title); head.addStretch(); head.addWidget(self.time); root.addLayout(head)
        row = QHBoxLayout(); row.setSpacing(16)
        self.hero = Card(); hl = QVBoxLayout(self.hero)
        self.wx = QLabel("☀️ 多雲時晴"); self.wx.setStyleSheet(f"font-size:15px;font-weight:700;color:{T.TEXT}")
        self.temp = QLabel("--°C"); self.temp.setFont(QFont("Segoe UI", 52, QFont.Weight.Bold))
        self.meta = QLabel("濕度 --  ·  風速 --\n降雨 --  ·  今日 -- / --")
        self.meta.setStyleSheet(f"color:{T.MUTED};line-height:1.6")
        hl.addWidget(self.wx); hl.addWidget(self.temp); hl.addWidget(self.meta); row.addWidget(self.hero, 3)
        self.aqi = Card(); al = QVBoxLayout(self.aqi)
        al.addWidget(QLabel("🌫️ 空氣品質"))
        self.aqi_num = QLabel("--"); self.aqi_num.setFont(QFont("Segoe UI", 40, QFont.Weight.Bold))
        self.aqi_desc = QLabel("等待資料…"); self.aqi_desc.setStyleSheet(f"color:{T.MUTED}")
        al.addWidget(self.aqi_num); al.addWidget(self.aqi_desc); row.addWidget(self.aqi, 2); root.addLayout(row)
        root.addWidget(QLabel("預報摘要"))
        self.forecast = Card(); fl = QVBoxLayout(self.forecast)
        self.forecast_label = QLabel("等待 CWA 預報資料…"); self.forecast_label.setWordWrap(True); fl.addWidget(self.forecast_label); root.addWidget(self.forecast)
        root.addStretch()

    def update(self, d):
        self.title.setText(f"🌤️ {d['location']}{'  ·  DEMO' if d.get('is_demo') else ''}")
        self.time.setText(f"更新 {d['updated_at']} · {d.get('source','')}")
        self.wx.setText(f"☀️ {d['weather']}")
        self.temp.setText("--°C" if d.get('temperature') is None else f"{d['temperature']:.0f}°C")
        self.meta.setText(f"濕度 {d.get('humidity','--')}%  ·  風速 {d.get('wind_speed','--')} m/s\n降雨 {d.get('rain_probability','--')}%  ·  今日 {d.get('min_temperature','--')}° / {d.get('max_temperature','--')}°")
        self.aqi_num.setText("--" if d.get('aqi') is None else str(d['aqi']))
        self.aqi_desc.setText(f"狀態：{d.get('aqi_status','—')}\nPM2.5：{d.get('pm25','—')}\n資料來源：環境部")
        self.forecast_label.setText(f"舒適度：{d.get('comfort_index','—')}\nCWA 來源：{d.get('source','中央氣象署 CWA')}\n降雨機率：{d.get('rain_probability','—')}%")


class NewsPage(QWidget):
    def __init__(self):
        super().__init__(); root = QVBoxLayout(self); root.setSpacing(12)
        self.status = QLabel("📰 今日頭條"); self.status.setFont(QFont(T.FONT, 17, QFont.Weight.Bold)); root.addWidget(self.status)
        self.listbox = QVBoxLayout(); root.addLayout(self.listbox); root.addStretch()

    def update(self, items):
        while self.listbox.count():
            item = self.listbox.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not items:
            self.listbox.addWidget(QLabel("目前沒有新聞資料。")); return
        for article in items:
            card = Card(); lay = QVBoxLayout(card)
            title = QLabel(("🔥 " if article.get("hero") else "") + article.get("title", "")); title.setFont(QFont(T.FONT, 13, QFont.Weight.Bold)); title.setWordWrap(True)
            meta = QLabel(f"{article.get('source','')} · {article.get('time','')}"); meta.setStyleSheet(f"color:{T.MUTED};font-size:11px")
            desc = QLabel(article.get("desc", "")); desc.setWordWrap(True); desc.setStyleSheet(f"color:{T.MUTED}")
            lay.addWidget(title); lay.addWidget(meta); lay.addWidget(desc)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            url = article.get("url", "")
            card.mousePressEvent = lambda e, u=url: QDesktopServices.openUrl(QUrl(u))
            self.listbox.addWidget(card)


class StocksPage(QWidget):
    def __init__(self):
        super().__init__(); root = QVBoxLayout(self); root.setSpacing(12)
        self.header = QLabel("📈 台股"); self.header.setFont(QFont(T.FONT, 17, QFont.Weight.Bold)); root.addWidget(self.header)
        self.market = Card(); ml = QVBoxLayout(self.market)
        self.market_price = QLabel("—"); self.market_price.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self.market_status = QLabel("等待資料…"); self.market_status.setStyleSheet(f"color:{T.MUTED}")
        ml.addWidget(QLabel("加權指數")); ml.addWidget(self.market_price); ml.addWidget(self.market_status); root.addWidget(self.market)
        root.addWidget(QLabel("⭐ 我的自選股")); self.listbox = QVBoxLayout(); root.addLayout(self.listbox); root.addStretch()

    def update(self, data):
        self.market_price.setText(data.get("market", {}).get("price", "—"))
        self.market_status.setText(f"{data.get('market', {}).get('status','')} · 更新 {data.get('updated_at','')}")
        while self.listbox.count():
            i = self.listbox.takeAt(0)
            if i.widget(): i.widget().deleteLater()
        for s in data.get("items", []):
            c = Card(); lay = QHBoxLayout(c)
            name = QLabel(f"<b>{s['name']}</b>  <span style='color:#9DA3B4'>{s['code']}</span>")
            price = QLabel(str(s.get("price","—"))); price.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            change = QLabel(f"{s.get('change','')} {s.get('pct','')}")
            val = str(s.get('change',''))
            change.setStyleSheet(f"color:{T.DANGER if not val.startswith('-') else T.SUCCESS};font-weight:700")
            lay.addWidget(name); lay.addStretch(); lay.addWidget(price); lay.addSpacing(16); lay.addWidget(change); self.listbox.addWidget(c)


class GamesPage(QWidget):
    def __init__(self):
        super().__init__(); root = QVBoxLayout(self); root.setSpacing(14)
        title = QLabel("🎮 無聊嗎？來玩一下！"); title.setFont(QFont(T.FONT, 17, QFont.Weight.Bold)); root.addWidget(title)
        self.game_btn = QPushButton("🎯 開始反應力挑戰")
        self.game_btn.setMinimumHeight(180)
        self.game_btn.setStyleSheet(f"background:{T.CARD};color:{T.TEXT};border-radius:18px;font-size:18px;font-weight:700")
        self.game_btn.clicked.connect(self.start_reaction)
        root.addWidget(self.game_btn)
        self.game_state = 0; self.started = 0.0; self.best = None
        mem = QPushButton("🧠 記憶挑戰（簡易版）"); mem.clicked.connect(self.memory_game); root.addWidget(mem)
        root.addStretch()

    def start_reaction(self):
        self.game_state = 1; self.game_btn.setText("準備……等綠色出現"); self.game_btn.setStyleSheet(f"background:{T.WARNING};color:#111;border-radius:18px;font-size:18px;font-weight:700")
        QTimer.singleShot(random.randint(1500, 3500), self._react_ready)

    def _react_ready(self):
        if self.game_state != 1: return
        self.game_state = 2; self.started = time.perf_counter(); self.game_btn.setText("⚡ 現在點！"); self.game_btn.setStyleSheet(f"background:{T.SUCCESS};color:white;border-radius:18px;font-size:24px;font-weight:700"); self.game_btn.clicked.disconnect(); self.game_btn.clicked.connect(self._react_done)

    def _react_done(self):
        elapsed = (time.perf_counter() - self.started) * 1000; self.best = elapsed if self.best is None else min(self.best, elapsed)
        self.game_state = 0; self.game_btn.setText(f"🎉 {elapsed:.0f} ms\n最佳 {self.best:.0f} ms\n\n再次挑戰"); self.game_btn.setStyleSheet(f"background:{T.CARD};color:{T.TEXT};border-radius:18px;font-size:18px;font-weight:700"); self.game_btn.clicked.disconnect(); self.game_btn.clicked.connect(self.start_reaction)

    def memory_game(self):
        seq = [random.choice(["🐾","⭐","🍎","🌈","💎"]) for _ in range(4)]
        QMessageBox.information(self, "🧠 記憶挑戰", "請記住：\n\n" + "  ".join(seq) + "\n\n2 秒後會消失。")


class SettingsPage(QWidget):
    saved = Signal()
    def __init__(self, config):
        super().__init__(); self.config = config; root = QVBoxLayout(self); root.setSpacing(12)
        title = QLabel("⚙️ 設定"); title.setFont(QFont(T.FONT, 17, QFont.Weight.Bold)); root.addWidget(title)
        row = QHBoxLayout(); row.addWidget(QLabel("城市")); self.city = QComboBox(); self.city.addItems(CITIES); self.city.setCurrentText(config.get("city","臺中市")); row.addWidget(self.city); root.addLayout(row)
        self.autostart = QCheckBox("Windows 登入後自動啟動"); self.autostart.setChecked(config.get("autostart", True)); root.addWidget(self.autostart)
        self.demo = QCheckBox("DEMO 測試模式"); self.demo.setChecked(config.get("demo_mode", True)); root.addWidget(self.demo)
        self.animation = QCheckBox("啟用桌寵動畫"); self.animation.setChecked(config.get("animation", True)); root.addWidget(self.animation)
        self.sound = QCheckBox("啟用音效"); self.sound.setChecked(config.get("sound", True)); root.addWidget(self.sound)
        save = QPushButton("💾 儲存設定"); save.clicked.connect(self.save); root.addWidget(save); root.addStretch()

    def save(self):
        self.config.update({"city": self.city.currentText(), "autostart": self.autostart.isChecked(), "demo_mode": self.demo.isChecked(), "animation": self.animation.isChecked(), "sound": self.sound.isChecked()})
        save_config(self.config); self.saved.emit()


class Dashboard(QMainWindow):
    def __init__(self, config, refresh_callback):
        super().__init__(); self.config = config; self.refresh_callback = refresh_callback
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.resize(900,650); self.setMinimumSize(760,540)
        base = QFrame(); base.setStyleSheet(f"QFrame{{background:{T.BG};border:1px solid {T.BORDER};border-radius:24px}}")
        root = QVBoxLayout(base); root.setContentsMargins(24,20,24,24); root.setSpacing(12)
        top = QHBoxLayout(); title = QLabel("🐾 Desktop Pet"); title.setFont(QFont(T.FONT,16,QFont.Weight.Bold)); top.addWidget(title); sub = QLabel(datetime.now().strftime("%Y/%m/%d  %A")); sub.setStyleSheet(f"color:{T.MUTED}"); top.addWidget(sub); top.addStretch()
        ref = QPushButton("↻"); ref.clicked.connect(refresh_callback); close = QPushButton("✕"); close.clicked.connect(self.hide); top.addWidget(ref); top.addWidget(close); root.addLayout(top)
        nav = QHBoxLayout(); self.buttons=[]
        names=["🌤️ 天氣","📰 新聞","📈 股市","🎮 遊戲","⚙️ 設定"]
        self.stack=QStackedWidget()
        self.weather=WeatherPage(); self.news=NewsPage(); self.stocks=StocksPage(); self.games=GamesPage(); self.settings=SettingsPage(config); self.settings.saved.connect(refresh_callback)
        for i,name in enumerate(names):
            b=QPushButton(name); b.clicked.connect(lambda _,x=i:self.stack.setCurrentIndex(x)); nav.addWidget(b); self.buttons.append(b)
        root.addLayout(nav)
        for p in [self.weather,self.news,self.stocks,self.games,self.settings]: self.stack.addWidget(p)
        root.addWidget(self.stack); self.setCentralWidget(base)

    def update(self, data):
        self.weather.update(data["weather"]); self.news.update(data["news"]); self.stocks.update(data["stocks"])


class Pet(QWidget):
    def __init__(self):
        super().__init__(); self.config=load_config(); self.dashboard=None; self.worker=None; self.drag_offset=QPoint(); self.cached=None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.resize(160,160)
        layout=QVBoxLayout(self); layout.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.setContentsMargins(0,0,0,0)
        self.bubble=QLabel("",self); self.bubble.hide(); self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter); self.bubble.setStyleSheet("background:rgba(255,255,255,.95);color:#111;padding:7px 10px;border-radius:12px")
        self.avatar=QLabel("🐾",self); self.avatar.setFont(QFont("Segoe UI Emoji",58)); self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shadow=QGraphicsDropShadowEffect(self); shadow.setBlurRadius(20); shadow.setColor(QColor(0,0,0,80)); shadow.setOffset(0,5); self.avatar.setGraphicsEffect(shadow)
        layout.addWidget(self.bubble); layout.addWidget(self.avatar)
        self._place(); self._float=0; self._dir=1; self.timer=QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(80 if self.config.get("animation",True) else 250)
        self.tray=QSystemTrayIcon(self); self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)); menu=QMenu(); a=QAction("🐾 開啟資訊",self); a.triggered.connect(self.open_dashboard); menu.addAction(a); r=QAction("🔄 更新資料",self); r.triggered.connect(self.refresh); menu.addAction(r); menu.addSeparator(); q=QAction("❌ 關閉",self); q.triggered.connect(QApplication.quit); menu.addAction(q); self.tray.setContextMenu(menu); self.tray.show()
        self.refresh()

    def _place(self):
        screen=QApplication.primaryScreen().availableGeometry(); self.move(screen.right()-190,screen.bottom()-190)

    def _tick(self):
        if not self.config.get("animation",True): return
        self._float += .5*self._dir
        if abs(self._float)>6: self._dir*=-1
        self.avatar.move(self.avatar.x(), max(55, 55+int(self._float)))

    def show_bubble(self,text):
        self.bubble.setText(text); self.bubble.show(); QTimer.singleShot(2200,self.bubble.hide)

    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.drag_offset=e.globalPosition().toPoint()-self.frameGeometry().topLeft(); e.accept()

    def mouseMoveEvent(self,e):
        if e.buttons() & Qt.MouseButton.LeftButton: self.move(e.globalPosition().toPoint()-self.drag_offset); e.accept()

    def mouseReleaseEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.show_bubble(random.choice(["嘿！","今天也加油！","雙擊我看資訊～","有點無聊嗎？"]))

    def mouseDoubleClickEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.avatar.setText("😮"); QTimer.singleShot(450,lambda:self.avatar.setText("🐾")); self.open_dashboard()

    def open_dashboard(self):
        if self.dashboard is None: self.dashboard=Dashboard(self.config,self.refresh)
        if self.cached: self.dashboard.update(self.cached)
        self.dashboard.show(); self.dashboard.raise_(); self.dashboard.activateWindow()

    def refresh(self):
        if self.worker and self.worker.isRunning(): return
        self.worker=Worker(self.config); self.worker.done.connect(self._loaded); self.worker.failed.connect(self._failed); self.worker.start()

    def _loaded(self,data):
        self.cached=data
        if self.dashboard and self.dashboard.isVisible(): self.dashboard.update(data)

    def _failed(self,msg):
        self.show_bubble("資料更新失敗")
        self.cached = self.cached or {"weather": asdict(WeatherService(self.config['city'],True).demo_data()), "news": NewsService().demo_data(), "stocks": StockService(self.config.get('favorites',[]),True).get()}
        if self.dashboard and self.dashboard.isVisible(): self.dashboard.update(self.cached)


def enable_autostart():
    try:
        from win32com.client import Dispatch
        startup=Path(os.getenv("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
        shortcut=startup / "Desktop Pet.lnk"
        target=Path(sys.executable).resolve()
        if target.name.lower() == "python.exe":
            target = target.with_name("pythonw.exe")
        if Path(sys.argv[0]).suffix.lower()==".py":
            args=f'"{Path(sys.argv[0]).resolve()}"'
        else:
            args=""
        shell=Dispatch("WScript.Shell"); link=shell.CreateShortCut(str(shortcut)); link.Targetpath=str(target); link.Arguments=args; link.WorkingDirectory=str(Path(sys.argv[0]).resolve().parent); link.save()
        return True
    except Exception:
        return False


def disable_autostart():
    try:
        p=Path(os.getenv("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/Desktop Pet.lnk"
        p.unlink(missing_ok=True); return True
    except Exception:
        return False


if __name__ == "__main__":
    app=QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    shared=QSharedMemory("DesktopPet_Unique_Key_2026_v2")
    if not shared.create(1): sys.exit(0)
    pet=Pet(); pet.show()
    if pet.config.get("autostart", True): enable_autostart()
    else: disable_autostart()
    sys.exit(app.exec())
