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
clone_cmd = f"git clone --depth 1 https://oauth2:{GH_PAT}@github.com/{GH_REPO}.git ./core"
exit_code = os.system(clone_cmd)
if exit_code != 0:
    raise RuntimeError("Error: Failed to clone private repository.")

# 3. 複製成功後，立刻刪除 .git 目錄，防範 Token 與歷史紀錄殘留於容器中
os.system("rm -rf ./core/.git")

# 4. 將私有程式碼目錄加入 Python 搜尋路徑中
sys.path.append(os.path.abspath("./core"))

# 5. 利用 uv 以 system 模式極速安裝專案依賴（補充安裝 pyproject.toml 宣告的套件）
if os.path.exists("./core/pyproject.toml"):
    os.system("uv pip install --system --no-cache ./core")
elif os.path.exists("./core/requirements.txt"):
    os.system("uv pip install --system --no-cache -r ./core/requirements.txt")

# 6. 啟動 uvicorn 服務
# 在 Docker Space 中，我們必須手動執行 uvicorn 監聽 7860 埠口
import uvicorn

if __name__ == "__main__":
    # 指向 core 目錄下的 main:app
    uvicorn.run("core.main:app", host="0.0.0.0", port=7860, reload=False)
