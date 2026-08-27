import os,sys,json,random,math
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus
import requests,feedparser
from dotenv import load_dotenv
from PySide6.QtCore import Qt,QTimer,QUrl,QThread,Signal
from PySide6.QtGui import QColor,QPainter,QBrush,QPen,QPixmap,QLinearGradient
from PySide6.QtWidgets import QApplication,QWidget,QMainWindow,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QFrame,QStackedWidget,QListWidget,QListWidgetItem,QLineEdit,QComboBox,QCheckBox,QSystemTrayIcon,QMenu,QMessageBox
load_dotenv()
APP='Desktop Pet'; HOME=Path.home(); CFG=HOME/'.desktop_pet_config.json'; CACHE=HOME/'.desktop_pet_cache'; CACHE.mkdir(exist_ok=True)
CWA=os.getenv('CWA_API_KEY','').strip(); MOENV=os.getenv('MOENV_API_KEY','').strip(); DEMO=os.getenv('DEMO_MODE','true').lower()=='true'
RSS={'🔥 熱門':'https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant','🇹🇼 國內':'https://news.google.com/rss/search?q='+quote_plus('台灣')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant','💻 科技':'https://news.google.com/rss/search?q='+quote_plus('科技 OR AI')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant','📈 財經':'https://news.google.com/rss/search?q='+quote_plus('台股 OR 財經')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant','🎬 娛樂':'https://news.google.com/rss/search?q='+quote_plus('娛樂 OR 電影 OR 音樂')+'&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'}
def load():
 c={'city':'臺中市','theme':'Monochrome','demo':DEMO,'autostart':True}
 try:c.update(json.loads(CFG.read_text(encoding='utf8')))
 except:pass
 return c
def save(c):
 try:CFG.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf8')
 except:pass
class W(QThread):
 done=Signal(object); fail=Signal(str)
 def __init__(self,fn):super().__init__();self.fn=fn
 def run(self):
  try:self.done.emit(self.fn())
  except Exception as e:self.fail.emit(str(e))
class Glass(QFrame):
 def __init__(self,a=48,r=30):
  super().__init__();self.setStyleSheet(f'QFrame{{background:rgba(255,255,255,{a}%);border:1px solid rgba(255,255,255,48%);border-radius:{r}px;}}')
class Btn(QPushButton):
 def __init__(self,t):
  super().__init__(t);self.setCursor(Qt.PointingHandCursor);self.setStyleSheet('QPushButton{background:rgba(255,255,255,50%);color:white;border:1px solid rgba(255,255,255,55%);border-radius:18px;padding:12px 16px;font-weight:800}QPushButton:hover{background:rgba(255,255,255,75%);color:#111}QPushButton:pressed{background:white;color:#111}')
class Dashboard(QMainWindow):
 def __init__(self,cfg):
  super().__init__();self.cfg=cfg;self.resize(1180,790);self.setMinimumSize(980,680);self.setWindowFlags(Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground);self.work=[];self.drag=None
  self.root=QWidget();self.root.setObjectName('root');self.root.setStyleSheet('#root{border:1px solid rgba(255,255,255,42%);border-radius:38px;background:rgba(10,12,18,175)}');self.setCentralWidget(self.root);self.bg=QPixmap();self.load_bg()
  self.stack=QStackedWidget();lay=QVBoxLayout(self.root);lay.setContentsMargins(0,0,0,0);lay.addWidget(self.stack);self.home();self.weather();self.news();self.market();self.arcade();self.settings();self.stack.setCurrentIndex(0)
  self.t=QTimer(self);self.t.timeout.connect(self.clock);self.t.start(1000);self.clock()
 def load_bg(self):
  p=CACHE/'bg.jpg'
  if p.exists():self.bg.load(str(p))
  u=f'https://picsum.photos/seed/desktop-pet-{random.randint(1,999999)}/1800/1200';self.bg_worker=W(lambda:requests.get(u,timeout=10).content);self.work.append(self.bg_worker);self.bg_worker.done.connect(self.bg_ok);self.bg_worker.finished.connect(lambda:self._release_worker(self.bg_worker));self.bg_worker.start()
 def _release_worker(self,w):
  try:self.work.remove(w)
  except ValueError:pass
  w.deleteLater()
 def bg_ok(self,b):
  try:
   if len(b)>1000:(CACHE/'bg.jpg').write_bytes(b);self.bg.loadFromData(b);self.update()
  except:pass
 def paintEvent(self,e):
  p=QPainter(self.root);p.setRenderHint(QPainter.Antialiasing);r=self.root.rect()
  if not self.bg.isNull():
   s=self.bg.scaled(r.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation);p.drawPixmap(r,s);p.fillRect(r,QColor(5,7,12,105))
  else:
   g=QLinearGradient(0,0,r.width(),r.height());g.setColorAt(0,QColor(38,42,55));g.setColorAt(1,QColor(7,9,12));p.fillRect(r,g)
  p.fillRect(r,QColor(7,9,12,50));p.end();super().paintEvent(e)
 def clock(self):
  if hasattr(self,'time'):self.time.setText(datetime.now().strftime('%H:%M'));self.date.setText(datetime.now().strftime('%Y.%m.%d  ·  %A'))
 def head(self,title,sub):
  x=QVBoxLayout();x.setContentsMargins(42,28,42,12);r=QHBoxLayout();b=Btn('‹ HOME');b.setFixedWidth(125);b.clicked.connect(lambda:self.stack.setCurrentIndex(0));r.addWidget(b);r.addStretch();x.addLayout(r);a=QLabel(title);a.setStyleSheet('color:white;font-size:36px;font-weight:900');x.addWidget(a);s=QLabel(sub);s.setStyleSheet('color:rgba(255,255,255,180);font-size:13px');x.addWidget(s);return x
 def home(self):
  w=QWidget();o=QVBoxLayout(w);o.setContentsMargins(62,38,62,44);r=QHBoxLayout();r.addStretch();q=Btn('×');q.setFixedSize(52,52);q.clicked.connect(self.hide);r.addWidget(q);o.addLayout(r);self.time=QLabel();self.time.setAlignment(Qt.AlignCenter);self.time.setStyleSheet('color:white;font-size:86px;font-weight:900;letter-spacing:-3px');o.addWidget(self.time);self.date=QLabel();self.date.setAlignment(Qt.AlignCenter);self.date.setStyleSheet('color:rgba(255,255,255,200);font-size:18px;font-weight:700');o.addWidget(self.date);o.addStretch();c=Glass(35,32);cl=QVBoxLayout(c);a=QLabel('A little companion for a busy desktop.');a.setStyleSheet('color:white;font-size:19px;font-weight:800');s=QLabel('Fantasy Liquid Glass  •  simple, spacious, alive');s.setStyleSheet('color:rgba(255,255,255,180)');cl.addWidget(a);cl.addWidget(s);o.addWidget(c);o.addStretch();r=QHBoxLayout();r.setSpacing(18)
  for i,t in enumerate([('☼','Weather','CWA'),('◉','News','RSS'),('↗','Market','Stocks'),('✦','Arcade','Games'),('⚙','Settings','System')]):
   b=QPushButton(f'{t[0]}\n{t[1]}\n{t[2]}');b.setFixedSize(150,150);b.setCursor(Qt.PointingHandCursor);b.setStyleSheet('QPushButton{background:rgba(255,255,255,54%);color:white;border:1px solid rgba(255,255,255,65%);border-radius:34px;font-size:18px;font-weight:900}QPushButton:hover{background:rgba(255,255,255,74%)}');b.clicked.connect(lambda _,n=i+1:self.stack.setCurrentIndex(n));r.addWidget(b)
  o.addLayout(r);self.stack.addWidget(w)
 def page(self,title,sub):
  w=QWidget();o=self.head(title,sub);w.setLayout(o);body=QVBoxLayout();w.layout().addLayout(body);self.stack.addWidget(w);return w,body
 def weather(self):
  w,b=self.page('Weather','Central Weather Administration + AQI');r=QHBoxLayout();c=Glass(38);l=QVBoxLayout(c);self.temp=QLabel('--°C');self.temp.setStyleSheet('color:white;font-size:68px;font-weight:900');self.wx=QLabel('Loading…');self.wx.setStyleSheet('color:white;font-size:24px;font-weight:800');self.wdet=QLabel('Humidity --\nWind --\nRain --');self.wdet.setStyleSheet('color:rgba(255,255,255,190);font-size:15px');l.addWidget(QLabel(self.cfg.get('city','臺中市')));l.addWidget(self.temp);l.addWidget(self.wx);l.addWidget(self.wdet);r.addWidget(c,3);a=Glass(34);al=QVBoxLayout(a);self.aqi=QLabel('--');self.aqi.setStyleSheet('color:white;font-size:64px;font-weight:900');self.aqis=QLabel('AQI · --');self.aqis.setStyleSheet('color:white;font-size:18px;font-weight:800');self.pm=QLabel('PM2.5 --');self.pm.setStyleSheet('color:rgba(255,255,255,190)');al.addWidget(QLabel('AIR QUALITY'));al.addWidget(self.aqi);al.addWidget(self.aqis);al.addWidget(self.pm);r.addWidget(a,2);b.addLayout(r);n=QLabel('Demo mode is ON. Add CWA_API_KEY / MOENV_API_KEY for live data.');n.setStyleSheet('color:rgba(255,255,255,160);font-size:11px');b.addWidget(n)
  self.weather_worker=W(self.get_weather);self.work.append(self.weather_worker);self.weather_worker.done.connect(self.set_weather);self.weather_worker.finished.connect(lambda:self._release_worker(self.weather_worker));self.weather_worker.start()
 def get_weather(self):
  if self.cfg.get('demo',True) or not CWA:return {'t':29,'h':72,'wind':2.1,'wx':'多雲時晴','rain':20}
  j=requests.get('https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001',headers={'Authorization':CWA},params={'format':'JSON'},timeout=10).json();ss=j.get('records',{}).get('Station',[]);s=next((x for x in ss if x.get('CountyName')==self.cfg.get('city')),ss[0]);e=s.get('WeatherElement',{});return {'t':e.get('AirTemperature','--'),'h':e.get('RelativeHumidity','--'),'wind':e.get('WindSpeed','--'),'wx':s.get('Weather','--'),'rain':'--'}
 def set_weather(self,d):self.temp.setText(f"{d['t']}°C");self.wx.setText(str(d['wx']));self.wdet.setText(f"Humidity {d['h']}%\nWind {d['wind']} m/s\nRain {d['rain']}%") ;self.aqi.setText('42');self.aqis.setText('AQI · Good');self.pm.setText('PM2.5 12')
 def news(self):
  w,b=self.page('News','Google News RSS · no GNews API key');nav=QHBoxLayout();self.nl=QListWidget();self.nl.setStyleSheet('QListWidget{background:transparent;border:none}QListWidget::item{background:rgba(255,255,255,38%);color:white;padding:15px;margin:5px;border-radius:16px}')
  for n,u in RSS.items():x=Btn(n);x.clicked.connect(lambda _,u=u:self.load_news(u));nav.addWidget(x)
  b.addLayout(nav);b.addWidget(self.nl);self.load_news(RSS['🔥 熱門'])
 def load_news(self,u):
  self.nl.clear();self.nl.addItem('Loading…');self.news_worker=W(lambda:feedparser.parse(u));self.work.append(self.news_worker);self.news_worker.done.connect(self.news_ok);self.news_worker.finished.connect(lambda:self._release_worker(self.news_worker));self.news_worker.start()
 def news_ok(self,f):
  self.nl.clear()
  for e in f.entries[:18]:i=QListWidgetItem('  '+e.get('title','Untitled'));i.setData(Qt.UserRole,e.get('link','https://news.google.com/'));self.nl.addItem(i)
  try:self.nl.itemDoubleClicked.disconnect()
  except:pass
  self.nl.itemDoubleClicked.connect(lambda i:QDesktopServices.openUrl(QUrl(i.data(Qt.UserRole))))
 def market(self):
  w,b=self.page('Market','Quick watchlist · 1D data');top=QHBoxLayout();self.q=QLineEdit();self.q.setPlaceholderText('Search 0050 / 2330 / AAPL');self.q.setStyleSheet('QLineEdit{background:rgba(255,255,255,42%);color:white;border:1px solid rgba(255,255,255,50%);border-radius:18px;padding:14px}');x=Btn('SEARCH');x.clicked.connect(self.search_market);top.addWidget(self.q);top.addWidget(x);b.addLayout(top);self.ml=QListWidget();self.ml.setStyleSheet('QListWidget{background:transparent;border:none}QListWidget::item{background:rgba(255,255,255,38%);color:white;padding:15px;margin:5px;border-radius:16px}');b.addWidget(self.ml);self.mv=QLabel('Select a market');self.mv.setStyleSheet('color:white;font-size:40px;font-weight:900');b.addWidget(self.mv);self.fill_markets()
 def fill_markets(self):
  self.ml.clear()
  for s,n in [('^TWII','TAIEX / 加權'),('0050.TW','0050'),('2330.TW','台積電'),('AAPL','Apple'),('MSFT','Microsoft'),('NVDA','NVIDIA'),('TSLA','Tesla')]:i=QListWidgetItem(f'{n}    {s}');i.setData(Qt.UserRole,s);self.ml.addItem(i)
  self.ml.itemClicked.connect(lambda i:self.market_load(i.data(Qt.UserRole)))
 def search_market(self):
  q=self.q.text().strip().upper();self.market_load(q if not q.isdigit() else q+'.TW')
 def market_load(self,s):
  self.mv.setText('Loading…');self.market_worker=W(lambda:self.market_fetch(s));self.work.append(self.market_worker);self.market_worker.done.connect(lambda t:self.mv.setText(t));self.market_worker.finished.connect(lambda:self._release_worker(self.market_worker));self.market_worker.start()
 def market_fetch(self,s):
  try:
   j=requests.get('https://query1.finance.yahoo.com/v8/finance/chart/'+s,params={'range':'1d','interval':'5m'},timeout=10).json();m=j['chart']['result'][0]['meta'];p=m.get('regularMarketPrice');pc=m.get('previousClose');return f'{s}   {p if p is not None else "--"}   {"" if p is None or pc is None else f"({p-pc:+.2f})"}'
  except:return s+'   Offline / unavailable'
 def arcade(self):
  w,b=self.page('Arcade','A tiny game layer for your desktop pet');a=QLabel('MEMORY ESCAPE');a.setStyleSheet('color:white;font-size:30px;font-weight:900');b.addWidget(a);self.info=QLabel('Press START and memorize the highlighted cells.');self.info.setStyleSheet('color:rgba(255,255,255,185);font-size:14px');b.addWidget(self.info);g=QFrame();gl=QGridLayout(g);self.cells=[];self.seq=[];self.inp=[]
  for i in range(16):
   x=Btn(str(i+1));x.clicked.connect(lambda _,i=i:self.cell(i));self.cells.append(x);gl.addWidget(x,i//4,i%4)
  b.addWidget(g);x=Btn('START');x.clicked.connect(self.start_game);b.addWidget(x)
 def start_game(self):
  self.seq=random.sample(range(16),4);self.inp=[];self.info.setText('Memorize…');[x.setText('●' if i in self.seq else str(i+1)) for i,x in enumerate(self.cells)];QTimer.singleShot(1200,self.hide_seq)
 def hide_seq(self):[x.setText(str(i+1)) for i,x in enumerate(self.cells)];self.info.setText('Your turn!')
 def cell(self,i):
  if not self.seq:return
  p=len(self.inp);self.inp.append(i)
  if i!=self.seq[p]:self.info.setText('Miss! Try again.');self.seq=[]
  elif len(self.inp)==len(self.seq):self.info.setText('Perfect! ✦');self.seq=[]
 def settings(self):
  w,b=self.page('Settings','Personalize the Fantasy Glass');c=Glass(36);l=QVBoxLayout(c);l.addWidget(QLabel('Theme'));self.theme=QComboBox();self.theme.addItems(['Monochrome','Blue','Purple','Green','Orange']);self.theme.setCurrentText(self.cfg.get('theme','Monochrome'));l.addWidget(self.theme);l.addWidget(QLabel('City'));self.city=QComboBox();self.city.addItems(['臺中市','臺北市','新北市','桃園市','臺南市','高雄市']);self.city.setCurrentText(self.cfg.get('city','臺中市'));l.addWidget(self.city);self.demo=QCheckBox('Demo mode (offline-friendly)');self.demo.setChecked(self.cfg.get('demo',True));l.addWidget(self.demo);saveb=Btn('SAVE SETTINGS');saveb.clicked.connect(self.save_settings);l.addWidget(saveb);l.addStretch();b.addWidget(c)
 def save_settings(self):
  self.cfg['theme']=self.theme.currentText();self.cfg['city']=self.city.currentText();self.cfg['demo']=self.demo.isChecked();save(self.cfg);QMessageBox.information(self,'Desktop Pet','Settings saved.')
class Pet(QWidget):
 def __init__(self,cfg):
  super().__init__();self.dash=Dashboard(cfg);self.setWindowFlags(Qt.FramelessWindowHint|Qt.Tool|Qt.WindowStaysOnTopHint);self.setAttribute(Qt.WA_TranslucentBackground);self.setFixedSize(150,150);self.move(80,100);self.phase=0;self.drag=None;self.t=QTimer(self);self.t.timeout.connect(self.anim);self.t.start(45);self.setCursor(Qt.PointingHandCursor)
 def anim(self):self.phase+=.08;self.update()
 def paintEvent(self,e):
  p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);b=5*math.sin(self.phase);p.setPen(Qt.NoPen);p.setBrush(QBrush(QColor(0,0,0,60)));p.drawEllipse(28,122,94,16);p.setBrush(QBrush(QColor(247,248,251,240)));p.drawEllipse(28,30+b,94,84);p.setBrush(QBrush(QColor(225,228,236,235)));p.drawEllipse(37,19+b,25,32);p.drawEllipse(88,19+b,25,32);p.setBrush(QBrush(QColor(22,24,30,245)));p.drawEllipse(56,61+b,9,13);p.drawEllipse(86,61+b,9,13);p.setPen(QPen(QColor(70,72,80,235),2));p.drawArc(63,76+b,28,18,200*16,140*16)
 def mousePressEvent(self,e):
  if e.button()==Qt.RightButton:m=QMenu(self);m.addAction('Open Dashboard',self.open);m.addAction('Hide Pet',self.hide);m.addSeparator();m.addAction('Quit',QApplication.quit);m.exec(e.globalPosition().toPoint());return
  self.drag=e.globalPosition().toPoint()-self.frameGeometry().topLeft()
 def mouseMoveEvent(self,e):
  if self.drag is not None and e.buttons()&Qt.LeftButton:self.move(e.globalPosition().toPoint()-self.drag)
 def mouseReleaseEvent(self,e):self.drag=None
 def mouseDoubleClickEvent(self,e):self.open()
 def open(self):self.dash.show();self.dash.raise_();self.dash.activateWindow()
def main():
 app=QApplication(sys.argv);app.setApplicationName(APP);app.setQuitOnLastWindowClosed(False);cfg=load();pet=Pet(cfg);pet.show();tray=QSystemTrayIcon(app.style().standardIcon(QStyle.SP_ComputerIcon),pet);m=QMenu();m.addAction('Open Dashboard',pet.open);m.addAction('Show Pet',pet.show);m.addAction('Hide Pet',pet.hide);m.addSeparator();m.addAction('Quit',app.quit);tray.setContextMenu(m);tray.show();pet.open();return app.exec()
if __name__=='__main__':sys.exit(main())