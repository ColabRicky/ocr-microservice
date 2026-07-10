# Hugging Face Space 部署引導程序 (Bootstrapper)

此目錄中的檔案專門用於將 `ocr-microservice` 部署至 **Hugging Face Space**。
採用此引導程序，能讓您的核心程式碼安全地保留在 GitHub 儲存庫中，並在 Hugging Face 容器啟動時動態下載並以 `uv` 極速載入運行。

## 部署步驟

### 1. 準備 GitHub 端的程式碼
1. 將您的 `ocr-microservice` 專案推送至 GitHub（可設為私有 Private Repository）。
2. 在您的 GitHub 帳號中，生成一個 **Personal Access Token (PAT)**：
   - 權限僅需具備讀取該儲存庫（`repo` 或 `read:packages`）的權限。

### 2. 在 Hugging Face 建立 Space
1. 登入 Hugging Face，點擊右上角的 **New Space**。
2. 填寫 Space 名稱，並將 **SDK** 選擇為 **Docker**。
3. 選擇 **Blank** 範本。
4. 為了保護程式碼，建議將 Space 隱私設為 **Private** (亦可為 Public，因為 Dockerfile 中不含任何原始碼或金鑰)。

### 3. 設定環境變數與金鑰 (Secrets)
1. 在建立好的 Space 頁面中，點擊頂部的 **Settings**。
2. 找到 **Variables and secrets** 區塊，點擊 **New secret** 新增以下兩個金鑰：
   - `GH_PAT`: 填入您剛才在 GitHub 生成的 Personal Access Token。
   - `GH_REPO`: 填入您的 GitHub 倉庫路徑，格式為 `用戶名/倉庫名` (例如：`rickyho/ocr-microservice`)。

### 4. 上傳部署引導檔案
1. 將本 `hf-deploy` 目錄下的所有檔案上傳到該 Hugging Face Space 儲存庫的**根目錄**：
   - `Dockerfile`
   - `app.py`
   - `README.md`
2. **請注意：不要上傳此目錄之外的核心程式碼（如外層的 `main.py`）**。Hugging Face 容器在啟動時會自動去 GitHub 下載它們。

上傳完成後，Hugging Face 會自動觸發 `docker build` 並利用 `uv` 安裝依賴，拉取您的 GitHub 專案代碼，最後啟動運作！
