# Desktop Pet Ultimate — RSS + Games

## 新聞
這版不使用 GNews API Key，改用 Google News RSS Feed：熱門、國內、科技、財經、娛樂。RSS 不需要 API 金鑰；但它不是一個帶 SLA 的正式新聞 API，因此仍可能因網路或服務端狀況暫時無資料。

## API
`.env` 只需要：

```env
CWA_API_KEY=你的CWA_KEY
MOENV_API_KEY=你的MOENV_KEY
DEMO_MODE=false
```

## 安裝

```bat
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements_ultimate.txt
```

## 執行

```bat
python desktop_pet_ultimate.py
```

## 遊戲

### 反應力
等目標亮起後立刻點擊，紀錄最佳毫秒數。

### 記憶挑戰
先看發亮位置，再照順序找回。關卡越高格數越多，會紀錄最高 Level。

### 星星接接樂
使用 ← → 控制桌寵，在限時內接住 ⭐／💎／🍎，紀錄最高分。

## PyInstaller

先測試 onedir：

```bat
pyinstaller --noconfirm --clean --windowed --onedir --name DesktopPet desktop_pet_ultimate.py
```

確認 `dist\\DesktopPet\\DesktopPet.exe` 沒問題後，再做 onefile：

```bat
pyinstaller --noconfirm --clean --windowed --onefile --name DesktopPet desktop_pet_ultimate.py
```

## 自動啟動

Settings 內開啟 Windows 登入後自動啟動。程式會建立 Startup Folder 的 `DesktopPet.lnk`。需要 `pywin32`。

## API Key 與 EXE

自己與家人使用，可以在每台電腦本機放 `.env`。不要把真正 Key 寫進 Python 原始碼。若未來公開給大量使用者，建議把第三方 API Key 移到自己的後端，不要打包進 EXE。
