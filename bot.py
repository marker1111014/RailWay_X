import os
import re
import logging
import random
import time
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import asyncio
import requests
from fake_useragent import UserAgent

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
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.unixfox.eu",
    "https://nitter.fdn.fr",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.domain.glass",
    "https://nitter.moomoo.me"
]

class NitterScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def _get_random_headers(self):
        """生成隨機請求頭"""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
        
    def _convert_nitter_url_to_twitter(self, nitter_url):
        """將 Nitter 圖片 URL 轉換為 Twitter 圖片 URL"""
        try:
            media_pattern = r'/media%2F([^%]+)'
            match = re.search(media_pattern, nitter_url)
            if match:
                media_id = match.group(1)
                return f"https://pbs.twimg.com/media/{media_id}?format=jpg&name=orig"
            return None
        except Exception as e:
            logging.error(f"URL 轉換失敗: {str(e)}")
            return None

    def get_tweet_images(self, tweet_url):
        """從推文中獲取圖片"""
        try:
            # 提取用戶名和推文 ID
            pattern = r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'
            match = re.search(pattern, tweet_url)
            if not match:
                return None
                
            username, tweet_id = match.groups()
            
            # 嘗試多個 Nitter 實例
            for nitter_instance in NITTER_INSTANCES:
                try:
                    nitter_url = f"{nitter_instance}/{username}/status/{tweet_id}"
                    headers = self._get_random_headers()
                    headers["Referer"] = f"{nitter_instance}/{username}"
                    
                    response = self.session.get(
                        nitter_url,
                        headers=headers,
                        timeout=20
                    )
                    
                    if response.status_code != 200:
                        continue
                        
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # 查找圖片容器
                    image_containers = []
                    containers = soup.find_all("div", class_="attachments")
                    if containers:
                        image_containers.extend(containers)
                    
                    if not image_containers:
                        containers = soup.find_all("div", class_="gallery-row")
                        if containers:
                            image_containers.extend(containers)
                    
                    if not image_containers:
                        containers = soup.find_all("div", class_="tweet-content")
                        if containers:
                            image_containers.extend(containers)
                    
                    if not image_containers:
                        containers = soup.find_all("div", class_="tweet-body")
                        if containers:
                            image_containers.extend(containers)
                    
                    if not image_containers:
                        containers = soup.find_all("div", class_="media-container")
                        if containers:
                            image_containers.extend(containers)
                    
                    if not image_containers:
                        containers = soup.find_all("div", class_="attachment")
                        if containers:
                            image_containers.extend(containers)
                    
                    if not image_containers:
                        containers = soup.find_all("div", class_="media")
                        if containers:
                            image_containers.extend(containers)
                    
                    if not image_containers:
                        image_containers = [soup]
                    
                    # 提取圖片 URL
                    images = []
                    for container in image_containers:
                        # 嘗試不同的圖片選擇器
                        still_images = container.find_all("a", class_="still-image")
                        if still_images:
                            for still_image in still_images:
                                href = still_image.get('href', '')
                                if href:
                                    if href.startswith('//'):
                                        img_url = 'https:' + href
                                    elif href.startswith('/'):
                                        img_url = f"{nitter_instance}{href}"
                                    else:
                                        img_url = href
                                    
                                    if "/pic/" in img_url:
                                        original_url = img_url.replace("/pic/", "/img/")
                                        if "?" in original_url:
                                            original_url = original_url.split("?")[0]
                                        if "/orig/" not in original_url and "/media/" in original_url:
                                            original_url = original_url.replace("/media/", "/orig/media/")
                                        images.append(original_url)
                                    else:
                                        images.append(img_url)
                        
                        # 嘗試其他圖片選擇器
                        img_elements = container.find_all("img", class_="attachment image")
                        if not img_elements:
                            img_elements = container.find_all("img", class_="tweet-img")
                        if not img_elements:
                            img_elements = container.find_all("img", class_="media-image")
                        if not img_elements:
                            img_elements = container.find_all("img", attrs={"alt": "Image"})
                        if not img_elements:
                            img_elements = container.find_all("img")
                        
                        for img in img_elements:
                            if 'src' in img.attrs:
                                img_url = img['src']
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif img_url.startswith('/'):
                                    img_url = f"{nitter_instance}{img_url}"
                                
                                if "/pic/" in img_url:
                                    original_url = img_url.replace("/pic/", "/img/")
                                    if "?" in original_url:
                                        original_url = original_url.split("?")[0]
                                    if "/orig/" not in original_url and "/media/" in original_url:
                                        original_url = original_url.replace("/media/", "/orig/media/")
                                    images.append(original_url)
                                else:
                                    images.append(img_url)
                    
                    if images:
                        return images
                        
                except Exception as e:
                    logging.error(f"Nitter 實例 {nitter_instance} 失敗: {str(e)}")
                    continue
            
            return None
            
        except Exception as e:
            logging.error(f"獲取推文圖片失敗: {str(e)}")
            return None

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
        
        # 首先嘗試使用 Playwright
        try:
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
                            '--allow-running-insecure-content',
                            '--disable-setuid-sandbox',
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
                    
                    # 訪問貼文頁面
                    await page.goto(f"https://twitter.com/i/status/{tweet_id}")
                    
                    # 等待頁面加載
                    await page.wait_for_load_state('networkidle')
                    await asyncio.sleep(5)  # 額外等待動態內容加載
                    
                    # 獲取頁面源碼
                    page_source = await page.content()
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
                        media_elements = await page.query_selector_all('[data-testid="tweetPhoto"], [data-testid="videoPlayer"]')
                        
                        for element in media_elements:
                            data_testid = await element.get_attribute('data-testid')
                            if data_testid == 'tweetPhoto':
                                img_element = await element.query_selector('img')
                                if img_element:
                                    img_url = await img_element.get_attribute('src')
                                    if img_url:
                                        img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                        await update.message.reply_photo(img_url)
                            elif data_testid == 'videoPlayer':
                                img_element = await element.query_selector('img')
                                if img_element:
                                    preview_url = await img_element.get_attribute('src')
                                    if preview_url:
                                        await update.message.reply_photo(preview_url)
                        return
                    except Exception as e:
                        logging.error(f"Error with JavaScript extraction: {str(e)}")
                    
                    await update.message.reply_text('這則貼文中沒有圖片或影片！')
                        
                except Exception as e:
                    logging.error(f"Error fetching tweet: {str(e)}")
                    raise  # 重新拋出異常以觸發 Nitter 備用方案
                finally:
                    # 關閉瀏覽器
                    await browser.close()
        except Exception as e:
            logging.error(f"Playwright 方法失敗，嘗試使用 Nitter: {str(e)}")
            # 如果 Playwright 失敗，嘗試使用 Nitter
            scraper = NitterScraper()
            images = scraper.get_tweet_images(tweet_url)
            
            if images:
                for img_url in images:
                    await update.message.reply_photo(img_url)
                return
            else:
                await update.message.reply_text('這則貼文中沒有圖片或影片！')
                    
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