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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """發送開始訊息"""
    await update.message.reply_text(
        '歡迎使用 X.com 圖片提取機器人！\n'
        '請直接發送 X.com 的貼文連結給我，我會幫你提取圖片。\n\n'
        '注意：如果貼文包含限制級內容（18+），可能需要登入才能查看。'
    )

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
                
                # 檢查是否為限制級內容
                age_restricted = False
                try:
                    # 檢查是否有年齡限制提示
                    age_restriction_texts = [
                        "This Tweet might contain sensitive content",
                        "This Tweet contains sensitive content",
                        "This media may contain sensitive content",
                        "This media contains sensitive content",
                        "Age-restricted content",
                        "Content warning",
                        "Sensitive content",
                        "View",  # Twitter常用於限制級內容的按鈕文字
                        "Show",  # Twitter常用於限制級內容的按鈕文字
                        "Yes, view profile",  # 限制級帳號的確認按鈕
                        "Some media in this Tweet may contain sensitive content"  # 新的限制級提示
                    ]
                    
                    # 檢查頁面內容中是否包含限制級提示
                    page_text = await page.evaluate('() => document.body.innerText')
                    for text in age_restriction_texts:
                        if text.lower() in page_text.lower():
                            age_restricted = True
                            logger.info(f"Age restriction detected: {text}")
                            break
                    
                    if not age_restricted:
                        # 檢查是否有限制級內容的按鈕
                        buttons = await page.query_selector_all('div[role="button"]')
                        for button in buttons:
                            button_text = await button.text_content()
                            if button_text and any(text.lower() in button_text.lower() for text in ["View", "Show"]):
                                age_restricted = True
                                logger.info(f"Age restriction detected: Button with text '{button_text}' found")
                                break
                        
                        # 檢查是否有限制級內容的遮罩層
                        overlay = await page.query_selector('div[aria-label*="sensitive"], div[aria-label*="warning"]')
                        if overlay:
                            age_restricted = True
                            logger.info("Age restriction detected: Content overlay found")
                            
                        # 檢查是否有特定的限制級內容標記
                        markers = await page.query_selector_all('[data-testid*="warning"], [data-testid*="sensitive"]')
                        if markers:
                            age_restricted = True
                            logger.info("Age restriction detected: Content markers found")
                            
                except Exception as e:
                    logger.error(f"Error checking age restriction: {str(e)}")
                    
                if age_restricted:
                    logger.info("Tweet contains age-restricted content")
                    await update.message.reply_text('這則貼文包含限制級內容（18+），需要登入才能查看完整內容。')
                    return
                
                # 等待更長時間以確保動態內容加載
                logger.info("Waiting for dynamic content...")
                await asyncio.sleep(15)  # 增加等待時間
                
                # 嘗試使用多種方法提取媒體
                media_found = False
                
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
                
                # 方法 4: 使用 API 提取
                if not media_found:
                    try:
                        logger.info("Trying API extraction method...")
                        # 使用 Twitter API 提取媒體
                        api_url = f"https://api.twitter.com/1.1/videos/tweet/config/{tweet_id}.json"
                        response = await page.goto(api_url)
                        if response.status == 200:
                            data = await response.json()
                            if 'variants' in data:
                                for variant in data['variants']:
                                    if variant['content_type'] == 'image/jpeg':
                                        img_url = variant['url']
                                        logger.info(f"Sending image from API: {img_url}")
                                        await update.message.reply_photo(img_url)
                                        media_found = True
                    except Exception as e:
                        logger.error(f"Error with API extraction: {str(e)}")
                
                # 方法 5: 使用 Nitter 提取
                if not media_found:
                    try:
                        logger.info("Trying Nitter extraction method...")
                        # 使用 Nitter 提取媒體
                        nitter_url = f"https://nitter.net/i/status/{tweet_id}"
                        await page.goto(nitter_url, timeout=30000)
                        await page.wait_for_load_state('networkidle', timeout=30000)
                        
                        # 獲取頁面源碼
                        nitter_content = await page.content()
                        nitter_soup = BeautifulSoup(nitter_content, 'html.parser')
                        
                        # 查找所有圖片
                        nitter_images = nitter_soup.find_all('img', {'class': 'tweet-image'})
                        if nitter_images:
                            logger.info(f"Found {len(nitter_images)} images with Nitter")
                            for img in nitter_images:
                                img_url = img['src']
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                logger.info(f"Sending image from Nitter: {img_url}")
                                await update.message.reply_photo(img_url)
                                media_found = True
                    except Exception as e:
                        logger.error(f"Error with Nitter extraction: {str(e)}")
                
                # 方法 6: 使用 Twitter 嵌入 API
                if not media_found:
                    try:
                        logger.info("Trying Twitter embed API method...")
                        # 使用 Twitter 嵌入 API 提取媒體
                        embed_url = f"https://publish.twitter.com/oembed?url=https://twitter.com/i/status/{tweet_id}"
                        response = await page.goto(embed_url)
                        if response.status == 200:
                            data = await response.json()
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
                    except Exception as e:
                        logger.error(f"Error with embed API extraction: {str(e)}")
                
                # 如果還是沒有找到媒體
                if not media_found:
                    logger.info("No media found in tweet")
                    # 檢查推文是否真的沒有媒體
                    try:
                        # 檢查是否有媒體容器
                        media_container = await page.query_selector('[data-testid="tweetPhoto"], [data-testid="videoPlayer"], [data-testid="cardWrapper"]')
                        if media_container:
                            logger.info("Media container found but extraction failed")
                            if age_restricted:
                                await update.message.reply_text('這則貼文包含限制級內容（18+），需要登入才能查看完整內容。')
                            else:
                                await update.message.reply_text('無法提取這則貼文中的媒體，可能是因為 Twitter 的限制。')
                        else:
                            logger.info("No media container found, tweet has no media")
                            await update.message.reply_text('這則貼文中沒有圖片或影片！')
                    except Exception as e:
                        logger.error(f"Error checking media container: {str(e)}")
                        if age_restricted:
                            await update.message.reply_text('這則貼文包含限制級內容（18+），需要登入才能查看完整內容。')
                        else:
                            await update.message.reply_text('這則貼文中沒有圖片或影片！')
                    
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