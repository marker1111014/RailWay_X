import os
import re
import logging
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import tweepy
from tweepy.errors import TooManyRequests
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 獲取環境變數
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# 初始化 Twitter API 客戶端
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

# 重試設置
MAX_RETRIES = 3
RETRY_DELAY = 60  # 秒

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """發送開始訊息"""
    await update.message.reply_text(
        '歡迎使用 X.com 圖片提取機器人！\n'
        '請直接發送 X.com 的貼文連結給我，我會幫你提取圖片。'
    )

async def extract_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """從 X.com 貼文中提取圖片"""
    try:
        # 獲取貼文 ID
        tweet_url = update.message.text
        tweet_id = re.search(r'/status/(\d+)', tweet_url)
        
        if not tweet_id:
            await update.message.reply_text('請發送有效的 X.com 貼文連結！')
            return
            
        tweet_id = tweet_id.group(1)
        
        # 添加重試機制
        for attempt in range(MAX_RETRIES):
            try:
                # 獲取貼文內容
                tweet = client.get_tweet(tweet_id, expansions=['attachments.media_keys'],
                                       media_fields=['url', 'preview_image_url'])
                break
            except TooManyRequests:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (attempt + 1)
                    await update.message.reply_text(
                        f'Twitter API 請求限制，等待 {wait_time} 秒後重試...'
                    )
                    time.sleep(wait_time)
                else:
                    await update.message.reply_text(
                        '抱歉，Twitter API 請求限制，請稍後再試。'
                    )
                    return
        
        if not hasattr(tweet, 'includes') or 'media' not in tweet.includes:
            await update.message.reply_text('這則貼文中沒有圖片！')
            return
            
        # 發送圖片
        for media in tweet.includes['media']:
            if media.type == 'photo':
                image_url = media.url
                await update.message.reply_photo(image_url)
            elif media.type == 'video':
                preview_url = media.preview_image_url
                if preview_url:
                    await update.message.reply_photo(preview_url)
                    
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        if isinstance(e, TooManyRequests):
            await update.message.reply_text(
                '抱歉，Twitter API 請求限制，請稍後再試。'
            )
        else:
            await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')

def main():
    """主程序"""
    # 創建應用
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # 添加處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, extract_images))

    # 啟動機器人
    application.run_polling()

if __name__ == '__main__':
    main() 