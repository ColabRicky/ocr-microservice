# OCR Microservice

FastAPI OCR microservice using rapidocr-onnxruntime.

# 1. 進入微服務專案目錄
cd /Users/rickyho/Documents/github/ocr-microservice
# 2. 啟動 FastAPI 服務（指定 8005 連接埠以避免衝突）
uv run uvicorn main:app --port 8005 --host 127.0.0.1

# 服務啟動後，開啟另一個終端機視窗，發送指令以驗證服務狀態與推理功能：

# 3. 測試健康度接口
curl http://127.0.0.1:8005/health
# 預期輸出：{"status":"healthy","engine_loaded":true}
# 4. 發送測試圖片進行實體 OCR 推理
curl -X POST -F "file=@/Users/rickyho/Documents/github/djangoMap/remarksPhotos/imageDBTreeInv.png" http://127.0.0.1:8005/ocr