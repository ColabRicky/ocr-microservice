# 使用官方輕量版 Python 映像檔作為基礎環境
FROM python:3.10-slim

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 設定工作目錄
WORKDIR /app

# 安裝系統級依賴（包含 Git 用於複製私有倉庫，以及 OpenCV、PaddlePaddle 執行所需的共享庫與 C++ 編譯環境）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 從官方 uv 映像檔中直接複製 uv 工具二進位檔，無需手動編譯
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 複製引導程式碼到工作目錄
COPY . .

# 預先利用 uv 以極速進行系統級安裝 (--system 裝在容器全域環境中)，安裝大型依賴與框架
# 這能大幅縮短容器啟動後拉取私有倉庫時的 pip install 時間
RUN uv pip install --system --no-cache \
    fastapi \
    uvicorn \
    pillow \
    numpy \
    python-multipart \
    paddlepaddle \
    paddleocr

# 暴露服務埠口（Hugging Face Space 預設監聽 7860）
EXPOSE 7860

# 執行 app.py 來複製私有程式碼並啟動服務
CMD ["python", "app.py"]
