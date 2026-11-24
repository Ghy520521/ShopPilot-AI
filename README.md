# ShopPilot AI — 智能电商与 AI 售后工单平台

传统 Python 后端 + AI 业务集成的综合项目：在商品 / 购物车 / 订单 / 库存的完整电商链路上，
叠加一条「自然语言 → 受约束查询计划 → 结构化过滤 + 语义召回融合」的 AI 工单检索链路。

> 本仓库是可运行的工程骨架与核心链路实现；本地测试使用 SQLite + 内存缓存，
> 无需 Postgres / Redis / 外部 LLM 即可跑通全部测试。

## 1. 功能模块

| 模块 | 实现内容 |
|---|---|
| 用户与权限 | 注册、bcrypt 密码哈希、JWT 签发 / 校验、admin / user 角色 |
| 商品系统 | 分类、商品、SKU、价格、库存；列表分页、详情 |
| 购物车 | 增删改查、同商品数量累加 |
| 订单 | 事务建单、订单商品快照、订单列表 / 详情、归属校验 |
| 库存控制 | 条件更新扣减（`WHERE stock >= qty`），库存不足整体回滚；预留 PG 行级锁方案 |
| 售后工单 | 创建、分配、状态机（open → in_progress → resolved → closed）、操作日志 |
| AI 工单检索 | LLM 输出受约束 `SearchPlan`，白名单构造 SQLAlchemy，结构化过滤 + 语义召回融合分页 |
| 工程化 | 缓存抽象（Redis / 内存降级）、Celery 异步任务、pytest、Docker Compose |

## 2. 技术栈

- Web：FastAPI、Pydantic v2、SQLAlchemy 2.0
- 数据库：PostgreSQL（生产 / Docker），SQLite（本地测试）；生产可替换为 pgvector 列
- 缓存 / 队列：Redis（可选，缺失自动降级）、Celery
- 鉴权：python-jose(JWT) + bcrypt
- 测试：pytest + FastAPI TestClient + httpx

## 3. 目录结构

```
shoppilot-ai/
├── app/
│   ├── main.py                  # FastAPI 入口
│   ├── core/                    # 配置、数据库、安全、缓存、embedding、LLM 适配、依赖
│   ├── models/                  # ORM 模型
│   ├── schemas/                 # Pydantic 请求 / 响应（含 SearchPlan）
│   ├── services/                # 业务逻辑：auth / inventory / order / ticket / search
│   ├── api/                     # 路由：auth / products / cart / orders / tickets
│   └── workers/celery_app.py    # 异步工单分析任务
├── scripts/eval_retrieval.py    # Recall@K / MRR / nDCG@K 离线评测脚手架
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 4. 快速启动

### 本地（零外部依赖）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# 前端控制台：http://localhost:8000/
# Swagger 交互式文档：http://localhost:8000/docs
```

### 前端控制台

`app/frontend/index.html` 是零构建的原生 JS 单页，由 FastAPI 直接托管在根路径 `/`，
覆盖：注册/登录、商品浏览与加购、购物车下单（自动生成幂等键）、我的订单、
工单提交与状态流转、AI 自然语言检索（展示解析计划与两路命中数）。
管理员登录后才显示「新建分类 / 商品」面板。JWT 存于 localStorage，401 自动回到登录页。

### Docker Compose（Postgres + Redis + API + Worker）

```bash
docker compose up --build
```

## 5. API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/products` | 商品列表（分页、分类筛选，带缓存） |
| GET | `/api/products/categories` | 分类列表 |
| POST | `/api/products/categories` | 管理员创建分类 |
| GET | `/api/products/{id}` | 商品详情 |
| POST | `/api/products` | 管理员创建商品 |
| GET / POST / DELETE | `/api/cart` | 购物车查看 / 加购 / 删除 |
| POST | `/api/orders` | 下单（幂等键） |
| GET | `/api/orders` / `/api/orders/{id}` | 订单列表 / 详情 |
| POST | `/api/tickets` | 创建工单 |
| GET | `/api/tickets` | 工单列表（普通用户仅见本人） |
| POST | `/api/tickets/{id}/assign` | 管理员指派 |
| POST | `/api/tickets/{id}/transition` | 状态机流转 |
| POST | `/api/tickets/search` | 自然语言检索工单 |

### 自然语言检索示例

```bash
curl -X POST http://localhost:8000/api/tickets/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question":"查一下最近7天还没有解决的高优先级物流工单","page":1,"page_size":10}'
```

响应中 `debug` 字段会同时给出 `structured_count`（结构化命中）、`semantic_count`（语义命中）、
`merged_count`（融合去重后总数）与解析出的 `SearchPlan`，便于调试与复盘。

## 6. 核心设计（可写进简历的工程点）

1. **事务一致性**：建单与扣库存放在同一数据库事务内，任一商品库存不足即整体回滚，
   避免「订单成功但库存没扣」或「扣了库存但订单没落库」。
2. **并发库存扣减**：采用条件更新 `UPDATE products SET stock = stock - :q WHERE id = :id AND stock >= :q`，
   通过 `rowcount` 判断成败，避免先查后扣的竞态；PostgreSQL 生产方案可换 `SELECT ... FOR UPDATE` 行级锁。
3. **幂等下单**：客户端携带 `idempotency_key`，服务端唯一约束 + 查重，重试直接返回首单，不重复扣库存。
4. **AI 检索的职责边界（重点）**：LLM 只输出 Pydantic 约束的 `SearchPlan`（枚举状态、优先级、
   时间范围、白名单关键词、订单号、语义查询串），**不生成也不接触 SQL**；后端用白名单字段
   显式构造 SQLAlchemy 查询，并先执行权限过滤（普通用户只检索本人工单）。
5. **双路融合召回**：结构化路负责精确筛选（状态 / 优先级 / 时间 / 订单号 / 关键词），
   语义路负责召回相似历史工单，合并去重后分页返回。
6. **缓存**：热门商品列表走缓存，写操作后主动失效对应前缀，避免脏读；Redis 不可用时自动降级为内存缓存。
7. **异步队列**：耗时的工单 AI 分析（分类 / 相似提醒）交给 Celery，不阻塞请求链路。

## 7. 测试

```bash
pytest app/tests -q
```

覆盖：注册唯一性 / 登录鉴权、事务扣库存与幂等、库存不足回滚、工单状态机与非法流转拒绝、
NL 检索的结构化过滤 / 权限隔离 / 语义召回 / SearchPlan 无原始 SQL 字段的安全边界。

## 8. 当前边界与生产化路线图（诚实说明）

- `EMBEDDING_PROVIDER=local` 是确定性哈希词袋向量、`LLM_PROVIDER=mock` 是规则解析器，
  仅用于开发与测试；生产替换为真实 embedding（bge / OpenAI）与大模型结构化输出，
  并把工单 `embedding` 列迁移为 pgvector 的 `vector` 类型。
- 支付为模拟支付，未接真实支付平台；金额字段生产应使用 `Numeric` 替代 `Float`。
- 生产数据库迁移请引入 Alembic；当前 `init_db()` 仅用于开发自动建表。
- 检索上线前需自建标注集，用 `scripts/eval_retrieval.py` 的 Recall@10 / MRR / nDCG@10
  对比纯结构化、纯语义与融合策略，并统计结构化解析准确率与检索延迟，指标以真实实验结果为准。
