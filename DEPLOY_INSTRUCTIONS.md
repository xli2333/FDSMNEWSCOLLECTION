# 复旦管院 AI 知识库系统：云端部署操作手册 (Render + Vercel)

本指南将指导您将本地开发完成的全栈应用部署到云端，实现全球访问。

---

## 🛠️ 第一部分：准备工作 (本地)

确保您本地的代码已经成功推送到 GitHub（刚才我们已经完成了这一步）。
GitHub 仓库地址: `https://github.com/xli2333/FDSMNEWSCOLLECTION`

---

## 🚀 第二部分：后端部署 (Render)

Render 用于托管 Python 后端服务，并提供持久化磁盘来存储我们的数据库。

### 1. 创建 Web Service
1.  登录 [Render Dashboard](https://dashboard.render.com/)。
2.  点击右上角 **New +** -> **Web Service**。
3.  选择 **Build and deploy from a Git repository**，点击 **Next**。
4.  在列表中找到并连接 `FDSMNEWSCOLLECTION` 仓库。

### 2. 配置服务参数
在配置页面填写以下信息：
*   **Name**: `fdsm-backend` (或您喜欢的名字)
*   **Region**: `Singapore` (推荐，访问国内较快) 或 `Oregon`。
*   **Branch**: `master`
*   **Root Directory**: `.` (保持默认，留空)
*   **Runtime**: **Python 3**
*   **Build Command**: `pip install -r requirements.txt`
*   **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port 10000`
*   **Instance Type**: `Free` (免费版) 或 `Starter` ($7/月，推荐，如果不挂磁盘只能用Starter及以上，免费版**不支持**挂载磁盘)。
    *   **注意**: 如果您想用持久化存储(Disk)，**必须**升级到付费版 Instance。如果是纯演示不想花钱，数据每次重启会丢失，且无法上传大文件。**本指南假设您使用付费版以挂载磁盘。**

### 3. 设置环境变量 (Environment Variables)
向下滚动找到 **Environment Variables**，添加以下键值对：
1.  `PYTHON_VERSION`: `3.11.0`
2.  `GOOGLE_API_KEY`: `[填入您的 Google Gemini API Key]` (以 AIza 开头的那串字符)
3.  `RENDER`: `true`

### 4. 挂载持久化磁盘 (Persistent Disk)
**这是数据不丢失的关键。**
1.  点击左侧菜单的 **Disks** -> **New Disk**。
2.  **Name**: `fdsm_data`
3.  **Size**: `1 GB` (足够了)
4.  **Service**: 选择刚才创建的 `fdsm-backend` 服务。
5.  **Mount Path**: `/etc/fdsm_data` (**必须完全一致**，代码里写死的是这个路径)。
6.  点击 **Create Disk**。

### 5. 部署服务
点击 **Create Web Service**。等待几分钟，直到看到绿色勾选 ✅ **Live**。
复制页面左上角的 URL (例如: `https://fdsm-backend-xxxx.onrender.com`)，这是您的**后端地址**。

---

## 📦 第三部分：数据上传 (最关键步骤)

因为 GitHub 限制大文件，我们的数据库 (`fudan_knowledge_base.db`) 和向量索引 (`faiss_index/`) 并没有传上去。现在的云端服务是一个空壳。我们需要把本地数据“搬”到 Render 的磁盘里。

### 方法：使用 Magic Wormhole (最简单，无需配置 SSH)

我们将利用 Render 的 **Shell** 功能，通过命令行工具直接传输文件。

#### 步骤 A: 在 Render 端接收
1.  在 Render Dashboard，进入 `fdsm-backend` 服务页面。
2.  点击 **Shell** 标签页（网页版终端）。
3.  安装传输工具 `magic-wormhole`：
    ```bash
    pip install magic-wormhole
    ```
4.  进入挂载盘目录：
    ```bash
    cd /etc/fdsm_data
    ```
5.  **准备接收数据库文件**:
    ```bash
    wormhole receive
    ```
    *(此时屏幕会显示一串像 `7-guitar-ist` 这样的代码，**不要关闭窗口**，复制这串代码)*

#### 步骤 B: 在本地端发送
1.  打开您本地电脑的终端 (PowerShell 或 CMD)。
2.  安装传输工具 (如果您本地没有 Python 环境，请先安装 Python):
    ```bash
    pip install magic-wormhole
    ```
3.  进入项目根目录：
    ```bash
    cd C:\Users\LXG\fdsmarticles
    ```
4.  **发送数据库文件**:
    ```bash
    wormhole send fudan_knowledge_base.db
    ```
5.  **输入代码**: 当提示 `Enter receive wormhole code:` 时，粘贴刚才 Render 上显示的那串代码（例如 `7-guitar-ist`），回车。
6.  **确认**: 双方都会显示确认提示，输入 `y` 或直接回车确认。等待传输完成。

#### 步骤 C: 上传 FAISS 索引 (文件夹)
由于 Wormhole 只能传单个文件，我们需要先打包本地的 `faiss_index` 文件夹。

1.  **本地**: 将 `faiss_index` 文件夹压缩为 `faiss_index.zip`。
2.  **Render (Shell)**: 再次运行 `wormhole receive`，获取新代码。
3.  **本地**: 运行 `wormhole send faiss_index.zip`，输入代码传输。
4.  **Render (Shell)**: 传输完成后，解压文件：
    ```bash
    apt-get update && apt-get install -y unzip  # 如果没有 unzip 命令
    unzip faiss_index.zip
    rm faiss_index.zip
    ```

#### 步骤 D: 验证
在 Render Shell 中输入 `ls -F /etc/fdsm_data/`，您应该能看到：
*   `fudan_knowledge_base.db`
*   `faiss_index/`

**重启服务**: 为了让后端加载新数据，点击 Dashboard 右上角的 **Manual Deploy** -> **Clear build cache & deploy** (或者直接在 Shell 里 kill 掉进程让它重启，但最稳妥是点按钮重启)。

---

## 🌐 第四部分：前端部署 (Vercel)

前端部署非常简单。

### 1. 导入项目
1.  登录 [Vercel](https://vercel.com/)。
2.  点击 **Add New...** -> **Project**。
3.  找到 `FDSMNEWSCOLLECTION`，点击 **Import**。

### 2. 配置参数
1.  **Framework Preset**: Vercel 会自动识别为 `Vite`，无需修改。
2.  **Root Directory**: 点击 **Edit**，选择 `frontend` 文件夹。(**这一步很关键！**)

### 3. 环境变量
展开 **Environment Variables**，添加：
*   **Key**: `VITE_API_BASE_URL`
*   **Value**: `https://fdsm-backend-xxxx.onrender.com/api` (填入您在第二部分获得的 Render 后端地址，注意末尾加上 `/api`，且不要有斜杠 `/` 在最后)。

### 4. 部署
点击 **Deploy**。等待几十秒，您的网站就上线了！

---

## 🎉 验收

访问 Vercel 生成的域名 (例如 `https://fdsm-news-collection.vercel.app`)。
1.  **测试搜索**: 输入“复旦”，看看是否有结果。
2.  **测试时光机**: 点击时光机，输入日期，看看是否生成图片。
3.  **测试总结**: 点击文章，看看是否生成 AI 导读。

如果一切正常，恭喜您！
