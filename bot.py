import os
import re
import logging
import time
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 禁用 SSL 警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 獲取環境變數
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Nitter 實例列表
NITTER_INSTANCES = [
    'https://nitter.net',
    'https://nitter.cz',
    'https://nitter.esmailelbob.xyz',
    'https://nitter.privacydev.net',
    'https://nitter.poast.org',
    'https://nitter.mint.lgbt',
    'https://nitter.foss.wtf',
    'https://nitter.projectsegfau.lt',
    'https://nitter.woodland.cafe',
    'https://nitter.rawbit.ninja',
]

def get_random_nitter_instance():
    """獲取隨機的 Nitter 實例"""
    import random
    return random.choice(NITTER_INSTANCES)

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
        
        # 嘗試不同的 Nitter 實例
        for instance in NITTER_INSTANCES:
            try:
                # 構建 Nitter URL
                nitter_url = f"{instance}/{tweet_id}"
                
                # 獲取頁面內容，禁用 SSL 驗證
                response = requests.get(nitter_url, timeout=10, verify=False)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找所有圖片
                    images = soup.find_all('img', class_='tweet-image')
                    if images:
                        for img in images:
                            if img.get('src'):
                                # 轉換相對 URL 為絕對 URL
                                img_url = img['src']
                                if img_url.startswith('/'):
                                    img_url = instance + img_url
                                await update.message.reply_photo(img_url)
                        return
                    
                    # 如果沒有找到圖片，檢查是否有影片預覽圖
                    video_preview = soup.find('img', class_='tweet-video-preview')
                    if video_preview and video_preview.get('src'):
                        preview_url = video_preview['src']
                        if preview_url.startswith('/'):
                            preview_url = instance + preview_url
                        await update.message.reply_photo(preview_url)
                        return
                    
                    # 如果這個實例沒有找到圖片，繼續嘗試下一個
                    continue
                    
            except Exception as e:
                logging.error(f"Error with instance {instance}: {str(e)}")
                continue
        
        # 如果所有實例都失敗了
        await update.message.reply_text('無法找到圖片，請確認貼文是否包含圖片或稍後再試。')
                    
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