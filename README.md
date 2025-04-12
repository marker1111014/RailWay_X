# X (Twitter) 圖片下載 Telegram Bot

這是一個 Telegram 機器人，可以從 X (Twitter) 貼文中下載圖片。

## 部署到 Railway

1. Fork 這個倉庫到你的 GitHub 帳戶
2. 在 Railway 上創建新項目
3. 選擇 "Deploy from GitHub repo"
4. 選擇你 fork 的倉庫
5. 設置以下環境變數：
   - `TELEGRAM_BOT_TOKEN`: 你的 Telegram Bot Token
   - `TWITTER_BEARER_TOKEN`: 你的 Twitter API Bearer Token
6. 點擊 "Deploy" 開始部署

## 環境變數

- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token，從 [@BotFather](https://t.me/BotFather) 獲取
- `TWITTER_BEARER_TOKEN`: Twitter API Bearer Token，從 [Twitter Developer Portal](https://developer.twitter.com/) 獲取

## 使用方法

1. 在 Telegram 中啟動機器人
2. 發送 X (Twitter) 貼文連結
3. 機器人會自動下載並發送貼文中的圖片

## 注意事項

- 請確保你的 X (Twitter) API 有足夠的權限
- 機器人只能處理公開的貼文
- 如果貼文沒有圖片，機器人會回傳提示訊息 