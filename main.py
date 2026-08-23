import io
import os
import time

# https://www.paddleocr.ai/latest/version3.x/pipeline_usage/OCR.html#21

# 繞過 PaddlePaddle 對模型主機連線的檢查，省去 startup 的延遲
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
# 限制 OMP 執行緒數為 1 以最佳化 OpenBLAS 運算效能並消除警告
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import paddleocr
# from paddleocr import PaddleOCR
from paddlex import create_pipeline

app = FastAPI(
    title="PaddleOCR Official Microservice",
    description="FastAPI microservice using official PaddleOCR engine",
    version="1.0.0"
)

# 啟用 CORS 跨域存取，方便前端 WebApp 跨域調用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from typing import List
from pydantic import BaseModel, Field

class OcrResultItem(BaseModel):
    text: str = Field(..., description="辨識出的文字")
    confidence: float = Field(..., description="辨識置信度")

class OcrResponse(BaseModel):
    success: bool = Field(..., description="執行是否成功")
    elapsed_ms: float = Field(..., description="推理耗時 (毫秒)")
    text_combined: str = Field(..., description="所有辨識文字的組合字串 (以逗號隔開)")
    results: List[OcrResultItem] = Field(..., description="辨識結果文字清單")

# 初始化 OCR 推理引擎 (以 PaddleX 3.x Pipeline PP-OCRv6/v5 為優先，傳統 PaddleOCR PP-OCRv4 為降級備援)
ocr_engine = None
engine_type = None

try:
    try:
        from paddlex import create_pipeline
        ocr_engine = create_pipeline(pipeline="OCR")
        engine_type = "paddlex"
        print("💡 Official PaddleX OCR Pipeline (PP-OCRv6/v5) successfully initialized")
    except Exception as err1:
        print(f"💡 PaddleX Pipeline load failed ({err1}), falling back to traditional PaddleOCR (PP-OCRv4)...")
        from paddleocr import PaddleOCR
        try:
            ocr_engine = PaddleOCR(use_textline_orientation=True, lang="ch", ocr_version="PP-OCRv4")
        except Exception:
            ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", ocr_version="PP-OCRv4")
        engine_type = "paddleocr"
        print("💡 Traditional PaddleOCR Engine (PP-OCRv4) successfully initialized")
except Exception as e:
    print(f"⚠️ Failed to initialize OCR Engine: {e}")
    ocr_engine = None
    engine_type = None

@app.post("/ocr", response_model=OcrResponse)
async def perform_ocr(file: UploadFile = File(...)):
    if ocr_engine is None:
        raise HTTPException(status_code=500, detail="OCR engine is not initialized.")

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
        start_time = time.time()

        formatted_results = []
        text_list = []

        # 4. 根據引擎類型執行推論與精簡文字解析 (無需 bbox)
        if engine_type == "paddlex":
            outputs = ocr_engine.predict(image_np)
            for res in outputs:
                inner_res = res.get('res', res) if isinstance(res, dict) else (getattr(res, 'res', res) or res)
                
                # 提取辨識文字陣列 (相容 PaddleX 3.x 各版本欄位命名)
                rec_texts = (
                    getattr(inner_res, 'rec_texts', None) 
                    or getattr(inner_res, 'rec_text', None)
                    or (inner_res.get('rec_texts') if isinstance(inner_res, dict) else None)
                    or (inner_res.get('rec_text') if isinstance(inner_res, dict) else None)
                    or []
                )
                if isinstance(rec_texts, str):
                    rec_texts = [rec_texts]
                    
                # 提取辨識置信度陣列
                rec_scores = (
                    getattr(inner_res, 'rec_scores', None)
                    or getattr(inner_res, 'rec_score', None)
                    or (inner_res.get('rec_scores') if isinstance(inner_res, dict) else None)
                    or (inner_res.get('rec_score') if isinstance(inner_res, dict) else None)
                    or []
                )
                if isinstance(rec_scores, (int, float)):
                    rec_scores = [rec_scores] * len(rec_texts)

                for text, score in zip(rec_texts, rec_scores):
                    clean_text = str(text).strip()
                    if clean_text:
                        formatted_results.append({
                            "text": clean_text,
                            "confidence": float(score)
                        })
                        text_list.append(clean_text)
        else:
            ocr_result = ocr_engine.ocr(image_np)
            if ocr_result and len(ocr_result) > 0 and ocr_result[0] is not None:
                for line in ocr_result[0]:
                    try:
                        _, (text, conf) = line
                        clean_text = str(text).strip()
                        if clean_text:
                            formatted_results.append({
                                "text": clean_text,
                                "confidence": float(conf)
                            })
                            text_list.append(clean_text)
                    except Exception:
                        continue

        elapsed_ms = (time.time() - start_time) * 1000
        text_combined = ", ".join(text_list)

        print(f"💡 OCR executed ({engine_type}) in {elapsed_ms:.1f} ms. Found {len(formatted_results)} text items.")
        
        return {
            "success": True,
            "elapsed_ms": elapsed_ms,
            "text_combined": text_combined,
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
        "engine_loaded": ocr_engine is not None
    }

if __name__ == "__main__":
    import uvicorn
    # 動態獲取環境變數 PORT，預設使用 8005
    server_port = int(os.environ.get("PORT", 8005))
    print(f"🚀 Starting Official PaddleOCR Microservice on port: {server_port}")
    uvicorn.run("main:app", host="0.0.0.0", port=server_port, reload=True)
