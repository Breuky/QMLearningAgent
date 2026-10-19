# 期末复习智能体（Exam Review Agent）

面向大学期末复习的课程资料问答智能体：上传老师 PPT、教材 PDF、历年卷，系统解析并切块入库，回答问题时给出出处（文件 + 页码），资料不足时明确拒答。

当前目标课程：**《数据结构》**、**《操作系统》**。

> 当前状态：**可运行的 MVP 骨架（walking skeleton）**。
> 先跑通「上传 → 解析 → 切块 → 检索 → 带引用回答」的最小闭环，再用评测数据驱动检索与生成升级。

---

## 现在能做什么

- 创建课程，上传 `.pptx` / `.pdf` / `.txt` / `.md` 资料
- PPTX 提取文本框、表格（拍平成文本）和演讲者备注；PDF 提取文本层
- 按页切块，保留页码、标题、内容类型等元数据，写入 SQLite
- 中文 n-gram 关键词检索（MVP 基线，不依赖向量库）
- 回答附 `[n]` 引用，并校验引用编号；资料为空时拒答
- 配置 `DEEPSEEK_API_KEY` 后走真实 DeepSeek 调用；未配置时进入演示模式（返回检索摘录）
- 保存会话、消息、引用、延迟，提供反馈接口
- Streamlit 界面：传资料、看入库状态、提问看引用
- 检索评测脚本：计算 Recall@k

## 现在**不**做什么（刻意留给后续迭代）

- 没有 BGE-M3 向量检索、Chroma、BM25 混合检索和 reranker 模型（`app/retrieval/reranker.py` 是可替换的空实现）
- 没有 OCR：扫描版 PDF / 图片型 PPT 解析不出文字，会入库失败
- 不保留代码块的原始缩进与结构，图表内容也不会被理解
- 不保证操作系统计算题（调度、页面置换、死锁、磁盘调度）的数值正确性，MVP 只评价推理过程
- 没有流式输出、鉴权、多租户、真正的任务队列（`BackgroundTasks` 是进程内异步）
- 没有 LLM-as-judge、引用准确率/忠实度的自动打分

## 快速开始（本地）

要求 Python 3.11+。

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

启动 API：

```powershell
uvicorn app.main:app --reload
```

另开一个终端启动界面：

```powershell
.venv\Scripts\Activate.ps1
streamlit run ui/streamlit_app.py
```

- API 文档：http://localhost:8000/docs
- 界面：http://localhost:8501

不配置 API Key 也能完整跑通流程，回答会标注「演示模式」。

### Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- API：http://localhost:8000
- UI：http://localhost:8501

SQLite 文件位于宿主机 `./data/app.db`。

## 测试与检查

```powershell
pytest
ruff check .
```

检索评测（需先启动 API 并完成资料入库）：

```powershell
python scripts/run_eval.py --eval-file examples/eval_items.example.json --top-k 5
```

评测集格式、指标定义和人工打分模板见 [docs/eval.md](docs/eval.md)。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/courses` | 创建课程 |
| GET | `/api/courses` | 课程列表 |
| GET | `/api/courses/{course_id}/documents` | 课程下资料列表 |
| POST | `/api/courses/{course_id}/documents` | 上传资料（202，后台解析入库） |
| GET | `/api/documents/{document_id}` | 资料状态 |
| POST | `/api/chat` | 提问，返回答案、引用、意图、延迟 |
| POST | `/api/feedback` | 提交回答反馈 |

上传同一课程下内容完全相同的文件会复用已有资料（SHA-256 去重）。

## 目录结构

```
app/
  core/config.py          # 环境变量与路径
  db/                     # SQLAlchemy Base / Session
  models/entities.py      # Course, Document, Chunk, Job, ChatSession,
                          # Message, Feedback, EvalItem, EvalRun
  schemas/                # Pydantic 请求/响应模型
  ingestion/              # 解析、切块、入库流水线
  retrieval/              # 关键词检索、rerank 接口、引用校验
  agent/                  # 意图路由、提示词、LLM 调用
  evaluation/             # Recall@k 等指标
  api/routes/             # FastAPI 路由
ui/streamlit_app.py       # Streamlit 界面
scripts/                  # 入库 CLI、检索评测
tests/                    # pytest
docs/                     # 架构、Spike、评测文档
examples/                 # 评测集样例
```

架构与模块边界见 [docs/architecture.md](docs/architecture.md)；
第一周数据可行性验证见 [docs/spike.md](docs/spike.md)。

## 关键设计

- **SQLite 是 MVP 的范围选择**：嵌入式、零运维、单文件，适合单机低并发。出现多用户并发写入、多实例部署或需要全文检索能力时再迁移 MySQL。
- **关键词检索是基线，不是终点**：先建立可度量的 baseline，再引入 embedding + 混合检索，用评测集证明提升。
- **引用可校验**：模型输出中的 `[n]` 会与本次检索结果比对，越界引用会被移除；没有引用时自动追加来源列表。
- **可控降级**：外部 LLM 失败时回退到检索摘录，接口不中断；资料为空时拒答而不是编造。

## 数据与合规

- **不要提交原始课程资料**：`*.pptx`、`*.pdf` 等已加入 `.gitignore`，上传文件存放在 `data/`（也已忽略）。
- 历年卷用于出题与评测前需**人工核对答案**，不能直接采信模型生成的答案。
- 使用同学的真实提问做评测前需取得同意并匿名化。
- `.env` 含密钥，永不入库；仓库只保留 `.env.example`。
- 公开部署时不要提供原始资料下载，回答引用只展示必要片段。
