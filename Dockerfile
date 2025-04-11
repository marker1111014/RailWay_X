FROM python:3.11-slim

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Playwright 瀏覽器
RUN playwright install chromium
RUN playwright install-deps

# 複製應用程序代碼
COPY . .

# 創建非 root 用戶
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 設置環境變數
ENV PYTHONUNBUFFERED=1

# 啟動應用
CMD ["python", "bot.py"] 