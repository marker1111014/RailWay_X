# 使用 Python 3.11 作為基礎映像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 創建非 root 用戶
RUN useradd -m appuser

# 安裝 Playwright 瀏覽器
RUN mkdir -p /home/appuser/.cache && \
    playwright install chromium && \
    playwright install-deps && \
    chown -R appuser:appuser /home/appuser/.cache

# 複製應用程序代碼
COPY --chown=appuser:appuser . .

# 切換到非 root 用戶
USER appuser

# 設置環境變數
ENV PYTHONUNBUFFERED=1

# 啟動應用
CMD ["python", "bot.py"] 