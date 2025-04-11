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
    "https://nitter.net"
]

# 隨機打亂 Nitter 實例列表
random.shuffle(NITTER_INSTANCES)

# Twitter API 端點
TWITTER_API_ENDPOINTS = [
    "https://api.twitter.com/1.1/videos/tweet/config/{tweet_id}.json",
    "https://api.twitter.com/1.1/statuses/show/{tweet_id}.json",
    "https://api.twitter.com/2/tweets/{tweet_id}?expansions=attachments.media_keys&media.fields=url,preview_image_url,type"
]

# Twitter GraphQL API 端點
TWITTER_GRAPHQL_ENDPOINTS = [
    "https://twitter.com/i/api/graphql/oMVVrI5kt3kOpyHHTTKf5Q/TweetDetail?variables=%7B%22focalTweetId%22%3A%22{tweet_id}%22%2C%22with_rux_injections%22%3Afalse%2C%22includePromotedContent%22%3Afalse%2C%22withCommunity%22%3Atrue%2C%22withQuickPromoteEligibilityTweetFields%22%3Afalse%2C%22withBirdwatchNotes%22%3Afalse%2C%22withVoice%22%3Atrue%2C%22withV2Timeline%22%3Atrue%7D",
    "https://twitter.com/i/api/graphql/0hWvDhmW8YOQ2fq22wF0Mw/TweetResultByRestId?variables=%7B%22tweetId%22%3A%22{tweet_id}%22%2C%22withCommunity%22%3Atrue%2C%22includePromotedContent%22%3Afalse%7D"
]

# 隨機生成的 Twitter 客戶端 ID
TWITTER_CLIENT_ID = "".join(random.choices("0123456789abcdef", k=32))

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

async def extract_images_with_graphql_api(tweet_id, update):
    """使用 Twitter GraphQL API 提取圖片"""
    media_found = False
    
    # 設置請求頭
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Referer': f'https://twitter.com/i/status/{tweet_id}',
        'Origin': 'https://twitter.com',
        'x-twitter-client-language': 'en',
        'x-twitter-active-user': 'yes',
        'x-csrf-token': TWITTER_CLIENT_ID,
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-version': 'web',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'te': 'trailers'
    }
    
    # 遍歷所有 Twitter GraphQL API 端點
    for api_endpoint in TWITTER_GRAPHQL_ENDPOINTS:
        if media_found:
            break
            
        try:
            api_url = api_endpoint.format(tweet_id=tweet_id)
            logger.info(f"Trying Twitter GraphQL API endpoint: {api_url}")
            
            # 發送請求
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, headers=headers, timeout=10)
                
                # 檢查響應狀態
                if response.status_code != 200:
                    logger.warning(f"Failed to access Twitter GraphQL API endpoint {api_url}, status code: {response.status_code}")
                    continue
                
                # 解析 JSON 響應
                try:
                    data = response.json()
                    logger.info(f"Twitter GraphQL API response: {json.dumps(data)[:200]}...")
                    
                    # 方法 1: TweetDetail API
                    if 'data' in data and 'threaded_conversation_with_injections_v2' in data['data']:
                        logger.info("Found 'threaded_conversation_with_injections_v2' in GraphQL response")
                        instructions = data['data']['threaded_conversation_with_injections_v2']['instructions']
                        
                        for instruction in instructions:
                            if 'entries' in instruction:
                                for entry in instruction['entries']:
                                    if 'content' in entry and 'itemContent' in entry['content']:
                                        tweet_results = entry['content']['itemContent']['tweet_results']
                                        if 'result' in tweet_results:
                                            result = tweet_results['result']
                                            
                                            # 檢查是否有媒體
                                            if 'legacy' in result and 'extended_entities' in result['legacy']:
                                                media = result['legacy']['extended_entities']['media']
                                                for item in media:
                                                    if item['type'] == 'photo':
                                                        img_url = item['media_url_https']
                                                        # 移除圖片大小限制
                                                        img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                                        logger.info(f"Sending image from GraphQL API: {img_url}")
                                                        await update.message.reply_photo(img_url)
                                                        media_found = True
                                                    elif item['type'] == 'video':
                                                        video_info = item['video_info']
                                                        variants = video_info['variants']
                                                        for variant in variants:
                                                            if variant['content_type'] == 'image/jpeg':
                                                                preview_url = variant['url']
                                                                logger.info(f"Sending video preview from GraphQL API: {preview_url}")
                                                                await update.message.reply_photo(preview_url)
                                                                media_found = True
                    
                    # 方法 2: TweetResultByRestId API
                    elif 'data' in data and 'tweet_result' in data['data']:
                        logger.info("Found 'tweet_result' in GraphQL response")
                        result = data['data']['tweet_result']
                        
                        if 'legacy' in result and 'extended_entities' in result['legacy']:
                            media = result['legacy']['extended_entities']['media']
                            for item in media:
                                if item['type'] == 'photo':
                                    img_url = item['media_url_https']
                                    # 移除圖片大小限制
                                    img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                    logger.info(f"Sending image from GraphQL API: {img_url}")
                                    await update.message.reply_photo(img_url)
                                    media_found = True
                                elif item['type'] == 'video':
                                    video_info = item['video_info']
                                    variants = video_info['variants']
                                    for variant in variants:
                                        if variant['content_type'] == 'image/jpeg':
                                            preview_url = variant['url']
                                            logger.info(f"Sending video preview from GraphQL API: {preview_url}")
                                            await update.message.reply_photo(preview_url)
                                            media_found = True
                    
                    # 如果成功提取了媒體，跳出循環
                    if media_found:
                        logger.info(f"Successfully extracted media from Twitter GraphQL API endpoint: {api_url}")
                        break
                    else:
                        logger.info(f"No media found in Twitter GraphQL API response from: {api_url}")
                
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response from Twitter GraphQL API endpoint: {api_url}")
                    continue
                
        except Exception as e:
            logger.error(f"Error with Twitter GraphQL API endpoint {api_url}: {str(e)}")
            continue
    
    return media_found

async def get_guest_token():
    """獲取 Twitter Guest Token"""
    try:
        logger.info("Getting Twitter Guest Token...")
        
        # 設置請求頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Origin': 'https://twitter.com',
            'Referer': 'https://twitter.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers'
        }
        
        # 發送請求
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.twitter.com/1.1/guest/activate.json',
                headers=headers,
                timeout=10
            )
            
            # 檢查響應狀態
            if response.status_code != 200:
                logger.warning(f"Failed to get Guest Token, status code: {response.status_code}")
                return None
            
            # 解析 JSON 響應
            try:
                data = response.json()
                guest_token = data.get('guest_token')
                if guest_token:
                    logger.info(f"Successfully got Guest Token: {guest_token[:10]}...")
                    return guest_token
                else:
                    logger.warning("No Guest Token in response")
                    return None
            
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON response from Guest Token API")
                return None
    
    except Exception as e:
        logger.error(f"Error getting Guest Token: {str(e)}")
        return None

async def extract_images_with_guest_token(tweet_id, update):
    """使用 Twitter Guest Token 提取圖片"""
    media_found = False
    
    try:
        # 獲取 Guest Token
        guest_token = await get_guest_token()
        if not guest_token:
            logger.warning("Failed to get Guest Token, skipping Guest Token extraction")
            return False
        
        # 設置請求頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': f'https://twitter.com/i/status/{tweet_id}',
            'Origin': 'https://twitter.com',
            'x-guest-token': guest_token,
            'x-twitter-client-language': 'en',
            'x-twitter-active-user': 'yes',
            'x-twitter-client-version': 'web',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'te': 'trailers'
        }
        
        # 嘗試使用 Guest Token 訪問 Twitter API
        api_url = f"https://api.twitter.com/1.1/statuses/show/{tweet_id}.json?tweet_mode=extended"
        logger.info(f"Trying Twitter API with Guest Token: {api_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=10)
            
            # 檢查響應狀態
            if response.status_code != 200:
                logger.warning(f"Failed to access Twitter API with Guest Token, status code: {response.status_code}")
                return False
            
            # 解析 JSON 響應
            try:
                data = response.json()
                logger.info(f"Twitter API response with Guest Token: {json.dumps(data)[:200]}...")
                
                # 檢查是否有媒體
                if 'extended_entities' in data and 'media' in data['extended_entities']:
                    logger.info("Found 'extended_entities.media' in API response with Guest Token")
                    for media in data['extended_entities']['media']:
                        if media.get('type') == 'photo':
                            img_url = media.get('media_url_https')
                            if img_url:
                                # 移除圖片大小限制
                                img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                logger.info(f"Sending image from Twitter API with Guest Token: {img_url}")
                                await update.message.reply_photo(img_url)
                                media_found = True
                        elif media.get('type') == 'video':
                            video_info = media.get('video_info', {})
                            variants = video_info.get('variants', [])
                            for variant in variants:
                                if variant.get('content_type') == 'image/jpeg':
                                    preview_url = variant.get('url')
                                    if preview_url:
                                        logger.info(f"Sending video preview from Twitter API with Guest Token: {preview_url}")
                                        await update.message.reply_photo(preview_url)
                                        media_found = True
                
                # 如果沒有找到媒體，嘗試使用 Guest Token 訪問 GraphQL API
                if not media_found:
                    logger.info("No media found with Guest Token, trying GraphQL API...")
                    
                    # 設置 GraphQL 請求頭
                    graphql_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Connection': 'keep-alive',
                        'Referer': f'https://twitter.com/i/status/{tweet_id}',
                        'Origin': 'https://twitter.com',
                        'x-guest-token': guest_token,
                        'x-twitter-client-language': 'en',
                        'x-twitter-active-user': 'yes',
                        'x-twitter-client-version': 'web',
                        'sec-fetch-dest': 'empty',
                        'sec-fetch-mode': 'cors',
                        'sec-fetch-site': 'same-origin',
                        'te': 'trailers'
                    }
                    
                    # 遍歷所有 Twitter GraphQL API 端點
                    for api_endpoint in TWITTER_GRAPHQL_ENDPOINTS:
                        if media_found:
                            break
                            
                        try:
                            api_url = api_endpoint.format(tweet_id=tweet_id)
                            logger.info(f"Trying Twitter GraphQL API with Guest Token: {api_url}")
                            
                            # 發送請求
                            response = await client.get(api_url, headers=graphql_headers, timeout=10)
                            
                            # 檢查響應狀態
                            if response.status_code != 200:
                                logger.warning(f"Failed to access Twitter GraphQL API with Guest Token, status code: {response.status_code}")
                                continue
                            
                            # 解析 JSON 響應
                            try:
                                data = response.json()
                                logger.info(f"Twitter GraphQL API response with Guest Token: {json.dumps(data)[:200]}...")
                                
                                # 方法 1: TweetDetail API
                                if 'data' in data and 'threaded_conversation_with_injections_v2' in data['data']:
                                    logger.info("Found 'threaded_conversation_with_injections_v2' in GraphQL response with Guest Token")
                                    instructions = data['data']['threaded_conversation_with_injections_v2']['instructions']
                                    
                                    for instruction in instructions:
                                        if 'entries' in instruction:
                                            for entry in instruction['entries']:
                                                if 'content' in entry and 'itemContent' in entry['content']:
                                                    tweet_results = entry['content']['itemContent']['tweet_results']
                                                    if 'result' in tweet_results:
                                                        result = tweet_results['result']
                                                        
                                                        # 檢查是否有媒體
                                                        if 'legacy' in result and 'extended_entities' in result['legacy']:
                                                            media = result['legacy']['extended_entities']['media']
                                                            for item in media:
                                                                if item['type'] == 'photo':
                                                                    img_url = item['media_url_https']
                                                                    # 移除圖片大小限制
                                                                    img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                                                    logger.info(f"Sending image from GraphQL API with Guest Token: {img_url}")
                                                                    await update.message.reply_photo(img_url)
                                                                    media_found = True
                                                                elif item['type'] == 'video':
                                                                    video_info = item['video_info']
                                                                    variants = video_info['variants']
                                                                    for variant in variants:
                                                                        if variant['content_type'] == 'image/jpeg':
                                                                            preview_url = variant['url']
                                                                            logger.info(f"Sending video preview from GraphQL API with Guest Token: {preview_url}")
                                                                            await update.message.reply_photo(preview_url)
                                                                            media_found = True
                                
                                # 方法 2: TweetResultByRestId API
                                elif 'data' in data and 'tweet_result' in data['data']:
                                    logger.info("Found 'tweet_result' in GraphQL response with Guest Token")
                                    result = data['data']['tweet_result']
                                    
                                    if 'legacy' in result and 'extended_entities' in result['legacy']:
                                        media = result['legacy']['extended_entities']['media']
                                        for item in media:
                                            if item['type'] == 'photo':
                                                img_url = item['media_url_https']
                                                # 移除圖片大小限制
                                                img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                                logger.info(f"Sending image from GraphQL API with Guest Token: {img_url}")
                                                await update.message.reply_photo(img_url)
                                                media_found = True
                                            elif item['type'] == 'video':
                                                video_info = item['video_info']
                                                variants = video_info['variants']
                                                for variant in variants:
                                                    if variant['content_type'] == 'image/jpeg':
                                                        preview_url = variant['url']
                                                        logger.info(f"Sending video preview from GraphQL API with Guest Token: {preview_url}")
                                                        await update.message.reply_photo(preview_url)
                                                        media_found = True
                                
                                # 如果成功提取了媒體，跳出循環
                                if media_found:
                                    logger.info(f"Successfully extracted media from Twitter GraphQL API with Guest Token: {api_url}")
                                    break
                                else:
                                    logger.info(f"No media found in Twitter GraphQL API response with Guest Token: {api_url}")
                            
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse JSON response from Twitter GraphQL API with Guest Token: {api_url}")
                                continue
                            
                        except Exception as e:
                            logger.error(f"Error with Twitter GraphQL API with Guest Token: {api_url}: {str(e)}")
                            continue
            
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON response from Twitter API with Guest Token")
                return False
    
    except Exception as e:
        logger.error(f"Error with Twitter Guest Token extraction: {str(e)}")
        return False
    
    return media_found

async def check_tweet_accessibility(tweet_id: str) -> tuple[bool, str, bool]:
    """
    檢查推文是否可以訪問
    返回: (是否可訪問, 錯誤訊息, 是否需要使用 Nitter)
    """
    try:
        async with async_playwright() as p:
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
            
            page = await browser.new_page()
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            try:
                await page.goto(f"https://twitter.com/i/status/{tweet_id}", timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)
                
                page_content = await page.content()
                
                if "Log in to X" in page_content or "Sign in to X" in page_content:
                    return False, "這則貼文需要登錄才能查看，正在嘗試使用 Nitter 提取...", True
                elif "This Tweet is unavailable" in page_content or "Tweet unavailable" in page_content:
                    return False, "這則貼文無法訪問，可能已被刪除或設為私密。", False
                elif "Something went wrong" in page_content:
                    return False, "Twitter 發生錯誤，正在嘗試使用 Nitter 提取...", True
                
                return True, "", False
                
            except Exception as e:
                logger.error(f"Error checking tweet accessibility: {str(e)}")
                return False, "檢查貼文可訪問性時發生錯誤，請稍後再試。", False
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"Error in check_tweet_accessibility: {str(e)}")
        return False, "檢查貼文可訪問性時發生錯誤，請稍後再試。", False

async def extract_images_from_nitter(tweet_id: str, update: Update) -> bool:
    """
    從 Nitter 提取圖片
    返回: 是否成功提取到媒體
    """
    media_found = False
    
    # 從原始 URL 中提取用戶名
    tweet_url = update.message.text
    username_match = re.search(r'x\.com/([^/]+)/status/', tweet_url)
    username = username_match.group(1) if username_match else None
    
    # 構建 Nitter URL - 嘗試不同的 URL 格式
    nitter_urls = [
        f"https://nitter.net/{username}/status/{tweet_id}#m" if username else f"https://nitter.net/i/status/{tweet_id}#m",
        f"https://nitter.net/{username}/status/{tweet_id}" if username else f"https://nitter.net/i/status/{tweet_id}",
        f"https://nitter.net/{username}/status/{tweet_id}/photo/1" if username else f"https://nitter.net/i/status/{tweet_id}/photo/1"
    ]
    
    # 設置請求頭 - 使用更新的 Chrome User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://nitter.net/',
        'DNT': '1',
        'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="135", "Chromium";v="135"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1'
    }
    
    for nitter_url in nitter_urls:
        if media_found:
            break
            
        try:
            logger.info(f"Trying Nitter URL: {nitter_url}")
            
            # 發送請求 - 增加超時時間和重試機制
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    logger.info(f"Sending request to: {nitter_url} (attempt {retry_count + 1})")
                    response = requests.get(nitter_url, headers=headers, timeout=30)
                    
                    # 檢查響應狀態
                    if response.status_code == 200:
                        break
                    elif response.status_code == 429:  # Too Many Requests
                        logger.warning("Rate limited by Nitter, waiting before retry...")
                        await asyncio.sleep(5)  # 等待 5 秒後重試
                    else:
                        logger.warning(f"Failed to access Nitter, status code: {response.status_code}")
                    
                    retry_count += 1
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request error: {str(e)}")
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(2)  # 等待 2 秒後重試
                    continue
            
            if retry_count == max_retries:
                logger.error("Max retries reached for Nitter request")
                continue
            
            # 獲取頁面內容
            nitter_content = response.text
            logger.info(f"Nitter page content length: {len(nitter_content)}")
            
            # 檢查頁面是否為空
            if len(nitter_content) < 100:
                logger.warning("Nitter page content is too short, might be an error page")
                continue
            
            # 檢查頁面是否包含錯誤訊息
            if "Error loading tweet" in nitter_content or "Tweet not found" in nitter_content:
                logger.warning("Tweet not found on Nitter")
                continue
            
            # 使用 BeautifulSoup 解析頁面
            logger.info("Parsing Nitter page with BeautifulSoup...")
            nitter_soup = BeautifulSoup(nitter_content, 'html.parser')
            
            # 直接查找所有圖片標籤
            logger.info("Searching for all img tags...")
            all_images = nitter_soup.find_all('img')
            logger.info(f"Found {len(all_images)} total img tags")
            
            # 過濾出可能是推文圖片的圖片
            nitter_images = []
            for img in all_images:
                src = img.get('src', '')
                if src and ('pbs.twimg.com/media/' in src or 'pbs.twimg.com/tweet_video_thumb/' in src):
                    nitter_images.append(img)
            
            logger.info(f"Filtered to {len(nitter_images)} potential tweet images")
            
            # 如果沒有找到圖片，嘗試查找帶有特定類的圖片
            if not nitter_images:
                logger.info("No images found with src filtering, trying specific classes...")
                
                # 方法 1: 查找帶有 tweet-image 類的圖片
                tweet_images = nitter_soup.find_all('img', {'class': 'tweet-image'})
                logger.info(f"Found {len(tweet_images)} images with class 'tweet-image'")
                
                # 方法 2: 查找帶有 media-item 類的圖片
                media_items = nitter_soup.find_all('div', {'class': 'media-item'})
                for item in media_items:
                    img = item.find('img')
                    if img:
                        nitter_images.append(img)
                logger.info(f"Found {len(nitter_images)} images with class 'media-item'")
                
                # 方法 3: 查找帶有 media-container 類的容器
                media_containers = nitter_soup.find_all('div', {'class': 'media-container'})
                for container in media_containers:
                    img = container.find('img')
                    if img:
                        nitter_images.append(img)
                logger.info(f"Found {len(nitter_images)} images in media-container")
            
            # 如果仍然沒有找到圖片，嘗試查找所有可能的圖片
            if not nitter_images:
                logger.info("No images found with specific classes, trying all images...")
                for img in all_images:
                    src = img.get('src', '')
                    if src and not src.startswith('data:'):  # 排除 base64 編碼的圖片
                        nitter_images.append(img)
                logger.info(f"Added {len(nitter_images)} additional images")
            
            if nitter_images:
                logger.info(f"Found {len(nitter_images)} images on Nitter")
                for img in nitter_images:
                    img_url = img.get('src', '')
                    if not img_url:
                        continue
                        
                    # 處理相對路徑
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = 'https://nitter.net' + img_url
                    
                    # 確保使用原始大小的圖片
                    if 'pbs.twimg.com/media/' in img_url:
                        img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                    
                    logger.info(f"Sending image from Nitter: {img_url}")
                    await update.message.reply_photo(img_url)
                    media_found = True
                
                # 如果成功提取了媒體，跳出循環
                if media_found:
                    logger.info(f"Successfully extracted media from Nitter URL: {nitter_url}")
                    break
            else:
                logger.info(f"No images found on Nitter URL: {nitter_url}")
                
        except Exception as e:
            logger.error(f"Error with Nitter URL {nitter_url}: {str(e)}")
            continue
    
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
        
        # 先檢查貼文是否可以訪問
        is_accessible, error_message, use_nitter = await check_tweet_accessibility(tweet_id)
        
        # 如果需要使用 Nitter
        if use_nitter:
            await update.message.reply_text(error_message)
            media_found = await extract_images_from_nitter(tweet_id, update)
            if not media_found:
                await update.message.reply_text('無法從 Nitter 提取媒體，請稍後再試。')
            return
            
        # 如果貼文無法訪問且不需要使用 Nitter
        if not is_accessible:
            await update.message.reply_text(error_message)
            return
        
        media_found = False
        media_container_found = False
        
        # 使用 Playwright 從 Twitter 直接提取
        logger.info("Trying Twitter directly with Playwright...")
        
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
                    
                    # 等待更長時間以確保動態內容加載
                    logger.info("Waiting for dynamic content...")
                    await asyncio.sleep(15)  # 增加等待時間
                    
                    # 檢查是否有媒體容器
                    media_container = await page.query_selector('[data-testid="tweetPhoto"], [data-testid="videoPlayer"], [data-testid="cardWrapper"]')
                    if media_container:
                        media_container_found = True
                        logger.info("Media container found")
                        
                        # 嘗試提取媒體
                        try:
                            # 等待媒體元素加載
                            media_elements = await page.query_selector_all('[data-testid="tweetPhoto"] img, [data-testid="videoPlayer"] img')
                            logger.info(f"Found {len(media_elements)} media elements")
                            
                            for element in media_elements:
                                img_url = await element.get_attribute('src')
                                if img_url:
                                    img_url = re.sub(r'&name=\w+', '&name=orig', img_url)
                                    logger.info(f"Found media URL: {img_url}")
                                    await update.message.reply_photo(img_url)
                                    media_found = True
                        except Exception as e:
                            logger.error(f"Error extracting media: {str(e)}")
                    
                    # 如果找到媒體容器但無法提取媒體
                    if media_container_found and not media_found:
                        logger.error("Media container found but extraction failed")
                        await update.message.reply_text('無法提取這則貼文中的媒體，可能是因為 Twitter 的限制。')
                    # 如果沒有找到媒體容器
                    elif not media_container_found:
                        logger.info("No media container found")
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