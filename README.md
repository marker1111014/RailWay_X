# X.com 圖片提取 Telegram 機器人

這是一個 Telegram 機器人，可以從 X.com (Twitter) 的貼文中提取圖片。

## 功能

- 接收 X.com 貼文連結
- 自動提取貼文中的圖片
- 支援圖片和影片預覽圖

## 設置

1. 克隆此專案
2. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```
3. 設置環境變數：
   - 複製 `.env.example` 到 `.env`
   - 填入你的 Telegram Bot Token
   - 填入你的 Twitter Bearer Token

## 部署到 Railway

1. 在 Railway 創建新專案
2. 連接你的 GitHub 倉庫
3. 設置環境變數：
   - `TELEGRAM_TOKEN`
   - `TWITTER_BEARER_TOKEN`
4. 部署專案

## 使用方法

1. 在 Telegram 中搜索你的機器人
2. 發送 `/start` 開始使用
3. 直接發送 X.com 的貼文連結給機器人
4. 機器人會自動提取並發送圖片

## 注意事項

- 需要有效的 Twitter API Bearer Token
- 需要有效的 Telegram Bot Token
- 確保貼文是公開的且包含圖片 