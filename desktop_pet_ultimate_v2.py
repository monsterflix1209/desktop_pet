import os, sys, json, time, random
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus

import requests
import feedparser
from dotenv import load_dotenv
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QPoint
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QBrush, QPen
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QFrame, QComboBox, QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QGridLayout, QSystemTrayIcon, QMenu

try:
    import win32com.client
except ImportError:
    win32com = None

load_dotenv()
APP_NAME = 'Desktop Pet'
CWA_KEY = os.getenv('CWA_API_KEY','').strip()
MOENV_KEY = os.getenv('MOENV_API_KEY','').strip()
DEMO_MODE = os.getenv('DEMO_MODE','true').lower()=='true'
CWA_BASE='https://opendata.cwa.gov.tw/api/v1/rest/datastore'
MOENV_URL='https://data.moenv.gov.tw/api/v2/AQX_P_432'
TWSE_BASE='https://openapi.twse.com.tw/v1'
YAHOO_CHART='https://query1.finance.yahoo.com/v8/finance/chart/'
CONFIG_PATH=Path.home()/'.desktop_pet_config.json'
CACHE_DIR=Path.home()/'.desktop_pet_cache'; CACHE_DIR.mkdir(exist_ok=True)
CITIES=['臺北市','新北市','桃園市','臺中市','臺南市','高雄市','基隆市','新竹市','新竹縣','苗栗縣','彰化縣','南投縣','雲林縣','嘉義市','嘉義縣','屏東縣','宜蘭縣','花蓮縣','臺東縣','澎湖縣','金門縣','連江縣']
DEFAULT={'city':'臺中市','favorites':['0050'],'theme':'dark','animation':True,'sound':True,'autostart':True,'demo_mode':DEMO_MODE,'best_reaction':9999,'best_memory':0,'best_catcher':0}
RSS_FEEDS={
'🔥 熱門':'https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
'🇹🇼 國內':'https://news.google.com/rss/search?q='+quote_plus('台灣')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
'💻 科技':'https://news.google.com/rss/search?q='+quote_plus('科技 OR AI OR 人工智慧')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
'📈 財經':'https://news.google.com/rss/search?q='+quote_plus('台股 OR 股市 OR 財經')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
'🎬 娛樂':'https://news.google.com/rss/search?q='+quote_plus('娛樂 OR 電影 OR 音樂')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'}
# Default market watchlist: TAIEX plus four major US names.
DEFAULT_MARKETS=[('TAIEX','加權指數','^TWII'),('AAPL','Apple','AAPL'),('MSFT','Microsoft','MSFT'),('NVDA','NVIDIA','NVDA'),('TSLA','Tesla','TSLA')]

def cfg_load():
    c=DEFAULT.copy()
    try:
        if CONFIG_PATH.exists(): c.update(json.loads(CONFIG_PATH.read_text(encoding='utf-8')))
    except Exception: pass
    return c

def cfg_save(c):
    try: CONFIG_PATH.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception: pass

def cache_write(name,data):
    try: (CACHE_DIR/f'{name}.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    except Exception: pass

def cache_read(name):
    try:
        p=CACHE_DIR/f'{name}.json'
        if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
    except Exception: pass
    return None

def get_json(url,params=None,headers=None,timeout=10):
    r=requests.get(url,params=params,headers=headers,timeout=timeout); r.raise_for_status(); return r.json()

def pfloat(v):
    try: return float(v)
    except: return None

def recursive_find(obj,keys):
    if isinstance(obj,dict):
        for k in keys:
            if k in obj and obj[k] not in (None,'','-99.0'): return obj[k]
        for v in obj.values():
            x=recursive_find(v,keys)
            if x is not None:return x
    elif isinstance(obj,list):
        for v in obj:
            x=recursive_find(v,keys)
            if x is not None:return x
    return None

class Theme:
    BG='#0B0D12'; SURFACE='#12151C'; CARD='#181D26'; CARD2='#222938'; ACCENT='#8D98FF'; ACCENT2='#C1C7FF'; TEXT='#F7F8FC'; MUTED='#98A2B5'; SUCCESS='#42D392'; DANGER='#FF667D'; WARNING='#FFC857'; BORDER='rgba(255,255,255,0.08)'

def style_widget(w):
    w.setStyleSheet(f'QWidget{{font-family:"Microsoft JhengHei UI";}} QPushButton{{background:{Theme.CARD2};color:{Theme.TEXT};border:none;border-radius:10px;padding:10px 14px;}} QPushButton:hover{{background:{Theme.ACCENT};}} QLineEdit,QComboBox{{background:{Theme.CARD};color:{Theme.TEXT};border:1px solid {Theme.BORDER};border-radius:10px;padding:10px;}}')

class Card(QFrame):
    def __init__(self):
        super().__init__(); self.setStyleSheet(f'QFrame{{background:{Theme.CARD};border:1px solid {Theme.BORDER};border-radius:18px;}}')

class Worker(QThread):
    done=Signal(object); failed=Signal(str)
    def __init__(self,fn): super().__init__(); self.fn=fn
    def run(self):
        try:self.done.emit(self.fn())
        except Exception as e:self.failed.emit(str(e))

class WeatherPage(QWidget):
    def __init__(self,cfg):
        super().__init__(); style_widget(self); self.cfg=cfg; self.workers=[]
        l=QVBoxLayout(self); l.setSpacing(14)
        h=QLabel('🌤️ 今日氣象'); h.setStyleSheet(f'color:{Theme.TEXT};font-size:28px;font-weight:900;'); l.addWidget(h)
        s=QLabel('中央氣象署 CWA 觀測＋36 小時預報 · 環境部 AQI'); s.setStyleSheet(f'color:{Theme.MUTED};'); l.addWidget(s)
        row=QHBoxLayout(); row.setSpacing(14)
        self.current=Card(); cl=QVBoxLayout(self.current); cl.setContentsMargins(24,24,24,24)
        self.city=QLabel(cfg['city']); self.city.setStyleSheet(f'color:{Theme.MUTED};font-size:14px')
        self.temp=QLabel('--°'); self.temp.setStyleSheet(f'color:{Theme.TEXT};font-size:56px;font-weight:900')
        self.wx=QLabel('載入中…'); self.wx.setStyleSheet(f'color:{Theme.ACCENT2};font-size:18px;font-weight:700')
        self.details=QLabel('濕度 --\n風速 --\n降雨機率 --\n最高 -- / 最低 --'); self.details.setStyleSheet(f'color:{Theme.MUTED};font-size:13px')
        for w in [self.city,self.temp,self.wx,self.details]: cl.addWidget(w)
        self.aqi=Card(); al=QVBoxLayout(self.aqi); al.setContentsMargins(24,24,24,24)
        q=QLabel('🌫️ 空氣品質'); q.setStyleSheet(f'color:{Theme.TEXT};font-size:16px;font-weight:800')
        self.aqiv=QLabel('--'); self.aqiv.setStyleSheet(f'color:{Theme.SUCCESS};font-size:44px;font-weight:900')
        self.aqis=QLabel('AQI --'); self.aqip=QLabel('PM2.5 --'); self.aqis.setStyleSheet(f'color:{Theme.TEXT};font-weight:700'); self.aqip.setStyleSheet(f'color:{Theme.MUTED};')
        for w in [q,self.aqiv,self.aqis,self.aqip]: al.addWidget(w)
        row.addWidget(self.current,3); row.addWidget(self.aqi,2); l.addLayout(row)
        self.updated=QLabel('資料載入中…'); self.updated.setStyleSheet(f'color:{Theme.MUTED};font-size:11px'); l.addWidget(self.updated); l.addStretch()
        self.refresh()
    def refresh(self):
        self._start(lambda:self.fetch_weather(),'weather',self.weather_ok)
        self._start(lambda:self.fetch_aqi(),'aqi',self.aqi_ok)
    def _start(self,fn,name,slot):
        w=Worker(fn); self.workers.append(w); w.finished.connect(lambda:self._cleanup(w)); w.done.connect(slot); w.failed.connect(lambda e:self._error(name,e)); w.start()
    def _cleanup(self,w):
        try:self.workers.remove(w)
        except ValueError:pass
        w.deleteLater()
    def fetch_weather(self):
        if self.cfg.get('demo_mode',True): return {'city':self.cfg['city'],'temp':29,'humidity':72,'wind':2.1,'wx':'多雲時晴','rain':20,'high':32,'low':25,'updated':datetime.now().strftime('%H:%M'),'source':'DEMO'}
        if not CWA_KEY: raise RuntimeError('未設定 CWA_API_KEY')
        headers={'Authorization':CWA_KEY}; obs=get_json(f'{CWA_BASE}/O-A0003-001',headers=headers,params={'format':'JSON'}); fc=get_json(f'{CWA_BASE}/F-C0032-001',headers=headers,params={'format':'JSON','locationName':self.cfg['city']})
        stations=obs.get('records',{}).get('Station',[]) or obs.get('records',{}).get('station',[]); cs=[x for x in stations if x.get('CountyName')==self.cfg['city'] or x.get('County')==self.cfg['city']]; st=next((x for x in cs if pfloat(recursive_find(x,['AirTemperature','airTemperature'])) is not None),None) or (cs[0] if cs else None)
        if not st: raise RuntimeError('找不到城市觀測站')
        temp=pfloat(recursive_find(st,['AirTemperature','airTemperature'])); hum=pfloat(recursive_find(st,['RelativeHumidity','relativeHumidity'])); wind=pfloat(recursive_find(st,['WindSpeed','windSpeed'])); wx=recursive_find(st,['Weather','weather']) or '未知'
        locs=fc.get('records',{}).get('location',[]) or fc.get('records',{}).get('Location',[]); loc=next((x for x in locs if x.get('locationName')==self.cfg['city'] or x.get('LocationName')==self.cfg['city']),{})
        es=loc.get('weatherElement',[]) or loc.get('WeatherElement',[]); rain=high=low=None
        for e in es:
            n=e.get('elementName') or e.get('ElementName'); ts=e.get('time',[]) or e.get('Time',[]); p=(ts[0].get('parameter',{}) or ts[0].get('Parameter',{})) if ts else {}; v=p.get('parameterName') or p.get('ParameterName')
            if n=='Wx':wx=v or wx
            elif n=='PoP':rain=int(float(v)) if v else None
            elif n=='MaxT':high=pfloat(v)
            elif n=='MinT':low=pfloat(v)
        return {'city':self.cfg['city'],'temp':temp,'humidity':hum,'wind':wind,'wx':wx,'rain':rain,'high':high,'low':low,'updated':datetime.now().strftime('%H:%M'),'source':'CWA'}
    def fetch_aqi(self):
        if self.cfg.get('demo_mode',True): return {'aqi':42,'status':'良好','pm25':12,'site':'Demo'}
        if not MOENV_KEY: raise RuntimeError('未設定 MOENV_API_KEY')
        d=get_json(MOENV_URL,params={'api_key':MOENV_KEY,'format':'json','offset':0,'limit':1000}); rows=[x for x in d.get('records',[]) if x.get('County')==self.cfg['city']]; r=next((x for x in rows if str(x.get('AQI','')).isdigit()),None)
        if not r: raise RuntimeError('找不到 AQI 測站')
        return {'aqi':int(r['AQI']),'status':r.get('Status',''),'pm25':pfloat(r.get('PM2.5')),'site':r.get('SiteName','')}
    def weather_ok(self,d): self.city.setText('📍 '+d['city']); self.temp.setText('--°' if d['temp'] is None else f"{d['temp']:.0f}°C"); self.wx.setText(d['wx']); self.details.setText(f"濕度 {d['humidity'] if d['humidity'] is not None else '--'}%\n風速 {d['wind'] if d['wind'] is not None else '--'} m/s\n降雨機率 {d['rain'] if d['rain'] is not None else '--'}%\n最高 {d['high'] if d['high'] is not None else '--'}° / 最低 {d['low'] if d['low'] is not None else '--'}°"); self.updated.setText(f"資料來源：{d['source']} · {d['updated']}")
    def aqi_ok(self,d): self.aqiv.setText(str(d.get('aqi','--'))); self.aqis.setText(f"{d.get('status','--')} · {d.get('site','--')}"); self.aqip.setText(f"PM2.5 {d.get('pm25','--')}")
    def _error(self,n,e): self.updated.setText(f'{n}：暫時無法更新 · {e}')

class NewsPage(QWidget):
    def __init__(self,cfg):
        super().__init__(); style_widget(self); self.cfg=cfg; self.workers=[]; l=QVBoxLayout(self); l.setSpacing(12)
        h=QLabel('📰 頭條新聞'); h.setStyleSheet(f'color:{Theme.TEXT};font-size:28px;font-weight:900'); l.addWidget(h)
        s=QLabel('Google News RSS · 不需要 GNews API Key'); s.setStyleSheet(f'color:{Theme.MUTED};'); l.addWidget(s)
        nav=QHBoxLayout()
        for name,url in RSS_FEEDS.items():
            b=QPushButton(name); b.clicked.connect(lambda _,u=url,n=name:self.load(u,n)); nav.addWidget(b)
        l.addLayout(nav)
        self.list=QListWidget(); self.list.setStyleSheet(f'QListWidget{{background:transparent;border:none;}} QListWidget::item{{background:{Theme.CARD};margin:4px;padding:14px;border-radius:14px;color:{Theme.TEXT};}}'); self.list.itemDoubleClicked.connect(lambda it: QDesktopServices.openUrl(QUrl(it.data(Qt.ItemDataRole.UserRole)))); l.addWidget(self.list); self.load(RSS_FEEDS['🔥 熱門'],'🔥 熱門')
    def load(self,url,name):
        w=Worker(lambda:self.fetch(url)); self.workers.append(w); w.finished.connect(lambda:self._done(w)); w.done.connect(lambda items:self.populate(items,name)); w.failed.connect(self.error); w.start()
    def _done(self,w):
        try:self.workers.remove(w)
        except ValueError:pass
        w.deleteLater()
    def fetch(self,url):
        f=feedparser.parse(url); items=[]
        for e in f.entries[:12]: items.append({'title':e.get('title','無標題'),'source':(e.get('source') or {}).get('title','Google News'),'time':e.get('published',e.get('updated','')),'url':e.get('link','https://news.google.com/')})
        if not items: raise RuntimeError('RSS 沒有新聞資料')
        return items
    def populate(self,items,name): self.list.clear(); [self._add(x) for x in items]
    def _add(self,x):
        it=QListWidgetItem(f"{x['title']}\n{x['source']} · {x['time']}"); it.setData(Qt.ItemDataRole.UserRole,x['url']); self.list.addItem(it)
    def error(self,e): self.list.clear(); self.list.addItem(QListWidgetItem(f'⚠️ 新聞暫時無法更新\n{e}'))

class StockPage(QWidget):
    def __init__(self,cfg):
        super().__init__(); style_widget(self); self.cfg=cfg; self.worker=None; self.chart_data={}; l=QVBoxLayout(self); l.setSpacing(12)
        h=QLabel('📈 市場'); h.setStyleSheet(f'color:{Theme.TEXT};font-size:28px;font-weight:900'); l.addWidget(h); s=QLabel('預設：加權指數＋AAPL／MSFT／NVDA／TSLA；也可以搜尋 0050 等台股'); s.setStyleSheet(f'color:{Theme.MUTED};'); l.addWidget(s)
        bar=QHBoxLayout(); self.query=QLineEdit(); self.query.setPlaceholderText('輸入股票代號或名稱，例如 0050、台積電'); go=QPushButton('🔎 搜尋'); go.clicked.connect(self.search); self.query.returnPressed.connect(self.search); bar.addWidget(self.query); bar.addWidget(go); l.addLayout(bar)
        self.list=QListWidget(); self.list.setStyleSheet(f'QListWidget{{background:transparent;border:none;}} QListWidget::item{{background:{Theme.CARD};margin:4px;padding:13px;border-radius:14px;color:{Theme.TEXT};}}'); self.list.itemDoubleClicked.connect(self.toggle_fav); l.addWidget(self.list)
        self.chart=ChartWidget(); self.chart.setMinimumHeight(220); l.addWidget(self.chart)
        f=QLabel('雙擊股票：加入／移除自選。點選股票後載入 1 個月走勢圖。'); f.setStyleSheet(f'color:{Theme.MUTED};font-size:11px'); l.addWidget(f); self.search()
    def search(self):
        q=self.query.text().strip().lower(); demo=self.cfg.get('demo_mode',True); self.worker=Worker(lambda:self.fetch_stocks(q,demo)); self.worker.finished.connect(lambda:self.cleanup()); self.worker.done.connect(self.show); self.worker.failed.connect(self.error); self.worker.start()
    def cleanup(self):
        if self.worker:self.worker.deleteLater(); self.worker=None
    def fetch_stocks(self,q,demo):
        if demo: rows=[{'Code':c,'Name':n,'ClosingPrice':str(random.randint(100,1000)),'Change':'+1.2'} for c,n,_ in [('0050','元大台灣50','0050'),('2330','台積電','2330'),('2317','鴻海','2317')]]
        else: rows=get_json(f'{TWSE_BASE}/exchangeReport/STOCK_DAY_ALL')
        return [r for r in rows if (not q or q in str(r.get('Code','')).lower() or q in str(r.get('Name','')).lower())][:20]
    def show(self,rows):
        self.list.clear(); self.rows=rows
        if not rows and not self.query.text(): rows=[{'Code':c,'Name':n,'ClosingPrice':'--','Change':'--'} for c,n,_ in DEFAULT_MARKETS]
        for r in rows:
            it=QListWidgetItem(f"{r.get('Code','')}  {r.get('Name','')}   {r.get('ClosingPrice','--')}   {r.get('Change','--')}\n雙擊加入／移除自選 · 點一下看走勢"); it.setData(Qt.ItemDataRole.UserRole,r.get('Code','')); self.list.addItem(it)
        if rows:
            self.load_chart(rows[0].get('Code',''))
    def toggle_fav(self,it):
        code=str(it.data(Qt.ItemDataRole.UserRole)); fav=self.cfg.setdefault('favorites',[]); fav.remove(code) if code in fav else fav.append(code); cfg_save(self.cfg)
    def load_chart(self,code):
        symbol='^TWII' if code in ('TAIEX','加權指數') else (code+'.TW' if code.isdigit() else code)
        if self.cfg.get('demo_mode',True):
            pts=[100+i*random.uniform(-2,3) for i in range(30)]; self.chart.set_points(pts,code); return
        w=Worker(lambda:self.fetch_chart(symbol)); w.done.connect(lambda pts:self.chart.set_points(pts,code)); w.start(); self.chart_worker=w
    def fetch_chart(self,symbol):
        d=get_json(YAHOO_CHART+symbol,params={'range':'1mo','interval':'1d'}); return [p for p in d['chart']['result'][0]['indicators']['quote'][0].get('close',[]) if p is not None]
    def error(self,e): self.list.clear(); self.list.addItem(QListWidgetItem(f'⚠️ 股票資料無法取得\n{e}'))

class ChartWidget(QFrame):
    def __init__(self): super().__init__(); self.points=[]; self.setStyleSheet(f'background:{Theme.SURFACE};border-radius:18px;')
    def set_points(self,pts,label=''): self.points=pts or []; self.label=label; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setBrush(QBrush(QColor(Theme.SURFACE))); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(self.rect(),18,18)
        if not self.points:return
        mn,mx=min(self.points),max(self.points); span=max(mx-mn,0.01); w=max(1,self.width()-40); h=max(1,self.height()-55); pen=QPen(QColor(Theme.ACCENT),3); p.setPen(pen); last=None
        for i,v in enumerate(self.points):
            x=20+i*w/max(1,len(self.points)-1); y=20+(mx-v)/span*h; cur=QPoint(int(x),int(y));
            if last:p.drawLine(last,cur)
            last=cur
        p.setPen(QPen(QColor(Theme.TEXT),1)); p.drawText(20,self.height()-15,f'{self.label} · 1M 走勢')

class GamesPage(QWidget):
    def __init__(self,cfg):
        super().__init__(); style_widget(self); l=QVBoxLayout(self); h=QLabel('🎮 無聊？來一場！'); h.setStyleSheet(f'color:{Theme.TEXT};font-size:28px;font-weight:900'); l.addWidget(h); s=QLabel('短局、快速、越玩越難'); s.setStyleSheet(f'color:{Theme.MUTED};'); l.addWidget(s); self.stack=QStackedWidget(); l.addWidget(self.stack); nav=QHBoxLayout(); [nav.addWidget(self._btn(n,i)) for i,n in enumerate(['🐍 貪食蛇','🧠 記憶大逃殺','🏃 無限跑酷'])]; l.insertLayout(2,nav); self.stack.addWidget(SnakeGame(cfg)); self.stack.addWidget(MemoryGame(cfg)); self.stack.addWidget(RunnerGame(cfg))
    def _btn(self,n,i): b=QPushButton(n); b.clicked.connect(lambda:self.stack.setCurrentIndex(i)); return b

class SnakeGame(QFrame):
    def __init__(self,cfg):
        super().__init__(); self.cfg=cfg; self.setStyleSheet(f'background:{Theme.SURFACE};border-radius:18px;'); l=QVBoxLayout(self); self.info=QLabel('🐍 末日版蛇蛇：吃能量、避開紅色障礙！'); self.info.setStyleSheet(f'color:{Theme.TEXT};font-weight:800;font-size:18px'); l.addWidget(self.info); self.btn=QPushButton('▶ 開始'); self.btn.clicked.connect(self.start); l.addWidget(self.btn); self.area=SnakeCanvas(self); l.addWidget(self.area); self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.reset()
    def reset(self): self.snake=[(5,5),(4,5),(3,5)]; self.dir=(1,0); self.food=(8,5); self.running=False
    def start(self): self.reset(); self.running=True; self.timer.start(120); self.area.setFocus(); self.btn.setText('重新開始')
    def tick(self):
        if not self.running:return
        hx,hy=self.snake[0]; nx,ny=hx+self.dir[0],hy+self.dir[1]
        if not(0<=nx<20 and 0<=ny<12) or (nx,ny) in self.snake: self.running=False; self.timer.stop(); self.info.setText('💥 GAME OVER！'); return
        self.snake.insert(0,(nx,ny));
        if (nx,ny)==self.food:self.food=(random.randrange(20),random.randrange(12)); self.info.setText(f'🐍 長度 {len(self.snake)} · 繼續！')
        else:self.snake.pop()
        self.area.update()

class SnakeCanvas(QFrame):
    def __init__(self,g): super().__init__(g); self.g=g; self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def keyPressEvent(self,e):
        m={Qt.Key.Key_Left:(-1,0),Qt.Key.Key_Right:(1,0),Qt.Key.Key_Up:(0,-1),Qt.Key.Key_Down:(0,1)}; n=m.get(e.key());
        if n and n!=( -self.g.dir[0],-self.g.dir[1]): self.g.dir=n
    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(Theme.SURFACE)); sx=self.width()/20; sy=self.height()/12
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(Theme.ACCENT))); [p.drawRoundedRect(int(x*sx+2),int(y*sy+2),int(sx-4),int(sy-4),5,5) for x,y in self.g.snake]; p.setBrush(QBrush(QColor(Theme.DANGER))); fx,fy=self.g.food; p.drawEllipse(int(fx*sx+4),int(fy*sy+4),int(sx-8),int(sy-8))

class MemoryGame(QFrame):
    def __init__(self,cfg):
        super().__init__(); self.cfg=cfg; self.level=1; self.life=3; self.seq=[]; self.pos=0; l=QVBoxLayout(self); self.info=QLabel('🧠 記憶大逃殺：看順序、拼速度、連續過關！'); self.info.setStyleSheet(f'color:{Theme.TEXT};font-size:18px;font-weight:800'); l.addWidget(self.info); self.grid=QGridLayout(); l.addLayout(self.grid); b=QPushButton('▶ 開始／下一關'); b.clicked.connect(self.new_round); l.addWidget(b); self.restart=b; self.new_round()
    def new_round(self):
        while self.grid.count():
            w=self.grid.takeAt(0).widget(); w.deleteLater() if w else None
        n=min(4+self.level,16); self.seq=random.sample(range(n),n); self.pos=0; self.buttons=[]
        for i in range(n):
            b=QPushButton(str(i+1)); b.setMinimumSize(70,55); b.clicked.connect(lambda _,x=i:self.pick(x)); self.grid.addWidget(b,i//4,i%4); self.buttons.append(b)
        self.restart.setEnabled(False); self.info.setText(f'Level {self.level} · 生命 ❤️×{self.life} · 記住順序！'); QTimer.singleShot(max(900,2200-self.level*80),self.hide)
    def hide(self):
        for b in self.buttons:b.setText('❓'); b.setEnabled(True)
        self.info.setText(f'Level {self.level} · 請照剛才順序找回！')
    def pick(self,x):
        if x!=self.seq[self.pos]:
            self.life-=1
            if self.life<=0:self.level=1; self.life=3; self.info.setText('💀 淘汰！重新開始'); self.restart.setEnabled(True); return
            self.info.setText(f'💥 錯了！剩餘生命 ❤️×{self.life}'); return
        self.buttons[x].setText('✨'); self.buttons[x].setEnabled(False); self.pos+=1
        if self.pos==len(self.seq): self.level+=1; self.info.setText(f'🔥 Combo！Level {self.level}'); self.restart.setEnabled(True)

class RunnerGame(QFrame):
    def __init__(self,cfg):
        super().__init__(); l=QVBoxLayout(self); self.info=QLabel('🏃 無限跑酷：← → 移動，跳過障礙！'); self.info.setStyleSheet(f'color:{Theme.TEXT};font-size:18px;font-weight:800'); l.addWidget(self.info); b=QPushButton('▶ 開始'); b.clicked.connect(self.start); l.addWidget(b); self.area=RunnerCanvas(self); l.addWidget(self.area); self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.running=False
    def start(self): self.area.reset(); self.running=True; self.timer.start(55); self.area.setFocus()
    def tick(self):
        if not self.running:return
        self.area.step(); self.info.setText(f'🏃 距離 {self.area.score} · 速度 {self.area.speed}');
        if self.area.dead:self.running=False; self.timer.stop(); self.info.setText(f'💥 撞到了！距離 {self.area.score}')

class RunnerCanvas(QFrame):
    def __init__(self,g): super().__init__(g); self.g=g; self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.reset()
    def reset(self): self.x=2; self.obs=[]; self.score=0; self.speed=7; self.dead=False
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Left:self.x=max(0,self.x-1)
        elif e.key()==Qt.Key.Key_Right:self.x=min(9,self.x+1)
        elif e.key()==Qt.Key.Key_Space:self.obs=[(x,y-2) for x,y in self.obs]
    def step(self):
        self.obs=[(x,y+self.speed*.04) for x,y in self.obs];
        if random.random()<0.04:self.obs.append((random.randrange(10),0))
        self.obs=[o for o in self.obs if o[1]<10]; self.score+=1; self.speed=7+min(10,self.score//200)
        for x,y in self.obs:
            if x==self.x and y>8.5:self.dead=True
        self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor(Theme.SURFACE)); sx=self.width()/10; p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(Theme.ACCENT))); p.drawRoundedRect(int(self.x*sx+8),self.height()-48,int(sx-16),32,8,8); p.setBrush(QBrush(QColor(Theme.DANGER)));
        for x,y in self.obs:p.drawRect(int(x*sx+10),int(y*(self.height()/10)),int(sx-20),25)

class SettingsPage(QWidget):
    def __init__(self,cfg,on_save):
        super().__init__(); style_widget(self); self.cfg=cfg; self.on_save=on_save; l=QVBoxLayout(self); h=QLabel('⚙️ 設定'); h.setStyleSheet(f'color:{Theme.TEXT};font-size:28px;font-weight:900'); l.addWidget(h); l.addWidget(QLabel('氣象城市')); self.city=QComboBox(); self.city.addItems(CITIES); self.city.setCurrentText(cfg['city']); l.addWidget(self.city); self.demo=QCheckBox('使用 Demo Mode'); self.demo.setChecked(cfg.get('demo_mode',True)); l.addWidget(self.demo); self.auto=QCheckBox('Windows 登入後自動啟動'); self.auto.setChecked(cfg.get('autostart',True)); l.addWidget(self.auto); b=QPushButton('💾 儲存設定'); b.clicked.connect(self.save); l.addWidget(b); l.addStretch()
    def save(self): self.cfg['city']=self.city.currentText(); self.cfg['demo_mode']=self.demo.isChecked(); self.cfg['autostart']=self.auto.isChecked(); cfg_save(self.cfg); self.on_save(self.cfg)

class Dashboard(QMainWindow):
    def __init__(self,cfg):
        super().__init__(); style_widget(self); self.cfg=cfg; self.resize(1020,720); self.setMinimumSize(850,600); self.setStyleSheet(f'QMainWindow{{background:{Theme.BG};}}')
        root=QWidget(); self.setCentralWidget(root); r=QHBoxLayout(root); r.setContentsMargins(16,16,16,16); r.setSpacing(16); nav=QFrame(); nav.setFixedWidth(190); nav.setStyleSheet(f'background:{Theme.SURFACE};border-radius:20px;'); nl=QVBoxLayout(nav); brand=QLabel('🐾\nDesktop Pet'); brand.setAlignment(Qt.AlignmentFlag.AlignCenter); brand.setStyleSheet(f'color:{Theme.TEXT};font-size:22px;font-weight:900'); nl.addWidget(brand); self.stack=QStackedWidget(); self.pages=[WeatherPage(cfg),NewsPage(cfg),StockPage(cfg),GamesPage(cfg),SettingsPage(cfg,self.saved)]
        for p in self.pages:self.stack.addWidget(p)
        for i,n in enumerate(['🌤️ 天氣','📰 新聞','📈 市場','🎮 遊戲','⚙️ 設定']):
            b=QPushButton(n); b.clicked.connect(lambda _,x=i:self.stack.setCurrentIndex(x)); nl.addWidget(b)
        nl.addStretch(); nl.addWidget(QLabel('CWA · MOENV · RSS · TWSE')); r.addWidget(nav); r.addWidget(self.stack,1)
    def saved(self,cfg): self.cfg=cfg; self.pages[0].refresh()

class Pet(QWidget):
    def __init__(self,cfg):
        super().__init__(); style_widget(self); self.cfg=cfg; self.dashboard=None; self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.resize(180,160); l=QVBoxLayout(self); l.setContentsMargins(5,5,5,5); self.bubble=QLabel(''); self.bubble.hide(); self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter); self.avatar=QLabel('🐾'); self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter); self.avatar.setStyleSheet(f'background:{Theme.CARD};border-radius:80px;font-size:72px;padding:10px'); l.addWidget(self.bubble); l.addWidget(self.avatar); self.timer=QTimer(self); self.timer.timeout.connect(self.anim); self.timer.start(120); self.dir=1; self.float=0
    def anim(self):
        if not self.cfg.get('animation',True):return
        self.float+=self.dir
        if abs(self.float)>4:self.dir*=-1
        self.avatar.move(self.avatar.x(),self.avatar.y()+self.dir)
    def open_dashboard(self):
        if self.dashboard is None:self.dashboard=Dashboard(self.cfg)
        self.dashboard.show(); self.dashboard.raise_(); self.dashboard.activateWindow()
    def mouseDoubleClickEvent(self,e): self.open_dashboard()
    def contextMenuEvent(self,e):
        m=QMenu(self); m.addAction('🖥️ 開啟資訊',self.open_dashboard); m.addAction('👆 摸摸頭',lambda:self.react('🥰','舒服～')); m.addAction('🍎 餵食',lambda:self.react('😋','好吃！')); m.addAction('🎾 陪我玩',lambda:self.react('🎉','來玩！')); m.addSeparator(); m.addAction('❌ 關閉',QApplication.quit); m.exec(e.globalPos())
    def react(self,face,text): self.avatar.setText(face); self.bubble.setText(text); self.bubble.show(); QTimer.singleShot(1500,self.bubble.hide); QTimer.singleShot(1500,lambda:self.avatar.setText('🐾'))

def main():
    app=QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); cfg=cfg_load(); pet=Pet(cfg); pet.move(1500,750); pet.show(); tray=QSystemTrayIcon(pet); tray.setIcon(app.style().standardIcon(QSystemTrayIcon.MessageIcon)); menu=QMenu(); menu.addAction('🖥️ 開啟資訊',pet.open_dashboard); menu.addAction('❌ 結束',app.quit); tray.setContextMenu(menu); tray.show(); sys.exit(app.exec())

if __name__=='__main__':main()
