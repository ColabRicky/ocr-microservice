---
title: Ocr Microservice
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
python_version: "3.12"
---

# 🔍 OCR Microservice - Hugging Face Deployment Shell

本資料夾包含用於部署至 Hugging Face Gradio Space (免費版) 的安全中介引導層。

## 🚀 部署步驟

1. 在 Hugging Face 建立一個 **Gradio** 空間 (Space) (此為免費 SDK 類型)。
2. 在 Space 的 **Settings -> Variables and Secrets** 新增以下機密 (Secrets)：
   - `GH_PAT`：您的 GitHub Personal Access Token (需有存取私有庫的權限)。
   - `GH_REPO`：您的 GitHub 專案倉庫路徑，例如 `GitHubUserName/GitRepoName` (如 `rickyho/ocr-microservice`)。
3. 將本 `hf-deploy` 目錄下的所有檔案推送或上傳至 Hugging Face Space 的 Git 倉庫即可。
