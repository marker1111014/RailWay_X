import os
import re
import logging
import json
import requests
from bs4 import BeautifulSoup
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
        
        # 使用網頁抓取
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            # 先嘗試獲取 oEmbed 數據
            oembed_url = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tweet_id}"
            response = requests.get(oembed_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                html_content = data.get('html', '')
                
                # 從 HTML 中提取圖片 URL
                img_urls = re.findall(r'https://pbs\.twimg\.com/media/[^"\']+', html_content)
                
                if img_urls:
                    # 轉換圖片 URL 為高質量版本
                    for img_url in img_urls:
                        # 移除圖片大小限制
                        img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                        await update.message.reply_photo(img_url)
                    return
                
                # 如果沒有找到圖片，檢查是否有影片
                if 'video' in html_content.lower():
                    # 提取影片預覽圖
                    preview_urls = re.findall(r'https://pbs\.twimg\.com/tweet_video_thumb/[^"\']+', html_content)
                    if preview_urls:
                        for preview_url in preview_urls:
                            await update.message.reply_photo(preview_url)
                        return
            
            # 如果 oEmbed 失敗，嘗試直接抓取網頁
            tweet_url = f"https://twitter.com/i/status/{tweet_id}"
            response = requests.get(tweet_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 查找所有圖片
                images = soup.find_all('img', {'src': re.compile(r'https://pbs\.twimg\.com/media/')})
                if images:
                    for img in images:
                        img_url = img['src']
                        # 移除圖片大小限制
                        img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                        await update.message.reply_photo(img_url)
                    return
                
                # 如果沒有找到圖片，檢查是否有影片預覽圖
                video_previews = soup.find_all('img', {'src': re.compile(r'https://pbs\.twimg\.com/tweet_video_thumb/')})
                if video_previews:
                    for preview in video_previews:
                        await update.message.reply_photo(preview['src'])
                    return
            
            await update.message.reply_text('這則貼文中沒有圖片或影片！')
                
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