# 部署规划文档：复旦管院知识库系统 (FDSM Knowledge Base)

## 1. 架构概览

我们将采用 **前后端分离** 的部署策略：

*   **前端 (Frontend)**: 部署在 **Vercel**。
    *   **理由**: 针对 React/Vite 极度优化，免费额度够用，自动 CI/CD。
*   **后端 (Backend)**: 部署在 **Render** (Web Service)。
    *   **理由**: 支持 Python 环境，**最关键的是支持挂载 Persistent Disk (持久化磁盘)**。
    *   **存储**: 你的 SQLite 数据库 (`fudan_knowledge_base.db`) 和 FAISS 索引 (`faiss_index/`) 必须放在 Render 的磁盘上，否则每次重启服务数据都会丢失。

---

## 2. 关键改造步骤 (Before Deployment)

在上传代码之前，必须对代码进行“云原生”改造，核心是**去敏感化**和**路径适配**。

### A. 后端改造 (`backend/`)

1.  **移除硬编码 API Key**:
    *   目前 `main.py` 里直接写了 `GOOGLE_API_KEY = "..."`。
    *   **动作**: 改为 `os.environ.get("GOOGLE_API_KEY")`。本地开发使用 `.env` 文件。

2.  **路径适配 (持久化存储)**:
    *   Render 的磁盘通常挂载在 `/var/lib/data` 或类似路径（或者你自定义的路径）。
    *   **动作**: 修改 `main.py` 中的路径配置。
        *   如果不检测到云环境，用本地路径。
        *   如果检测到云环境 (e.g. `RENDER` env var)，指向挂载盘路径 (e.g., `/etc/fdsm_data/`).
        *   **注意**: 数据库文件和 FAISS 索引必须移到这个挂载目录。

3.  **CORS 配置**:
    *   目前是 `allow_origins=["*"]`，生产环境建议改为前端的 Vercel 域名（部署后再填）。

4.  **依赖管理**:
    *   确保 `requirements.txt` 包含所有库 (`google-genai`, `langchain`, `fastapi`, `uvicorn`, `pydantic` 等)。
    *   **动作**: 我会运行 `pip freeze` 生成标准文件。

### B. 前端改造 (`frontend/`)

1.  **API 地址动态化**:
    *   目前 `api.js` 硬编码了 `http://localhost:8000/api`。
    *   **动作**: 使用 Vite 的环境变量 `import.meta.env.VITE_API_BASE_URL`。
    *   本地开发用 `.env.development` (`localhost:8000`)。
    *   生产环境 (Vercel) 设置环境变量指向 Render 的后端地址。

---

## 3. Render 后端部署流程

1.  **代码库**: 将项目推送到 GitHub。
2.  **创建 Web Service**:
    *   Environment: `Python 3`
    *   Build Command: `pip install -r requirements.txt`
    *   Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port 10000`
3.  **环境变量 (Environment Variables)**:
    *   `PYTHON_VERSION`: `3.11.0` (推荐)
    *   `GOOGLE_API_KEY`: **[在此处填入你的 Key]**
    *   `IS_CLOUD`: `true` (用于代码识别环境)
4.  **挂载磁盘 (Disks)**:
    *   Render 控制台 -> Disks -> Add Disk。
    *   **Mount Path**: `/etc/fdsm_data` (举例)。
    *   **Size**: 1GB (足够了)。
5.  **数据迁移 (关键)**:
    *   部署首次启动后，数据库是空的。
    *   **动作**: 需要写一个脚本或通过 SSH (Render支持) 把本地的 `fudan_knowledge_base.db` 和 `faiss_index` 上传到 Render 的 `/etc/fdsm_data` 目录。或者在启动脚本里加一个逻辑：如果磁盘为空，从代码仓复制一份初始数据过去。

---

## 4. Vercel 前端部署流程

1.  **导入项目**: 在 Vercel 面板导入 GitHub 仓库。
2.  **设置 Root Directory**: 选择 `frontend` 目录。
3.  **环境变量**:
    *   `VITE_API_BASE_URL`: 填入 Render 后端的 URL (e.g., `https://fdsm-backend.onrender.com/api`)。
4.  **部署**: 点击 Deploy。

---

## 5. 待确认事项

1.  **Render Disk**: 你现在的 Render 账号是否已经创建好了 Disk？如果没有，我们稍后在代码里先做好路径兼容。
2.  **数据同步**: 你是希望我写一个脚本让服务器启动时自动把 Repo 里的数据复制到磁盘（最简单，适合只读数据），还是你打算手动 SSH 上传？
    *   *建议*: 鉴于你可能有新数据，我建议在代码里加一段：“**启动时检查挂载盘是否有数据，没有则从项目目录复制一份过去**”。这样第一次部署最省心。

请确认以上规划，确认无误后回复“开始”，我将执行代码改造。
