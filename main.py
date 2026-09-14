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

# 初始化 OCR 推理引擎 (以 PaddleX 3.x Pipeline PP-OCRv5 為優先，傳統 PaddleOCR PP-OCRv4 為降級備援)
ocr_engine = None
engine_type = None

try:
    try:
        from paddlex import create_pipeline
        ocr_engine = create_pipeline(pipeline="OCR")
        engine_type = "paddlex"
        print("💡 Official PaddleX OCR Pipeline (PP-OCRv5) successfully initialized")
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

def extract_ocr_texts_and_scores(res):
    texts = []
    scores = []
    
    # 1. 嘗試由 dict / json 屬性讀取
    data = None
    if isinstance(res, dict):
        data = res
    elif hasattr(res, 'json') and isinstance(res.json, dict):
        data = res.json
    elif hasattr(res, 'to_dict') and callable(res.to_dict):
        try:
            data = res.to_dict()
        except Exception:
            pass

    if data:
        texts = data.get('rec_text') or data.get('rec_texts') or data.get('texts') or []
        scores = data.get('rec_score') or data.get('rec_scores') or data.get('scores') or []

    # 2. 嘗試由索引器 (__getitem__) 讀取 (相容 PaddleX 3.x OCRResult 物件)
    if not texts and hasattr(res, '__getitem__'):
        for k in ['rec_text', 'rec_texts', 'texts', 'text']:
            try:
                val = res[k]
                if val:
                    texts = val
                    break
            except Exception:
                pass
        for k in ['rec_score', 'rec_scores', 'scores', 'score']:
            try:
                val = res[k]
                if val:
                    scores = val
                    break
            except Exception:
                pass

    # 3. 嘗試由物件屬性讀取
    if not texts:
        texts = getattr(res, 'rec_text', None) or getattr(res, 'rec_texts', None) or []
    if not scores:
        scores = getattr(res, 'rec_score', None) or getattr(res, 'rec_scores', None) or []

    if isinstance(texts, str):
        texts = [texts]
    if isinstance(scores, (int, float)):
        scores = [scores] * len(texts)
    elif not scores or len(scores) < len(texts):
        scores = list(scores) + [1.0] * (len(texts) - len(scores))

    return texts, scores

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
            outputs = ocr_engine.predict(image_np, 
                                        use_doc_orientation_classify=True, 
                                        use_textline_orientation=True,)
            for res in outputs:
                rec_texts, rec_scores = extract_ocr_texts_and_scores(res)
                for text, score in zip(rec_texts, rec_scores):
                    clean_text = str(text).strip()
                    if clean_text:
                        formatted_results.append({
                            "text": clean_text,
                            "confidence": float(score)
                        })
                        text_list.append(clean_text)
        else:
            ocr_result = ocr_engine.ocr(image_np, cls=True)
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
