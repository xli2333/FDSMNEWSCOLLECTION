# RAG 与 检索系统开发待办清单 (TODO List)

## 1. 环境准备与配置 (Environment Setup)
- [x] **安装依赖库**:
    - `langchain` / `langchain-google-genai`: 用于 RAG 流程和模型调用。
    - `faiss-cpu`: 用于本地向量存储 (替代 ChromaDB)。
    - `fastapi` / `uvicorn`: 后端 API 服务。
    - `sqlite3`: 关系型数据库。
- [x] **API 配置**:
    - 设置 Google Gemini API Key。
    - **生成模型**: `gemini-2.5-pro` (用于意图提取/查询扩展)。
    - **Embedding 模型**: `models/gemini-embedding-exp-03-07`。

## 2. 工具一：向量检索系统 (Backend API - Vector Search)

### 2.1 数据预处理与切片 (Data Slicing)
- [x] **读取数据**: 从 `fudan_knowledge_base.db` 读取所有文章。
- [x] **制定切片策略 (Chunking Strategy)**:
    - 采用 `RecursiveCharacterTextSplitter`。
    - **Chunk Size**: 800 字符。
    - **Chunk Overlap**: 100 字符。
    - **Metadata**: 保留 `article_id`, `title`, `publish_date`, `source`。
- [x] **向量化与存储 (Embedding & Storage)**:
    - 使用 Gemini Embedding 模型将切片转换为向量。
    - 将向量存入本地 `FAISS` 索引 (`faiss_index/`)。

### 2.2 检索逻辑实现 (Retrieval Logic)
- [x] **意图提取 (Intent Extraction)**:
    - 实现 `extract_core_query`: 从用户自然语言中提取核心搜索词，去除噪音。
- [x] **查询增强 (Query Expansion)**:
    - 实现 `expand_query`: 生成 2-3 个严格同义词/具体变体。
- [x] **多路召回与融合 (Multi-Query Retrieval & Fusion)**:
    - **独立搜索**: 核心词与联想词分别进行向量检索。
    - **加权排序**: 
        - 优先核心词召回 (Weight 1.0)。
        - 联想词召回降权 (Weight 0.85)。
        - 频率奖励 (Frequency Boost)。
    - **阈值过滤**: `MIN_RELEVANCE_THRESHOLD = 0.55`。
- [x] **结果回溯**:
    - `/api/article/{article_id}` 接口：返回完整文章内容。

## 3. 工具二：条件检索系统 (Backend API - Conditional Search)

### 3.1 结构化查询构建 (Structured Query Builder)
- [x] **开发 SQL 生成器**:
    - 实现 `/api/sql_search` 接口。
    - 支持条件：**时间范围** (Start/End Date)、**关键词匹配** (LIKE)、**来源筛选** (News/Wechat)。
- [x] **执行与优化**:
    - 使用 SQLite 进行高效查询。

## 4. 前端交互界面 (Frontend UI - Planned: React)

### 4.1 界面框架搭建
- [ ] **项目初始化**: 创建 React 项目 (e.g., `create-react-app` or `vite`).
- [ ] **侧边栏/导航 (Navigation)**:
    - 检索模式切换 (智能问答 / 高级搜索)。
    - 筛选器组件 (Date Picker, Source Dropdown)。
- [ ] **主区域 (Main Area)**:
    - 搜索框组件 (Search Bar)。
    - 结果展示列表 (Result List Cards)。

### 4.2 结果展示与交互
- [ ] **列表视图**:
    - 展示标题、摘要、来源、日期、匹配度分数。
- [ ] **文章详情页 (Article Detail)**:
    - 点击标题弹出模态框或跳转详情页。
    - 展示完整内容和原始链接。

## 5. 测试与验证 (Testing)
- [x] **API 测试**: 通过 curl 验证所有后端接口功能正常。
- [x] **召回策略优化**: 已调整 Temperature (0.1) 和 Prompt，解决关键词发散问题。
- [ ] **集成测试**: 前后端联调。