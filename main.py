import io
import os
import time

# 繞過 PaddlePaddle 對模型主機連線的檢查，省去 startup 的延遲
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
# 關閉 oneDNN，防範其在新一代編譯器（PIR）模式下對 DoubleAttribute 轉譯未實現的 C++ 異常
os.environ["FLAGS_use_onednn"] = "0"
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import paddleocr
from paddleocr import PaddleOCR

app = FastAPI(
    title="PaddleOCR Official Microservice",
    description="FastAPI microservice using official PaddleOCR engine",
    version="1.0.0"
)

import sys
try:
    import spaces
    IS_HF_SPACE = True
except ImportError:
    IS_HF_SPACE = False
    from types import ModuleType
    mock_spaces = ModuleType("spaces")
    def mock_gpu(func):
        return func
    mock_spaces.GPU = mock_gpu
    sys.modules["spaces"] = mock_spaces
    import spaces

# 啟用 CORS 跨域存取，方便前端 WebApp 跨域調用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 快取推理引擎實例，延遲初始化以配合 ZeroGPU 規範
_ocr_engine = None

@spaces.GPU
def get_and_run_ocr(image_np):
    global _ocr_engine
    if _ocr_engine is None:
        # 延遲初始化，交由 PaddleOCR 內部自動偵測 GPU/CUDA 裝置以防參數不相容
        print("💡 Initializing PaddleOCR (Auto Device Detection)")
        _ocr_engine = PaddleOCR(ocr_version="PP-OCRv5", use_angle_cls=True, lang="chinese_cht")
    return _ocr_engine.ocr(image_np)

@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    # 1. 驗證檔案類型
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file is not an image.")

    try:
        # 2. 讀取影像位元組並以 Pillow 載入
        contents = await file.read()
        
        # 安全機制：限制最大處理檔案大小為 15 MB
        if len(contents) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size exceeds the 15 MB limit.")

        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # 安全防禦與記憶體最佳化：限制影像單邊最大尺寸為 2048 像素
        width, height = image.size
        if max(width, height) > 2048:
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            print(f"💡 Auto-resized large image from {width}x{height} to {image.size[0]}x{image.size[1]}")

        # 3. 轉成 NumPy 陣列供推理引擎使用
        image_np = np.array(image)
        
        # 4. 執行 OCR 推理
        start_time = time.time()
        # 呼叫相容 ZeroGPU 的延遲載入推理函數
        ocr_result = get_and_run_ocr(image_np)
        elapsed_ms = (time.time() - start_time) * 1000

        # 5. 整理回傳格式以向下相容
        formatted_results = []
        
        # 官方 PaddleOCR 回傳格式適配 (支援新版 paddlex 字典結構與經典 list 結構)
        if ocr_result and len(ocr_result) > 0 and ocr_result[0] is not None:
            res_item = ocr_result[0]
            # 情況 A：新版 paddlex 封裝的 dict 結構
            if isinstance(res_item, dict):
                texts = res_item.get("rec_texts", [])
                scores = res_item.get("rec_scores", [])
                polys = res_item.get("rec_polys", [])
                for i in range(len(texts)):
                    text = texts[i]
                    conf = scores[i] if i < len(scores) else 0.0
                    poly = polys[i] if i < len(polys) else []
                    
                    if hasattr(poly, "tolist"):
                        points = poly.tolist()
                    else:
                        points = poly

                    formatted_results.append({
                        "points": points,
                        "text": text,
                        "confidence": float(conf)
                    })
            # 情況 B：經典的 nested list 結構 (points, (text, confidence))
            elif isinstance(res_item, list):
                for line in res_item:
                    try:
                        points, (text, conf) = line
                        if hasattr(points, "tolist"):
                            points = points.tolist()
                        formatted_results.append({
                            "points": points,
                            "text": text,
                            "confidence": float(conf)
                        })
                    except Exception:
                        continue

        print(f"💡 Official PaddleOCR PP-OCRv5 executed in {elapsed_ms:.1f} ms. Found {len(formatted_results)} text blocks.")
        
        return {
            "success": True,
            "elapsed_ms": elapsed_ms,
            "results": formatted_results
        }

    except Exception as err:
        print(f"⚠️ OCR processing failed: {err}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(err)}")

@app.get("/")
async def root():
    return {
        "message": "Official PaddleOCR Microservice is running",
        "endpoints": {
            "health": "/health",
            "ocr": "/ocr (POST)"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "engine_loaded": _ocr_engine is not None
    }

if __name__ == "__main__":
    import os
    import uvicorn
    # 動態獲取環境變數 PORT，預設使用 8005
    server_port = int(os.environ.get("PORT", 8005))
    print(f"🚀 Starting Official PaddleOCR Microservice on port: {server_port}")
    uvicorn.run("main:app", host="0.0.0.0", port=server_port, reload=True)
