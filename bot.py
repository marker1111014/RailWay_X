import os
import re
import logging
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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
        
        # 使用 Twitter API v1.1
        api_url = f"https://api.twitter.com/1.1/statuses/show/{tweet_id}.json?include_entities=true"
        
        headers = {
            'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAAPYXBAAAAAAACLXUNDekMxqa8h%2F40K4moUkGsoc%3DTYfbDKbT3jJPCEVnMYqilB28NHfOPqkca3qaAxGfsyKCs0wRbw'
        }
        
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # 檢查是否有媒體
                if 'entities' in data and 'media' in data['entities']:
                    media_items = data['entities']['media']
                    
                    for media in media_items:
                        if media['type'] == 'photo':
                            # 獲取原始圖片 URL
                            image_url = media['media_url_https']
                            if '?format=' in image_url:
                                image_url = image_url.split('?')[0] + '?format=jpg&name=orig'
                            await update.message.reply_photo(image_url)
                        elif media['type'] == 'video':
                            # 獲取影片預覽圖
                            if 'media_url_https' in media:
                                await update.message.reply_photo(media['media_url_https'])
                    return
                
                await update.message.reply_text('這則貼文中沒有圖片或影片！')
            else:
                await update.message.reply_text('無法獲取貼文內容，請稍後再試。')
                
        except Exception as e:
            logging.error(f"Error fetching tweet: {str(e)}")
            await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')
                    
    except Exception as e:
        logging.error(f"Error: {str(e)}")
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