import json
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests
from dotenv import load_dotenv

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPoint, QUrl
from PySide6.QtGui import QFont, QColor, QDesktopServices, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QFrame, QComboBox, QCheckBox, QLineEdit,
    QScrollArea, QMessageBox, QGridLayout, QListWidget, QListWidgetItem,
    QSpinBox, QProgressBar, QSystemTrayIcon, QMenu, QDialog, QDialogButtonBox
)

try:
    import win32com.client  # type: ignore
except ImportError:
    win32com = None

load_dotenv()

APP_NAME = "Desktop Pet"
CONFIG_PATH = Path.home() / ".desktop_pet_config.json"
CACHE_DIR = Path.home() / ".desktop_pet_cache"
CACHE_DIR.mkdir(exist_ok=True)

CWA_KEY = os.getenv("CWA_API_KEY", "").strip()
MOENV_KEY = os.getenv("MOENV_API_KEY", "").strip()
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

CWA_BASE = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
MOENV_URL = "https://data.moenv.gov.tw/api/v2/AQX_P_432"
TWSE_BASE = "https://openapi.twse.com.tw/v1"

RSS_FEEDS = {
    "🔥 熱門": "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "🇹🇼 國內": "https://news.google.com/rss/search?q=" + quote_plus("台灣") + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "💻 科技": "https://news.google.com/rss/search?q=" + quote_plus("科技 OR AI OR 人工智慧") + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "📈 財經": "https://news.google.com/rss/search?q=" + quote_plus("台股 OR 股市 OR 財經") + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "🎬 娛樂": "https://news.google.com/rss/search?q=" + quote_plus("娛樂 OR 電影 OR 音樂") + "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
}

CITIES = [
    "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市",
    "基隆市", "新竹市", "新竹縣", "苗栗縣", "彰化縣", "南投縣",
    "雲林縣", "嘉義市", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣",
    "臺東縣", "澎湖縣", "金門縣", "連江縣"
]

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
    "best_reaction": 9999,
    "best_memory": 0,
    "best_catcher": 0,
}


def load_config():
    cfg = DEFAULT_CONFIG.copy()
    try:
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def cache_write(name, data):
    try:
        (CACHE_DIR / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def cache_read(name):
    try:
        p = CACHE_DIR / f"{name}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def api_get(url, params=None, headers=None, timeout=10):
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def pfloat(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def recursive_find(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, "", "-99.0"):
                return obj[key]
        for value in obj.values():
            hit = recursive_find(value, keys)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for value in obj:
            hit = recursive_find(value, keys)
            if hit is not None:
                return hit
    return None


class T:
    BG = "#0E1014"
    SURFACE = "#171A20"
    CARD = "#1D2129"
    CARD2 = "#242A34"
    ACCENT = "#8A94FF"
    ACCENT2 = "#B1B8FF"
    TEXT = "#F5F7FB"
    MUTED = "#9AA3B5"
    SUCCESS = "#38D98A"
    DANGER = "#FF6478"
    WARNING = "#FFC857"
    BORDER = "rgba(255,255,255,0.07)"
    FONT = "Microsoft JhengHei UI"


@dataclass
class Weather:
    location: str
    temperature: float | None
    humidity: float | None
    wind: float | None
    weather: str
    rain: int | None
    high: float | None
    low: float | None
    comfort: str
    aqi: int | None
    aqi_status: str
    pm25: float | None
    updated: str
    source: str
    demo: bool = False


class WeatherWorker(QThread):
    done = Signal(object, object)
    failed = Signal(str)

    def __init__(self, city, demo):
        super().__init__()
        self.city = city
        self.demo = demo

    def run(self):
        try:
            if self.demo:
                weather = Weather(self.city, 29.0, 72, 2.1, "多雲時晴", 20, 32, 25, "舒適", 42, "良好", 12, datetime.now().strftime("%H:%M"), "DEMO", True)
                self.done.emit(weather, {"aqi": 42, "status": "良好", "pm25": 12})
                return
            if not CWA_KEY:
                cached = cache_read("weather")
                if cached:
                    self.done.emit(Weather(**cached), cache_read("aqi") or {})
                    return
                raise RuntimeError("尚未設定 CWA_API_KEY")
            headers = {"Authorization": CWA_KEY}
            obs = api_get(f"{CWA_BASE}/O-A0003-001", headers=headers, params={"format": "JSON"})
            fc = api_get(f"{CWA_BASE}/F-C0032-001", headers=headers, params={"format": "JSON", "locationName": self.city})
            stations = obs.get("records", {}).get("Station", []) or obs.get("records", {}).get("station", [])
            candidates = [s for s in stations if s.get("CountyName") == self.city or s.get("County") == self.city]
            station = next((s for s in candidates if pfloat(recursive_find(s, ["AirTemperature", "airTemperature"])) is not None), None)
            if not station:
                station = candidates[0] if candidates else None
            if not station:
                raise RuntimeError(f"找不到 {self.city} 的 CWA 觀測站")
            temp = pfloat(recursive_find(station, ["AirTemperature", "airTemperature"]))
            hum = pfloat(recursive_find(station, ["RelativeHumidity", "relativeHumidity"]))
            wind = pfloat(recursive_find(station, ["WindSpeed", "windSpeed"]))
            weather_text = recursive_find(station, ["Weather", "weather"]) or "未知"
            locs = fc.get("records", {}).get("location", []) or fc.get("records", {}).get("Location", [])
            loc = next((x for x in locs if x.get("locationName") == self.city or x.get("LocationName") == self.city), locs[0] if locs else {})
            elements = loc.get("weatherElement", []) or loc.get("WeatherElement", [])
            wx = weather_text
            rain = high = low = None
            comfort = "—"
            for e in elements:
                name = e.get("elementName") or e.get("ElementName")
                times = e.get("time", []) or e.get("Time", [])
                if not times:
                    continue
                param = times[0].get("parameter", {}) or times[0].get("Parameter", {})
                val = param.get("parameterName") or param.get("ParameterName")
                if name == "Wx": wx = val or wx
                elif name == "PoP": rain = int(float(val)) if val else None
                elif name == "MaxT": high = pfloat(val)
                elif name == "MinT": low = pfloat(val)
                elif name == "CI": comfort = val or "—"
            weather = Weather(self.city, temp, hum, wind, wx, rain, high, low, comfort, None, "—", None, datetime.now().strftime("%H:%M"), "中央氣象署 CWA")
            cache_write("weather", asdict(weather))
            self.done.emit(weather, {})
        except Exception as exc:
            cached = cache_read("weather")
            if cached:
                self.done.emit(Weather(**cached), cache_read("aqi") or {})
            else:
                self.failed.emit(str(exc))


class AQIWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, city, demo):
        super().__init__()
        self.city, self.demo = city, demo

    def run(self):
        try:
            if self.demo:
                data = {"aqi": 42, "status": "良好", "pm25": 12, "site": "Demo"}
                self.done.emit(data)
                return
            if not MOENV_KEY:
                cached = cache_read("aqi")
                if cached:
                    self.done.emit(cached)
                    return
                raise RuntimeError("尚未設定 MOENV_API_KEY")
            data = api_get(MOENV_URL, params={"api_key": MOENV_KEY, "format": "json", "offset": 0, "limit": 1000})
            rows = data.get("records", [])
            candidates = [r for r in rows if r.get("County") == self.city]
            row = next((r for r in candidates if str(r.get("AQI", "")).strip().isdigit()), None)
            if not row:
                raise RuntimeError(f"找不到 {self.city} 的 AQI 測站")
            result = {"aqi": int(row["AQI"]), "status": row.get("Status", ""), "pm25": pfloat(row.get("PM2.5")), "site": row.get("SiteName", "")}
            cache_write("aqi", result)
            self.done.emit(result)
        except Exception as exc:
            cached = cache_read("aqi")
            if cached:
                self.done.emit(cached)
            else:
                self.failed.emit(str(exc))


class RSSWorker(QThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, feed_url, demo=False):
        super().__init__()
        self.feed_url, self.demo = feed_url, demo

    def run(self):
        if self.demo:
            self.done.emit([
                {"title": "AI 與科技產業最新消息（Demo）", "source": "Desktop Pet", "time": "現在", "url": "https://news.google.com/"},
                {"title": "台灣今日焦點新聞（Demo）", "source": "Desktop Pet", "time": "今天", "url": "https://news.google.com/"},
                {"title": "生活娛樂焦點（Demo）", "source": "Desktop Pet", "time": "今天", "url": "https://news.google.com/"},
            ])
            return
        try:
            feed = feedparser.parse(self.feed_url)
            items = []
            for entry in feed.entries[:12]:
                items.append({
                    "title": entry.get("title", "無標題"),
                    "source": entry.get("source", {}).get("title", "Google News"),
                    "time": entry.get("published", entry.get("updated", "")),
                    "url": entry.get("link", "https://news.google.com/"),
                })
            if not items:
                raise RuntimeError("RSS 沒有回傳新聞")
            self.done.emit(items)
        except Exception as exc:
            self.failed.emit(str(exc))


class StockWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, favorites, query="", demo=False):
        super().__init__()
        self.favorites, self.query, self.demo = favorites, query.strip().lower(), demo

    def run(self):
        try:
            if self.demo:
                rows = [
                    {"Code": "2330", "Name": "台積電", "ClosingPrice": "980.0", "Change": "+12.0"},
                    {"Code": "2317", "Name": "鴻海", "ClosingPrice": "185.5", "Change": "-1.5"},
                    {"Code": "2454", "Name": "聯發科", "ClosingPrice": "1220.0", "Change": "+15.0"},
                ]
            else:
                rows = api_get(f"{TWSE_BASE}/exchangeReport/STOCK_DAY_ALL")
            def match(r):
                code = str(r.get("Code", ""))
                name = str(r.get("Name", "")).lower()
                return (not self.query) or self.query in code.lower() or self.query in name
            matches = [r for r in rows if match(r)]
            favorites = [r for r in rows if str(r.get("Code", "")) in set(self.favorites)]
            self.done.emit({"search": matches[:20], "favorites": favorites, "updated": datetime.now().strftime("%H:%M")})
        except Exception as exc:
            cached = cache_read("stocks")
            if cached:
                self.done.emit(cached)
            else:
                self.failed.emit(str(exc))


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame{{background:{T.CARD};border:1px solid {T.BORDER};border-radius:18px;}}")


class BasePage(QWidget):
    def title(self, text, sub=""):
        box = QVBoxLayout()
        label = QLabel(text)
        label.setStyleSheet(f"color:{T.TEXT};font-size:24px;font-weight:800;")
        box.addWidget(label)
        if sub:
            s = QLabel(sub)
            s.setStyleSheet(f"color:{T.MUTED};font-size:12px;")
            box.addWidget(s)
        return box


class WeatherPage(BasePage):
    def __init__(self, config):
        super().__init__(); self.config = config
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(14)
        lay.addLayout(self.title("🌤️ 今日氣象", "中央氣象署觀測＋預報 · 環境部 AQI"))
        row = QHBoxLayout(); row.setSpacing(14)
        self.main = Card(); ml = QVBoxLayout(self.main); ml.setContentsMargins(24,24,24,24)
        self.city = QLabel("臺中市"); self.city.setStyleSheet(f"color:{T.MUTED};font-size:14px;")
        self.temp = QLabel("--°C"); self.temp.setStyleSheet(f"color:{T.TEXT};font-size:54px;font-weight:900;")
        self.wx = QLabel("載入中…"); self.wx.setStyleSheet(f"color:{T.ACCENT2};font-size:18px;font-weight:700;")
        self.details = QLabel("濕度 --   風速 --\n降雨機率 --   舒適度 --\n最高 --°   最低 --°")
        self.details.setStyleSheet(f"color:{T.MUTED};font-size:13px;line-height:1.6;")
        for w in (self.city,self.temp,self.wx,self.details): ml.addWidget(w)
        self.aqi = Card(); al=QVBoxLayout(self.aqi); al.setContentsMargins(24,24,24,24)
        self.aqi_val=QLabel("--"); self.aqi_val.setStyleSheet(f"color:{T.SUCCESS};font-size:42px;font-weight:900;")
        self.aqi_status=QLabel("空氣品質 --"); self.aqi_status.setStyleSheet(f"color:{T.TEXT};font-size:16px;font-weight:700;")
        self.aqi_pm=QLabel("PM2.5 --"); self.aqi_pm.setStyleSheet(f"color:{T.MUTED};font-size:13px;")
        al.addWidget(QLabel("🌫️ 空氣品質")); al.addWidget(self.aqi_val); al.addWidget(self.aqi_status); al.addWidget(self.aqi_pm)
        row.addWidget(self.main, 3); row.addWidget(self.aqi, 2); lay.addLayout(row)
        self.updated=QLabel("等待更新…"); self.updated.setStyleSheet(f"color:{T.MUTED};font-size:11px;"); lay.addWidget(self.updated); lay.addStretch()
    def update_weather(self, w):
        self.city.setText(f"📍 {w.location}"); self.temp.setText(f"{int(w.temperature)}°C" if w.temperature is not None else "--°C")
        self.wx.setText(w.weather); self.details.setText(f"濕度 {w.humidity or '--'}%   風速 {w.wind or '--'} m/s\n降雨機率 {w.rain or '--'}%   舒適度 {w.comfort}\n最高 {w.high or '--'}°   最低 {w.low or '--'}°")
        self.updated.setText(f"資料來源：{w.source} · 更新 {w.updated}")
    def update_aqi(self,d):
        self.aqi_val.setText(str(d.get("aqi","--"))); self.aqi_status.setText(f"{d.get('status','--')} · 測站 {d.get('site','--')}"); self.aqi_pm.setText(f"PM2.5 {d.get('pm25','--')}")


class NewsPage(BasePage):
    def __init__(self, demo=False):
        super().__init__(); self.demo=demo; self.worker=None
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)
        lay.addLayout(self.title("📰 頭條新聞", "Google News RSS · 無需 GNews API Key"))
        self.tabs=QHBoxLayout()
        for name,url in RSS_FEEDS.items():
            b=QPushButton(name); b.clicked.connect(lambda _,u=url,n=name:self.load_feed(u,n)); b.setStyleSheet(f"QPushButton{{background:{T.CARD};color:{T.MUTED};padding:9px 13px;border-radius:10px;border:1px solid {T.BORDER};}} QPushButton:hover{{color:white;background:{T.ACCENT};}}")
            self.tabs.addWidget(b)
        lay.addLayout(self.tabs)
        self.list=QListWidget(); self.list.setStyleSheet(f"QListWidget{{background:transparent;border:none;}} QListWidget::item{{background:{T.CARD};margin:5px;padding:14px;border-radius:14px;}} QListWidget::item:hover{{background:{T.CARD2};}}")
        self.list.itemDoubleClicked.connect(self.open_item); lay.addWidget(self.list)
        self.load_feed(RSS_FEEDS["🔥 熱門"], "🔥 熱門")
    def load_feed(self,url,name):
        self.worker=RSSWorker(url,self.demo); self.worker.done.connect(lambda items:self.populate(items,name)); self.worker.failed.connect(lambda e:self.show_error(str(e))); self.worker.start()
    def populate(self,items,name):
        self.list.clear()
        for it in items:
            text=f"{it['title']}\n{it['source']} · {it['time']}"
            q=QListWidgetItem(text); q.setData(Qt.ItemDataRole.UserRole,it['url']); self.list.addItem(q)
    def open_item(self,item): QDesktopServices.openUrl(QUrl(item.data(Qt.ItemDataRole.UserRole)))
    def show_error(self,e): self.list.clear(); self.list.addItem(QListWidgetItem(f"⚠️ 新聞暫時無法更新\n{e}"))


class StockPage(BasePage):
    def __init__(self, config):
        super().__init__(); self.config=config; self.worker=None; self.search_results=[]
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(12)
        lay.addLayout(self.title("📈 台股", "搜尋股票、加入自選、快速查看最新市場資料"))
        search=QHBoxLayout(); self.query=QLineEdit(); self.query.setPlaceholderText("輸入股票代號或名稱，例如：2330／台積電")
        go=QPushButton("🔎 搜尋"); go.clicked.connect(self.search); self.query.returnPressed.connect(self.search); search.addWidget(self.query); search.addWidget(go); lay.addLayout(search)
        self.results=QListWidget(); self.results.setStyleSheet(f"QListWidget{{background:transparent;border:none;}} QListWidget::item{{background:{T.CARD};margin:4px;padding:12px;border-radius:12px;}}")
        self.results.itemDoubleClicked.connect(self.toggle_favorite); lay.addWidget(self.results)
        self.fav=QLabel("⭐ 自選股："+"、".join(self.config.get("favorites",[]))); self.fav.setStyleSheet(f"color:{T.MUTED};font-size:12px;"); lay.addWidget(self.fav)
    def search(self):
        self.worker=StockWorker(self.config.get("favorites",[]),self.query.text(),self.config.get("demo_mode",True)); self.worker.done.connect(self.populate); self.worker.failed.connect(lambda e:self.results.clear() or self.results.addItem(QListWidgetItem(f"⚠️ 股票資料無法取得：{e}"))); self.worker.start()
    def populate(self,d):
        self.results.clear(); self.search_results=d.get("search",[])
        rows=self.search_results if self.query.text().strip() else d.get("favorites",[])
        for r in rows:
            q=QListWidgetItem(f"{r.get('Code','')}  {r.get('Name','')}    {r.get('ClosingPrice','--')}   {r.get('Change','--')}\n雙擊加入／移除自選")
            q.setData(Qt.ItemDataRole.UserRole,r.get("Code","")); self.results.addItem(q)
    def toggle_favorite(self,item):
        code=str(item.data(Qt.ItemDataRole.UserRole)); fav=self.config.setdefault("favorites",[])
        if code in fav: fav.remove(code)
        else: fav.append(code)
        save_config(self.config); self.fav.setText("⭐ 自選股："+"、".join(fav))
        self.search()


class ReactionGame(QWidget):
    def __init__(self, config):
        super().__init__(); self.cfg=config; self.started=None; self.waiting=False; self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.ready)
        l=QVBoxLayout(self); l.setSpacing(12)
        self.info=QLabel("🎯 反應力挑戰"); self.info.setStyleSheet(f"color:{T.TEXT};font-size:24px;font-weight:800;"); l.addWidget(self.info)
        self.zone=QPushButton("開始挑戰"); self.zone.setMinimumHeight(220); self.zone.clicked.connect(self.click); l.addWidget(self.zone)
        self.best=QLabel(f"最佳：{self.cfg.get('best_reaction',9999)} ms"); l.addWidget(self.best)
        self.reset()
    def reset(self): self.waiting=False; self.started=None; self.zone.setText("開始挑戰"); self.zone.setStyleSheet(f"background:{T.CARD};color:white;font-size:24px;border-radius:18px;")
    def click(self):
        if self.started is None and not self.waiting:
            self.waiting=True; self.zone.setText("準備……不要點！"); self.timer.start(random.randint(1200,3200)); return
        if self.waiting: self.info.setText("😳 太早了！再試一次"); self.reset(); return
        elapsed=int((time.perf_counter()-self.started)*1000); self.started=None
        best=min(self.cfg.get("best_reaction",9999),elapsed); self.cfg["best_reaction"]=best; save_config(self.cfg); self.best.setText(f"最佳：{best} ms"); self.info.setText("⚡ 超快！" if elapsed<300 else "🎉 不錯！"); self.reset()
    def ready(self): self.waiting=False; self.started=time.perf_counter(); self.zone.setText("🔥 現在點！"); self.zone.setStyleSheet(f"background:{T.SUCCESS};color:white;font-size:28px;font-weight:900;border-radius:18px;")


class MemoryGame(QWidget):
    def __init__(self, config):
        super().__init__(); self.cfg=config; self.level=1; self.seq=[]; self.pos=0; self.alive=True
        l=QVBoxLayout(self); self.title=QLabel("🧠 記憶挑戰"); self.title.setStyleSheet(f"color:{T.TEXT};font-size:24px;font-weight:800;"); l.addWidget(self.title)
        self.status=QLabel("看清楚順序，全部記住！"); self.status.setStyleSheet(f"color:{T.MUTED};"); l.addWidget(self.status)
        self.grid=QGridLayout(); l.addLayout(self.grid); self.start=QPushButton("▶ 開始第 1 關"); self.start.clicked.connect(self.new_round); l.addWidget(self.start)
    def clear_grid(self):
        while self.grid.count():
            w=self.grid.takeAt(0).widget()
            if w: w.deleteLater()
    def new_round(self):
        self.clear_grid(); n=min(3+self.level,12); cols=4; self.seq=random.sample(range(n),n); self.pos=0; self.status.setText(f"Level {self.level} · 請記住 {n} 個位置")
        self.buttons=[]
        for i in range(n):
            b=QPushButton("⭐"); b.setMinimumSize(80,65); b.setProperty("index",i); b.clicked.connect(lambda checked=False,idx=i:self.pick(idx)); self.grid.addWidget(b,i//cols,i%cols); self.buttons.append(b)
        self.start.setEnabled(False)
        QTimer.singleShot(max(1000,2400-self.level*120),self.hide_all)
    def hide_all(self):
        for b in self.buttons: b.setText("❓"); b.setEnabled(True)
        self.status.setText("照剛才的順序找回來！")
    def pick(self,idx):
        if idx!=self.seq[self.pos]: self.status.setText("💥 失誤！這關重來"); self.level=max(1,self.level-1); self.start.setText(f"▶ 再試一次（Level {self.level}）"); self.start.setEnabled(True); return
        self.buttons[idx].setText("✨"); self.buttons[idx].setEnabled(False); self.pos+=1
        if self.pos>=len(self.seq): self.level+=1; best=max(self.cfg.get("best_memory",0),self.level-1); self.cfg["best_memory"]=best; save_config(self.cfg); self.status.setText(f"🎉 完美！進入 Level {self.level}"); self.start.setText(f"▶ 開始 Level {self.level}"); self.start.setEnabled(True)


class CatcherGame(QWidget):
    def __init__(self, config):
        super().__init__(); self.cfg=config; self.score=0; self.player_x=180; self.objects=[]; self.running=False; self.time_left=30
        l=QVBoxLayout(self); self.info=QLabel("🐾 星星接接樂 · 30 秒挑戰"); self.info.setStyleSheet(f"color:{T.TEXT};font-size:22px;font-weight:800;"); l.addWidget(self.info)
        self.canvas=CatcherCanvas(self); l.addWidget(self.canvas); self.start=QPushButton("▶ 開始挑戰"); self.start.clicked.connect(self.start_game); l.addWidget(self.start)
        self.tick=QTimer(self); self.tick.timeout.connect(self.step)
    def start_game(self): self.score=0; self.time_left=30; self.objects=[]; self.running=True; self.start.setEnabled(False); self.tick.start(50); self.canvas.setFocus()
    def step(self):
        if not self.running: return
        if random.random()<0.06: self.objects.append([random.randint(20,330),-20,random.choice(["⭐","💎","🍎"])])
        for o in self.objects: o[1]+=6
        self.objects=[o for o in self.objects if o[1]<260]
        px=self.canvas.player_x
        kept=[]
        for x,y,ch in self.objects:
            if 35<y<260 and abs(x-px)<32: self.score+=10; continue
            kept.append([x,y,ch])
        self.objects=kept; self.canvas.update(); self.time_left-=0.05
        self.info.setText(f"🐾 分數 {self.score}   ⏱️ {max(0,int(self.time_left))} 秒")
        if self.time_left<=0: self.end_game()
    def end_game(self): self.running=False; self.tick.stop(); self.start.setEnabled(True); best=max(self.cfg.get("best_catcher",0),self.score); self.cfg["best_catcher"]=best; save_config(self.cfg); self.info.setText(f"🎉 結束！本局 {self.score} 分 · 最高 {best} 分")


class CatcherCanvas(QFrame):
    def __init__(self, game): super().__init__(game); self.game=game; self.player_x=180; self.setMinimumHeight(300); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.setStyleSheet(f"background:{T.SURFACE};border-radius:18px;")
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Left: self.player_x=max(30,self.player_x-20)
        elif e.key()==Qt.Key.Key_Right: self.player_x=min(330,self.player_x+20)
        self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(T.SURFACE))); p.drawRoundedRect(self.rect(),18,18)
        p.setPen(QPen(QColor(T.TEXT),2)); p.drawText(self.player_x-15,275,"🐾")
        for x,y,ch in self.game.objects: p.drawText(x,y,ch)


class GamesPage(QWidget):
    def __init__(self, config):
        super().__init__(); l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(12)
        h=QLabel("🎮 無聊？不，這裡真的可以玩！"); h.setStyleSheet(f"color:{T.TEXT};font-size:24px;font-weight:900;"); l.addWidget(h)
        sub=QLabel("三款短遊戲 · 每局 30 秒～3 分鐘 · 紀錄最高分")
        sub.setStyleSheet(f"color:{T.MUTED};"); l.addWidget(sub)
        tabs=QStackedWidget(); l.addWidget(tabs)
        for page in (ReactionGame(config),MemoryGame(config),CatcherGame(config)):
            tabs.addWidget(page)
        nav=QHBoxLayout()
        for i,name in enumerate(["🎯 反應力","🧠 記憶","🐾 接星星"]):
            b=QPushButton(name); b.clicked.connect(lambda _,idx=i:tabs.setCurrentIndex(idx)); nav.addWidget(b)
        l.insertLayout(2,nav)


class SettingsPage(QWidget):
    def __init__(self, config, on_save):
        super().__init__(); self.cfg=config; self.on_save=on_save; l=QVBoxLayout(self); l.setSpacing(14)
        title=QLabel("⚙️ 設定"); title.setStyleSheet(f"color:{T.TEXT};font-size:24px;font-weight:900;"); l.addWidget(title)
        self.city=QComboBox(); self.city.addItems(CITIES); self.city.setCurrentText(config.get("city","臺中市")); l.addWidget(QLabel("氣象城市")); l.addWidget(self.city)
        self.demo=QCheckBox("使用 Demo Mode"); self.demo.setChecked(config.get("demo_mode",True)); l.addWidget(self.demo)
        self.auto=QCheckBox("Windows 登入後自動啟動"); self.auto.setChecked(config.get("autostart",True)); l.addWidget(self.auto)
        save=QPushButton("💾 儲存設定"); save.clicked.connect(self.save); l.addWidget(save); l.addStretch()
    def save(self):
        self.cfg["city"]=self.city.currentText(); self.cfg["demo_mode"]=self.demo.isChecked(); self.cfg["autostart"]=self.auto.isChecked(); save_config(self.cfg); set_autostart(self.cfg["autostart"]); self.on_save(self.cfg)


def set_autostart(enabled):
    if os.name != "nt" or win32com is None: return
    startup=Path(os.environ.get("APPDATA",""))/"Microsoft/Windows/Start Menu/Programs/Startup"
    link=startup/"DesktopPet.lnk"
    try:
        if enabled:
            exe=sys.executable if getattr(sys,"frozen",False) else os.path.abspath(sys.argv[0])
            shell=win32com.client.Dispatch("WScript.Shell")
            shortcut=shell.CreateShortCut(str(link)); shortcut.Targetpath=exe; shortcut.WorkingDirectory=os.path.dirname(exe); shortcut.save()
        elif link.exists(): link.unlink()
    except Exception: pass


class Dashboard(QMainWindow):
    def __init__(self, config):
        super().__init__(); self.cfg=config; self.setWindowTitle(APP_NAME); self.resize(980,700); self.setMinimumSize(820,600)
        self.setStyleSheet(f"QMainWindow{{background:{T.BG};}} QPushButton{{background:{T.CARD2};color:{T.TEXT};border:none;border-radius:11px;padding:9px 13px;}} QPushButton:hover{{background:{T.ACCENT};}} QLineEdit,QComboBox,QSpinBox{{background:{T.CARD};color:{T.TEXT};border:1px solid {T.BORDER};border-radius:10px;padding:9px;}}")
        central=QWidget(); root=QHBoxLayout(central); root.setContentsMargins(16,16,16,16); root.setSpacing(14); self.setCentralWidget(central)
        nav=QFrame(); nav.setFixedWidth(180); nav.setStyleSheet(f"background:{T.SURFACE};border-radius:20px;"); nl=QVBoxLayout(nav); brand=QLabel("🐾\nDesktop Pet"); brand.setAlignment(Qt.AlignmentFlag.AlignCenter); brand.setStyleSheet(f"color:{T.TEXT};font-size:22px;font-weight:900;"); nl.addWidget(brand); self.stack=QStackedWidget(); pages=[WeatherPage(config),NewsPage(config.get("demo_mode",True)),StockPage(config),GamesPage(config),SettingsPage(config,self.on_save)]
        labels=["🌤️ 天氣","📰 新聞","📈 股票","🎮 遊戲","⚙️ 設定"]
        for i,name in enumerate(labels): b=QPushButton(name); b.clicked.connect(lambda _,idx=i:self.stack.setCurrentIndex(idx)); nl.addWidget(b)
        nl.addStretch(); footer=QLabel("CWA · MOENV · RSS · TWSE"); footer.setAlignment(Qt.AlignmentFlag.AlignCenter); footer.setStyleSheet(f"color:{T.MUTED};font-size:10px;"); nl.addWidget(footer)
        root.addWidget(nav); root.addWidget(self.stack,1)
        self.weather_page,self.news_page,self.stock_page,self.games_page,self.settings_page=pages
        self.refresh_all()
    def on_save(self,cfg): self.cfg=cfg; self.refresh_all()
    def refresh_all(self):
        city=self.cfg.get("city","臺中市"); demo=self.cfg.get("demo_mode",True)
        self.ww=WeatherWorker(city,demo); self.ww.done.connect(self.weather_ready); self.ww.start()
        self.aw=AQIWorker(city,demo); self.aw.done.connect(self.aqi_ready); self.aw.start()
        self.news_page.load_feed(RSS_FEEDS["🔥 熱門"],"🔥 熱門")
        self.stock_page.search()
    def weather_ready(self,w,a): self.weather_page.update_weather(w)
    def aqi_ready(self,d): self.weather_page.update_aqi(d)


class Pet(QWidget):
    def __init__(self, config):
        super().__init__(); self.cfg=config; self.dashboard=None; self.drag=None; self.mood="🐾"; self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.resize(180,180)
        l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar=QLabel("🐾"); self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter); self.avatar.setStyleSheet("background:transparent;font-size:78px;"); l.addWidget(self.avatar)
        self.bubble=QLabel(""); self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter); self.bubble.setStyleSheet(f"background:{T.TEXT};color:#16181E;border-radius:12px;padding:7px;"); self.bubble.hide(); l.insertWidget(0,self.bubble)
        self.float_dir=1; self.float_y=0; self.float_timer=QTimer(self); self.float_timer.timeout.connect(self.float_step); self.float_timer.start(80)
        self.move_to_corner(); self.setup_menu(); set_autostart(self.cfg.get("autostart",True))
    def move_to_corner(self):
        s=QApplication.primaryScreen().availableGeometry(); self.move(s.right()-220,s.bottom()-210)
    def setup_menu(self):
        self.menu=QMenu(self); self.openAct=self.menu.addAction("🖥️ 開啟資訊"); self.headAct=self.menu.addAction("👆 摸摸頭"); self.feedAct=self.menu.addAction("🍎 餵食"); self.playAct=self.menu.addAction("🎾 陪我玩"); self.menu.addSeparator(); self.refreshAct=self.menu.addAction("🔄 更新資料"); self.quitAct=self.menu.addAction("❌ 關閉"); self.openAct.triggered.connect(self.open_dashboard); self.headAct.triggered.connect(lambda:self.react("🥰","舒服～")); self.feedAct.triggered.connect(lambda:self.react("😋","好吃！")); self.playAct.triggered.connect(lambda:self.react("🎉","來玩！")); self.refreshAct.triggered.connect(self.open_dashboard); self.quitAct.triggered.connect(QApplication.quit)
    def float_step(self):
        if not self.cfg.get("animation",True): return
        self.float_y+=self.float_dir*0.35
        if abs(self.float_y)>5:self.float_dir*=-1
        self.avatar.move(self.avatar.x(),70+int(self.float_y))
    def react(self,face,text): self.avatar.setText(face); self.show_bubble(text); QTimer.singleShot(1200,lambda:self.avatar.setText("🐾"))
    def show_bubble(self,text): self.bubble.setText(text); self.bubble.show(); QTimer.singleShot(1800,self.bubble.hide)
    def open_dashboard(self):
        if self.dashboard is None: self.dashboard=Dashboard(self.cfg)
        else: self.dashboard.raise_(); self.dashboard.activateWindow()
        self.dashboard.show(); self.dashboard.raise_(); self.dashboard.activateWindow()
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.RightButton: self.menu.exec(e.globalPosition().toPoint()); return
        if e.button()==Qt.MouseButton.LeftButton: self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft(); self.react("😊","嘿嘿～")
    def mouseMoveEvent(self,e):
        if e.buttons() & Qt.MouseButton.LeftButton and self.drag: self.move(e.globalPosition().toPoint()-self.drag)
    def mouseDoubleClickEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.react("😮","要看資訊嗎？"); self.open_dashboard()


def main():
    app=QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); cfg=load_config(); pet=Pet(cfg); pet.show()
    tray=QSystemTrayIcon(pet); tray.setIcon(app.style().standardIcon(QSystemTrayIcon.MessageIcon)); menu=QMenu(); menu.addAction("🖥️ 開啟資訊",pet.open_dashboard); menu.addAction("❌ 結束",app.quit); tray.setContextMenu(menu); tray.show()
    sys.exit(app.exec())


if __name__ == "__main__": main()
