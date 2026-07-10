import os
import sys

# 1. 讀取金鑰與儲存庫路徑
GH_PAT = os.environ.get("GH_PAT")
GH_REPO = os.environ.get("GH_REPO")

if not GH_PAT:
    raise RuntimeError("Error: GH_PAT environment variable is missing.")
if not GH_REPO:
    raise RuntimeError("Error: GH_REPO environment variable is missing.")

# 2. 複製私有儲存庫核心程式碼
# 使用 depth 1 加速複製
if not os.path.exists("./core"):
    clone_cmd = f"git clone --depth 1 https://oauth2:{GH_PAT}@github.com/{GH_REPO}.git ./core"
    exit_code = os.system(clone_cmd)
    if exit_code != 0:
        raise RuntimeError("Error: Failed to clone private repository.")
    # 複製成功後，立刻刪除 .git 目錄，防範 Token 與歷史紀錄殘留於容器中
    os.system("rm -rf ./core/.git")

# 3. 將私有程式碼目錄加入 Python 搜尋路徑中
sys.path.append(os.path.abspath("./core"))

# 4. 利用 uv 以 system 模式極速安裝專案依賴
if os.path.exists("./core/pyproject.toml"):
    os.system("uv pip install --system --no-cache ./core")
elif os.path.exists("./core/requirements.txt"):
    os.system("uv pip install --system --no-cache -r ./core/requirements.txt")

# 5. 確保導入相容的 spaces 與 gradio，並設定啟動檢測
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

import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from core.main import app as fastapi_app
from core.main import get_and_run_ocr

# 真正的 GPU 推理處理函數，並透過 @spaces.GPU 裝飾以通過 Hugging Face 檢測
@spaces.GPU
def run_gradio_ocr(image_path):
    if not image_path:
        return "Upload a Photo。"
    try:
        # 1. 驗證檔案大小（安全機制：限制最大處理檔案大小為 15 MB）
        file_size = os.path.getsize(image_path)
        if file_size > 15 * 1024 * 1024:
            return f"OCR Procssing Faile: File size ({file_size / (1024*1024):.1f} MB) Exceeds 15 MB Limit。"

        # 2. 以 Pillow 載入並進行單邊最大 2048 像素的縮放防禦（對齊 API 邏輯）
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        if max(width, height) > 2048:
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            print(f"💡 [Gradio] Auto-resized large image from {width}x{height} to {image.size[0]}x{image.size[1]}")

        # 3. 轉成 NumPy 陣列
        import numpy as np
        image_np = np.array(image)
        
        # 4. 執行推理
        ocr_result = get_and_run_ocr(image_np)
        
        # 5. 整理輸出格式以展示
        formatted_results = []
        if ocr_result and len(ocr_result) > 0 and ocr_result[0] is not None:
            res_item = ocr_result[0]
            if isinstance(res_item, dict):
                texts = res_item.get("rec_texts", [])
                for text in texts:
                    formatted_results.append(text)
            elif isinstance(res_item, list):
                for line in res_item:
                    points, (text, conf) = line
                    formatted_results.append(f"{text} (信賴度: {conf:.2f})")
        
        if not formatted_results:
            return "未偵測到任何文字。"
        return "\n".join(formatted_results)
    except Exception as e:
        return f"OCR 處理失敗：{str(e)}"

# 建立實用的 Gradio 圖片上傳辨識展示介面（使用 filepath 以支援檔案大小驗證）
with gr.Blocks() as demo:
    gr.Markdown("# 🔍 OCR Microservice GPU Demonstration Gateway")
    gr.Markdown("The space is not only a FastAPI backend microservice, but also a Gradio web interface for online OCR testing. You can upload images directly below to test the OCR function.")
    with gr.Row():
        with gr.Column():
            input_image = gr.Image(type="filepath", label="Upload Image for OCR")
            submit_btn = gr.Button("Start OCR Recognition", variant="primary")
        with gr.Column():
            output_text = gr.Textbox(label="OCR Result", interactive=False, lines=15)
    
    # 綁定事件並套用裝飾器函數
    submit_btn.click(fn=run_gradio_ocr, inputs=input_image, outputs=output_text)

# 6. 將 FastAPI 的核心路由合併到 Gradio 內建的 FastAPI 實例中
demo.app.include_router(fastapi_app.router)

# 7. 為 Gradio 的 FastAPI 實例啟用 CORS 跨域存取
demo.app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 8. 啟動 Gradio 服務
demo.launch(server_name="0.0.0.0", server_port=7860)
