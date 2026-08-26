# Desktop Pet V2

## 執行

```bash
python -m pip install -r requirements-v2.txt
python desktop_pet_v2.py
```

## API

複製 `.env.example` 為 `.env`，再填入：

```env
CWA_API_KEY=你的中央氣象署 Open Data 授權碼
MOENV_API_KEY=你的環境部 API Key
GNEWS_API_KEY=你的 GNews API Key
DEMO_MODE=false
```

開發測試時可維持 `DEMO_MODE=true`，完全不需要 API Key。

## V2 目前包含

- 🐾 透明桌寵
- 雙擊開 Dashboard
- 🌤️ CWA 觀測＋36 小時預報
- 🌫️ 環境部 AQI
- 📰 GNews 頭條
- 📈 TWSE 自選股
- 🎮 反應力／記憶小遊戲
- ⚙️ 設定
- 💾 本機 JSON 設定與 API Cache
- 🖥️ Windows 登入自動啟動
- 📌 System Tray
- 🧪 DEMO Mode

## 注意

V2 先放在 `desktop-pet-v2` 分支，沒有覆蓋 `main`。測試確認沒問題後，再合併回 `main`。