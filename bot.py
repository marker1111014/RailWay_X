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
from playwright.async_api import async_playwright, TimeoutError
import asyncio
import random
import httpx

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    "https://nitter.moomoo.me",
    "https://nitter.weiler.rocks",
    "https://nitter.esmailelbob.xyz",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.mint.lgbt",
    "https://nitter.foss.wtf",
    "https://nitter.projectsegfau.lt",
    "https://nitter.woodland.cafe"
]

# 隨機打亂 Nitter 實例列表
random.shuffle(NITTER_INSTANCES)

# Twitter API 端點
TWITTER_API_ENDPOINTS = [
    "https://api.twitter.com/1.1/videos/tweet/config/{tweet_id}.json",
    "https://api.twitter.com/1.1/statuses/show/{tweet_id}.json",
    "https://api.twitter.com/2/tweets/{tweet_id}?expansions=attachments.media_keys&media.fields=url,preview_image_url,type"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """發送開始訊息"""
    await update.message.reply_text(
        '歡迎使用 X.com 圖片提取機器人！\n'
        '請直接發送 X.com 的貼文連結給我，我會幫你提取圖片。'
    )

async def extract_images_with_requests(tweet_id, update):
    """使用 requests 庫從 Nitter 提取圖片"""
    media_found = False
    
    # 遍歷所有 Nitter 實例
    for nitter_base in NITTER_INSTANCES:
        if media_found:
            break
            
        try:
            logger.info(f"Trying Nitter instance with requests: {nitter_base}")
            nitter_url = f"{nitter_base}/i/status/{tweet_id}"
            
            # 設置請求頭
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            # 發送請求
            logger.info(f"Sending request to: {nitter_url}")
            response = requests.get(nitter_url, headers=headers, timeout=10)
            
            # 檢查響應狀態
            if response.status_code != 200:
                logger.warning(f"Failed to access Nitter instance {nitter_base}, status code: {response.status_code}")
                continue
            
            # 獲取頁面內容
            nitter_content = response.text
            logger.info(f"Nitter page content length: {len(nitter_content)}")
            
            # 檢查頁面是否包含錯誤訊息
            if "Error loading tweet" in nitter_content or "Tweet not found" in nitter_content:
                logger.warning(f"Tweet not found on Nitter instance: {nitter_base}")
                continue
            
            # 使用 BeautifulSoup 解析頁面
            logger.info("Parsing Nitter page with BeautifulSoup...")
            nitter_soup = BeautifulSoup(nitter_content, 'html.parser')
            
            # 查找所有圖片
            logger.info("Searching for images in Nitter page...")
            nitter_images = nitter_soup.find_all('img', {'class': 'tweet-image'})
            logger.info(f"Found {len(nitter_images)} images with class 'tweet-image'")
            
            # 如果沒有找到帶有 tweet-image 類的圖片，嘗試查找所有圖片
            if not nitter_images:
                logger.info("No images with class 'tweet-image', trying all images...")
                all_images = nitter_soup.find_all('img')
                logger.info(f"Found {len(all_images)} total images")
                
                # 過濾出可能是推文圖片的圖片
                for img in all_images:
                    src = img.get('src', '')
                    if src and ('pbs.twimg.com/media/' in src or 'pbs.twimg.com/tweet_video_thumb/' in src):
                        nitter_images.append(img)
                
                logger.info(f"Filtered to {len(nitter_images)} potential tweet images")
            
            if nitter_images:
                logger.info(f"Found {len(nitter_images)} images with Nitter instance: {nitter_base}")
                for img in nitter_images:
                    img_url = img['src']
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    logger.info(f"Sending image from Nitter: {img_url}")
                    await update.message.reply_photo(img_url)
                    media_found = True
                
                # 如果成功提取了媒體，跳出循環
                if media_found:
                    logger.info(f"Successfully extracted media from Nitter instance: {nitter_base}")
                    break
            else:
                logger.info(f"No images found on Nitter instance: {nitter_base}")
                
        except Exception as e:
            logger.error(f"Error with Nitter instance {nitter_base}: {str(e)}")
            continue
    
    return media_found

async def extract_images_with_twitter_api(tweet_id, update):
    """使用 Twitter API 提取圖片"""
    media_found = False
    
    # 設置請求頭
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Referer': f'https://twitter.com/i/status/{tweet_id}',
        'Origin': 'https://twitter.com'
    }
    
    # 遍歷所有 Twitter API 端點
    for api_endpoint in TWITTER_API_ENDPOINTS:
        if media_found:
            break
            
        try:
            api_url = api_endpoint.format(tweet_id=tweet_id)
            logger.info(f"Trying Twitter API endpoint: {api_url}")
            
            # 發送請求
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, headers=headers, timeout=10)
                
                # 檢查響應狀態
                if response.status_code != 200:
                    logger.warning(f"Failed to access Twitter API endpoint {api_url}, status code: {response.status_code}")
                    continue
                
                # 解析 JSON 響應
                try:
                    data = response.json()
                    logger.info(f"Twitter API response: {json.dumps(data)[:200]}...")
                    
                    # 方法 1: 視頻配置 API
                    if 'variants' in data:
                        logger.info("Found 'variants' in API response")
                        for variant in data['variants']:
                            if variant.get('content_type') == 'image/jpeg':
                                img_url = variant.get('url')
                                if img_url:
                                    logger.info(f"Sending image from Twitter API: {img_url}")
                                    await update.message.reply_photo(img_url)
                                    media_found = True
                    
                    # 方法 2: 推文狀態 API
                    elif 'extended_entities' in data and 'media' in data['extended_entities']:
                        logger.info("Found 'extended_entities.media' in API response")
                        for media in data['extended_entities']['media']:
                            if media.get('type') == 'photo':
                                img_url = media.get('media_url_https')
                                if img_url:
                                    # 移除圖片大小限制
                                    img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                    logger.info(f"Sending image from Twitter API: {img_url}")
                                    await update.message.reply_photo(img_url)
                                    media_found = True
                            elif media.get('type') == 'video':
                                video_info = media.get('video_info', {})
                                variants = video_info.get('variants', [])
                                for variant in variants:
                                    if variant.get('content_type') == 'image/jpeg':
                                        preview_url = variant.get('url')
                                        if preview_url:
                                            logger.info(f"Sending video preview from Twitter API: {preview_url}")
                                            await update.message.reply_photo(preview_url)
                                            media_found = True
                    
                    # 方法 3: Twitter API v2
                    elif 'includes' in data and 'media' in data['includes']:
                        logger.info("Found 'includes.media' in API response (Twitter API v2)")
                        for media in data['includes']['media']:
                            if media.get('type') == 'photo':
                                img_url = media.get('url')
                                if img_url:
                                    logger.info(f"Sending image from Twitter API v2: {img_url}")
                                    await update.message.reply_photo(img_url)
                                    media_found = True
                            elif media.get('type') == 'video':
                                preview_url = media.get('preview_image_url')
                                if preview_url:
                                    logger.info(f"Sending video preview from Twitter API v2: {preview_url}")
                                    await update.message.reply_photo(preview_url)
                                    media_found = True
                    
                    # 如果成功提取了媒體，跳出循環
                    if media_found:
                        logger.info(f"Successfully extracted media from Twitter API endpoint: {api_url}")
                        break
                    else:
                        logger.info(f"No media found in Twitter API response from: {api_url}")
                
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response from Twitter API endpoint: {api_url}")
                    continue
                
        except Exception as e:
            logger.error(f"Error with Twitter API endpoint {api_url}: {str(e)}")
            continue
    
    return media_found

async def extract_images_with_embed_api(tweet_id, update):
    """使用 Twitter 嵌入 API 提取圖片"""
    media_found = False
    
    try:
        embed_url = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tweet_id}"
        logger.info(f"Trying Twitter embed API: {embed_url}")
        
        # 設置請求頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': f'https://twitter.com/i/status/{tweet_id}',
            'Origin': 'https://twitter.com'
        }
        
        # 發送請求
        async with httpx.AsyncClient() as client:
            response = await client.get(embed_url, headers=headers, timeout=10)
            
            # 檢查響應狀態
            if response.status_code != 200:
                logger.warning(f"Failed to access Twitter embed API, status code: {response.status_code}")
                return False
            
            # 解析 JSON 響應
            try:
                data = response.json()
                logger.info(f"Twitter embed API response: {json.dumps(data)[:200]}...")
                
                if 'html' in data:
                    embed_html = data['html']
                    embed_soup = BeautifulSoup(embed_html, 'html.parser')
                    embed_images = embed_soup.find_all('img')
                    
                    if embed_images:
                        logger.info(f"Found {len(embed_images)} images with embed API")
                        for img in embed_images:
                            img_url = img['src']
                            logger.info(f"Sending image from embed API: {img_url}")
                            await update.message.reply_photo(img_url)
                            media_found = True
                    else:
                        logger.info("No images found in embed API response")
                else:
                    logger.info("No 'html' field in embed API response")
            
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON response from Twitter embed API")
                return False
    
    except Exception as e:
        logger.error(f"Error with Twitter embed API: {str(e)}")
        return False
    
    return media_found

async def extract_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """從 X.com 貼文中提取圖片"""
    try:
        # 獲取貼文 ID
        tweet_url = update.message.text
        logger.info(f"Processing tweet URL: {tweet_url}")
        
        tweet_id = re.search(r'/status/(\d+)', tweet_url)
        if not tweet_id:
            logger.error("Invalid tweet URL format")
            await update.message.reply_text('請發送有效的 X.com 貼文連結！')
            return
            
        tweet_id = tweet_id.group(1)
        logger.info(f"Extracted tweet ID: {tweet_id}")
        
        media_found = False
        
        # 方法 1: 使用 Twitter API 提取媒體
        logger.info("Trying to extract media using Twitter API...")
        media_found = await extract_images_with_twitter_api(tweet_id, update)
        
        # 方法 2: 使用 Twitter 嵌入 API 提取媒體
        if not media_found:
            logger.info("Twitter API extraction failed, trying Twitter embed API...")
            media_found = await extract_images_with_embed_api(tweet_id, update)
        
        # 方法 3: 使用 requests 從 Nitter 提取媒體
        if not media_found:
            logger.info("Twitter embed API extraction failed, trying Nitter with requests...")
            media_found = await extract_images_with_requests(tweet_id, update)
        
        # 方法 4: 使用 Playwright 從 Twitter 直接提取
        if not media_found:
            logger.info("Nitter extraction failed, trying Twitter directly with Playwright...")
            
            # 使用 Playwright 訪問貼文頁面
            async with async_playwright() as p:
                try:
                    logger.info("Launching browser...")
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
                    
                    logger.info("Creating new page...")
                    # 創建新頁面
                    page = await browser.new_page()
                    
                    # 設置用戶代理
                    await page.set_extra_http_headers({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    })
                    
                    try:
                        logger.info(f"Navigating to tweet URL: https://twitter.com/i/status/{tweet_id}")
                        # 訪問貼文頁面
                        try:
                            await page.goto(f"https://twitter.com/i/status/{tweet_id}", timeout=30000)
                        except TimeoutError:
                            logger.error("Page load timeout")
                            await update.message.reply_text('頁面加載超時，請稍後再試。')
                            return
                        
                        # 等待頁面加載
                        logger.info("Waiting for page to load...")
                        try:
                            await page.wait_for_load_state('networkidle', timeout=30000)
                        except TimeoutError:
                            logger.warning("Network idle timeout, continuing anyway")
                        
                        # 檢查頁面內容
                        page_content = await page.content()
                        logger.info("Checking page content...")
                        
                        # 檢查是否需要登錄
                        if "Log in to X" in page_content or "Sign in to X" in page_content:
                            logger.error("Login required")
                            await update.message.reply_text('這則貼文需要登錄才能查看，請確保貼文是公開的。')
                            return
                        
                        # 檢查推文是否存在
                        if "This Tweet is unavailable" in page_content or "Tweet unavailable" in page_content:
                            logger.error("Tweet unavailable")
                            await update.message.reply_text('這則貼文無法訪問，可能已被刪除或設為私密。')
                            return
                        
                        # 檢查是否有錯誤訊息
                        if "Something went wrong" in page_content:
                            logger.error("Twitter error")
                            # 不要立即返回，繼續嘗試提取媒體
                            logger.info("Continuing despite Twitter error message")
                        
                        # 等待更長時間以確保動態內容加載
                        logger.info("Waiting for dynamic content...")
                        await asyncio.sleep(15)  # 增加等待時間
                        
                        # 嘗試使用多種方法提取媒體
                        
                        # 方法 1: 使用 JavaScript 提取
                        try:
                            logger.info("Trying JavaScript extraction method 1...")
                            # 等待媒體元素加載
                            media_elements = await page.query_selector_all('[data-testid="tweetPhoto"], [data-testid="videoPlayer"]')
                            logger.info(f"Found {len(media_elements)} media elements")
                            
                            for element in media_elements:
                                data_testid = await element.get_attribute('data-testid')
                                if data_testid == 'tweetPhoto':
                                    img_element = await element.query_selector('img')
                                    if img_element:
                                        img_url = await img_element.get_attribute('src')
                                        if img_url:
                                            img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                            logger.info(f"Sending image from JavaScript method 1: {img_url}")
                                            await update.message.reply_photo(img_url)
                                            media_found = True
                                elif data_testid == 'videoPlayer':
                                    img_element = await element.query_selector('img')
                                    if img_element:
                                        preview_url = await img_element.get_attribute('src')
                                        if preview_url:
                                            logger.info(f"Sending video preview from JavaScript method 1: {preview_url}")
                                            await update.message.reply_photo(preview_url)
                                            media_found = True
                        except Exception as e:
                            logger.error(f"Error with JavaScript extraction method 1: {str(e)}")
                        
                        # 方法 2: 使用 BeautifulSoup 解析
                        if not media_found:
                            try:
                                logger.info("Trying BeautifulSoup extraction...")
                                # 獲取頁面源碼
                                page_source = await page.content()
                                soup = BeautifulSoup(page_source, 'html.parser')
                                
                                # 查找所有圖片
                                images = soup.find_all('img', {'src': re.compile(r'https://pbs\.twimg\.com/media/')})
                                if images:
                                    logger.info(f"Found {len(images)} images with BeautifulSoup")
                                    for img in images:
                                        img_url = img['src']
                                        # 移除圖片大小限制
                                        img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                        logger.info(f"Sending image from BeautifulSoup: {img_url}")
                                        await update.message.reply_photo(img_url)
                                        media_found = True
                                
                                # 如果沒有找到圖片，檢查是否有影片預覽圖
                                if not media_found:
                                    video_previews = soup.find_all('img', {'src': re.compile(r'https://pbs\.twimg\.com/tweet_video_thumb/')})
                                    if video_previews:
                                        logger.info(f"Found {len(video_previews)} video previews with BeautifulSoup")
                                        for preview in video_previews:
                                            await update.message.reply_photo(preview['src'])
                                            media_found = True
                            except Exception as e:
                                logger.error(f"Error with BeautifulSoup extraction: {str(e)}")
                        
                        # 方法 3: 使用 JavaScript 執行腳本
                        if not media_found:
                            try:
                                logger.info("Trying JavaScript execution method...")
                                # 執行 JavaScript 來提取媒體 URL
                                media_urls = await page.evaluate('''() => {
                                    const mediaUrls = [];
                                    // 查找所有圖片
                                    document.querySelectorAll('img').forEach(img => {
                                        const src = img.src;
                                        if (src && (src.includes('pbs.twimg.com/media/') || src.includes('pbs.twimg.com/tweet_video_thumb/'))) {
                                            mediaUrls.push(src);
                                        }
                                    });
                                    return mediaUrls;
                                }''')
                                
                                if media_urls and len(media_urls) > 0:
                                    logger.info(f"Found {len(media_urls)} media URLs with JavaScript execution")
                                    for url in media_urls:
                                        # 移除圖片大小限制
                                        url = re.sub(r'&name=\w+', '&name=orig', url)
                                        logger.info(f"Sending media from JavaScript execution: {url}")
                                        await update.message.reply_photo(url)
                                        media_found = True
                            except Exception as e:
                                logger.error(f"Error with JavaScript execution: {str(e)}")
                        
                        # 如果還是沒有找到媒體
                        if not media_found:
                            logger.info("No media found in tweet")
                            # 檢查推文是否真的沒有媒體
                            try:
                                # 檢查是否有媒體容器
                                media_container = await page.query_selector('[data-testid="tweetPhoto"], [data-testid="videoPlayer"], [data-testid="cardWrapper"]')
                                if media_container:
                                    logger.info("Media container found but extraction failed")
                                    await update.message.reply_text('無法提取這則貼文中的媒體，可能是因為 Twitter 的限制。')
                                else:
                                    logger.info("No media container found, tweet has no media")
                                    await update.message.reply_text('這則貼文中沒有圖片或影片！')
                            except Exception as e:
                                logger.error(f"Error checking media container: {str(e)}")
                                await update.message.reply_text('這則貼文中沒有圖片或影片！')
                    
                    except Exception as e:
                        logger.error(f"Error with Twitter direct extraction: {str(e)}")
                        await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')
                    
                except Exception as e:
                    logger.error(f"Error fetching tweet: {str(e)}")
                    await update.message.reply_text('處理貼文時發生錯誤，請稍後再試。')
                finally:
                    # 關閉瀏覽器
                    logger.info("Closing browser...")
                    await browser.close()
                    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
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