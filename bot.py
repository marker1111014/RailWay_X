import os
import re
import logging
import json
import time
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import asyncio

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
        
        # 使用 Playwright 訪問 Nitter 頁面
        async with async_playwright() as p:
            try:
                # 啟動瀏覽器
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions',
                        '--disable-infobars',
                        '--disable-notifications',
                        '--disable-popup-blocking',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-site-isolation-trials',
                        '--disable-web-security',
                        '--allow-running-insecure-content',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--single-process'
                    ]
                )
                
                # 創建新頁面
                page = await browser.new_page()
                
                # 設置用戶代理
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
                
                # 訪問 Nitter 頁面
                nitter_url = f"https://nitter.net/i/status/{tweet_id}"
                await page.goto(nitter_url)
                
                # 等待頁面加載
                await page.wait_for_load_state('networkidle')
                await asyncio.sleep(5)  # 額外等待動態內容加載
                
                # 獲取頁面源碼
                page_source = await page.content()
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # 查找所有圖片
                images = soup.find_all('img', {'class': 'attachment-image'})
                if images:
                    for img in images:
                        img_url = img['src']
                        if not img_url.startswith('http'):
                            img_url = 'https://nitter.net' + img_url
                        await update.message.reply_photo(img_url)
                    return
                
                # 如果沒有找到圖片，檢查是否有影片預覽圖
                video_previews = soup.find_all('img', {'class': 'attachment-video'})
                if video_previews:
                    for preview in video_previews:
                        preview_url = preview['src']
                        if not preview_url.startswith('http'):
                            preview_url = 'https://nitter.net' + preview_url
                        await update.message.reply_photo(preview_url)
                    return
                
                await update.message.reply_text('這則貼文中沒有圖片或影片！')
                    
            except Exception as e:
                logging.error(f"Error fetching tweet: {str(e)}")
                await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')
            finally:
                # 關閉瀏覽器
                await browser.close()
                    
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