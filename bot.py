import os
import re
import logging
import random
import time
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
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

# 只使用 nitter.net 作為 Nitter 實例
NITTER_INSTANCE = "https://nitter.net"

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
            logging.info(f"開始從 Nitter 獲取圖片: {tweet_url}")
            # 提取用戶名和推文 ID
            pattern = r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'
            match = re.search(pattern, tweet_url)
            if not match:
                logging.error("無效的推文 URL 格式")
                return None
                
            username, tweet_id = match.groups()
            logging.info(f"解析推文信息: 用戶名={username}, 推文ID={tweet_id}")
            
            # 使用 nitter.net 實例
            try:
                logging.info(f"使用 Nitter 實例: {NITTER_INSTANCE}")
                nitter_url = f"{NITTER_INSTANCE}/{username}/status/{tweet_id}"
                headers = self._get_random_headers()
                headers["Referer"] = f"{NITTER_INSTANCE}/{username}"
                
                response = self.session.get(
                    nitter_url,
                    headers=headers,
                    timeout=20
                )
                
                if response.status_code != 200:
                    logging.warning(f"Nitter 實例返回狀態碼: {response.status_code}")
                    return None
                    
                logging.info(f"成功獲取 Nitter 頁面: {nitter_url}")
                soup = BeautifulSoup(response.text, "html.parser")
                
                # 查找圖片容器
                logging.info("開始查找圖片容器...")
                image_containers = []
                containers = soup.find_all("div", class_="attachments")
                if containers:
                    logging.info("找到 attachments 容器")
                    image_containers.extend(containers)
                
                if not image_containers:
                    containers = soup.find_all("div", class_="gallery-row")
                    if containers:
                        logging.info("找到 gallery-row 容器")
                        image_containers.extend(containers)
                
                if not image_containers:
                    containers = soup.find_all("div", class_="tweet-content")
                    if containers:
                        logging.info("找到 tweet-content 容器")
                        image_containers.extend(containers)
                
                if not image_containers:
                    containers = soup.find_all("div", class_="tweet-body")
                    if containers:
                        logging.info("找到 tweet-body 容器")
                        image_containers.extend(containers)
                
                if not image_containers:
                    containers = soup.find_all("div", class_="media-container")
                    if containers:
                        logging.info("找到 media-container 容器")
                        image_containers.extend(containers)
                
                if not image_containers:
                    containers = soup.find_all("div", class_="attachment")
                    if containers:
                        logging.info("找到 attachment 容器")
                        image_containers.extend(containers)
                
                if not image_containers:
                    containers = soup.find_all("div", class_="media")
                    if containers:
                        logging.info("找到 media 容器")
                        image_containers.extend(containers)
                
                if not image_containers:
                    logging.info("未找到特定容器，使用整個頁面")
                    image_containers = [soup]
                
                # 提取圖片 URL
                logging.info("開始提取圖片 URL...")
                images = []
                for container in image_containers:
                    # 嘗試不同的圖片選擇器
                    still_images = container.find_all("a", class_="still-image")
                    if still_images:
                        logging.info(f"找到 {len(still_images)} 個 still-image 元素")
                        for still_image in still_images:
                            href = still_image.get('href', '')
                            if href:
                                if href.startswith('//'):
                                    img_url = 'https:' + href
                                elif href.startswith('/'):
                                    img_url = f"{NITTER_INSTANCE}{href}"
                                else:
                                    img_url = href
                                
                                if "/pic/" in img_url:
                                    original_url = img_url.replace("/pic/", "/img/")
                                    if "?" in original_url:
                                        original_url = original_url.split("?")[0]
                                    if "/orig/" not in original_url and "/media/" in original_url:
                                        original_url = original_url.replace("/media/", "/orig/media/")
                                    images.append(original_url)
                                    logging.info(f"從 still-image 找到圖片: {original_url}")
                                else:
                                    images.append(img_url)
                                    logging.info(f"從 still-image 找到圖片: {img_url}")
                    
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
                    
                    if img_elements:
                        logging.info(f"找到 {len(img_elements)} 個圖片元素")
                    
                    for img in img_elements:
                        if 'src' in img.attrs:
                            img_url = img['src']
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            elif img_url.startswith('/'):
                                img_url = f"{NITTER_INSTANCE}{img_url}"
                            
                            if "/pic/" in img_url:
                                original_url = img_url.replace("/pic/", "/img/")
                                if "?" in original_url:
                                    original_url = original_url.split("?")[0]
                                if "/orig/" not in original_url and "/media/" in original_url:
                                    original_url = original_url.replace("/media/", "/orig/media/")
                                images.append(original_url)
                                logging.info(f"從 img 標籤找到圖片: {original_url}")
                            else:
                                images.append(img_url)
                                logging.info(f"從 img 標籤找到圖片: {img_url}")
                
                if images:
                    logging.info(f"成功找到 {len(images)} 張圖片")
                    return images
                else:
                    logging.warning("未找到任何圖片")
                    return None
                    
            except Exception as e:
                logging.error(f"Nitter 實例失敗: {str(e)}")
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
        logging.info(f"收到推文連結: {tweet_url}")
        
        # 提取用戶名和推文 ID
        pattern = r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'
        match = re.search(pattern, tweet_url)
        
        if not match:
            logging.error("無效的推文連結格式")
            await update.message.reply_text('請發送有效的 X.com 貼文連結！')
            return
            
        username, tweet_id = match.groups()
        logging.info(f"解析推文信息: 用戶名={username}, 推文ID={tweet_id}")
        
        # 使用 NitterScraper 提取圖片
        logging.info("開始使用 NitterScraper 提取圖片...")
        scraper = NitterScraper()
        images = scraper.get_tweet_images(tweet_url)
        
        if images:
            logging.info(f"成功找到 {len(images)} 張圖片")
            for img_url in images:
                logging.info(f"發送圖片: {img_url}")
                await update.message.reply_photo(img_url)
            return
        else:
            logging.warning("未找到任何圖片")
            await update.message.reply_text('這則貼文中沒有圖片或影片！')
                    
    except Exception as e:
        logging.error(f"處理失敗: {str(e)}")
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