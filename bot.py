import os
import re
import logging
import json
import time
import requests
import subprocess
import tempfile
import uuid
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
    driver = None
    temp_dir = None
    
    try:
        # 獲取貼文 ID
        tweet_url = update.message.text
        tweet_id = re.search(r'/status/(\d+)', tweet_url)
        
        if not tweet_id:
            await update.message.reply_text('請發送有效的 X.com 貼文連結！')
            return
            
        tweet_id = tweet_id.group(1)
        
        # 創建唯一的臨時用戶數據目錄
        temp_dir = os.path.join(tempfile.gettempdir(), f'chrome_{uuid.uuid4().hex}')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 設置 Chrome 選項
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--disable-site-isolation-trials')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-accelerated-2d-canvas')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-zygote')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument(f'--user-data-dir={temp_dir}')
        chrome_options.add_argument('--remote-debugging-port=0')  # 使用隨機端口
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # 設置 Chrome 二進制文件路徑
        chrome_options.binary_location = os.getenv('CHROME_BIN', '/usr/bin/google-chrome')
        
        # 初始化 WebDriver
        try:
            # 使用 webdriver_manager 獲取 ChromeDriver 路徑
            driver_path = ChromeDriverManager().install()
            
            # 找到實際的 chromedriver 可執行文件
            chromedriver_dir = os.path.dirname(driver_path)
            chromedriver_executable = None
            
            # 檢查目錄中的所有文件
            for file in os.listdir(chromedriver_dir):
                if file.startswith('chromedriver'):
                    chromedriver_executable = os.path.join(chromedriver_dir, file)
                    break
            
            if not chromedriver_executable:
                # 如果找不到，嘗試在子目錄中查找
                for root, dirs, files in os.walk(chromedriver_dir):
                    for file in files:
                        if file.startswith('chromedriver'):
                            chromedriver_executable = os.path.join(root, file)
                            break
                    if chromedriver_executable:
                        break
            
            if not chromedriver_executable:
                raise Exception("找不到 chromedriver 可執行文件")
            
            # 設置執行權限
            os.chmod(chromedriver_executable, 0o755)
            
            # 創建 Service 對象
            service = Service(executable_path=chromedriver_executable)
            
            # 初始化 WebDriver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
        except Exception as e:
            logging.error(f"ChromeDriver 初始化錯誤: {str(e)}")
            # 嘗試使用系統安裝的 ChromeDriver
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                logging.error(f"系統 ChromeDriver 初始化錯誤: {str(e2)}")
                await update.message.reply_text('初始化瀏覽器時發生錯誤，請稍後再試。')
                return
        
        try:
            # 訪問貼文頁面
            driver.get(f"https://twitter.com/i/status/{tweet_id}")
            
            # 等待頁面加載
            time.sleep(5)  # 等待動態內容加載
            
            # 獲取頁面源碼
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
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
            
            # 如果還是沒有找到，嘗試使用 JavaScript 獲取
            try:
                # 等待媒體元素加載
                media_elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="tweetPhoto"], [data-testid="videoPlayer"]'))
                )
                
                for element in media_elements:
                    if element.get_attribute('data-testid') == 'tweetPhoto':
                        img_url = element.find_element(By.TAG_NAME, 'img').get_attribute('src')
                        if img_url:
                            img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                            await update.message.reply_photo(img_url)
                    elif element.get_attribute('data-testid') == 'videoPlayer':
                        preview_url = element.find_element(By.TAG_NAME, 'img').get_attribute('src')
                        if preview_url:
                            await update.message.reply_photo(preview_url)
                return
            except Exception as e:
                logging.error(f"Error with JavaScript extraction: {str(e)}")
            
            await update.message.reply_text('這則貼文中沒有圖片或影片！')
                
        except Exception as e:
            logging.error(f"Error fetching tweet: {str(e)}")
            await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')
                    
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')
    finally:
        # 確保清理資源
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"Error quitting driver: {str(e)}")
        
        if temp_dir:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logging.error(f"Error cleaning up temp directory: {str(e)}")

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