# PostgreSQL 迁移指南

Game Analyzer 默认使用 **SQLite**（`data/game_analyzer.db`）。试点/生产多实例部署请使用 **PostgreSQL**。

## 快速启动

### 方式 A（推荐）：只起 Postgres，应用在宿主机跑

避免 Docker 构建应用镜像时 `apt-get` 403 等问题：

```bash
cd /Users/wly/Hermes-Agent/game_analyzer   # 你的项目路径
source .venv/bin/activate
pip install -r requirements.txt

chmod +x scripts/dev_postgres.sh
./scripts/dev_postgres.sh
```

另开终端检查：

```bash
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool
# "database_type": "postgresql"
```

可选迁移旧 SQLite：`RUN_MIGRATE=1 ./scripts/dev_postgres.sh`

### 方式 B：Postgres + 应用都在 Docker

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
docker compose -f docker-compose.postgres.yml up -d --build
```

若构建失败（Debian 源 403），请改用 **方式 A**。

默认连接串（容器内）：

`postgresql://game:game@postgres:5432/game_analyzer`

## 环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | **推荐**。`postgresql://user:pass@host:5432/dbname` |
| `DATABASE_TYPE` | 可选强制 `postgresql` / `sqlite`（无 URL 时） |

设置 `DATABASE_URL` 后**无需**改 `config/config.json`；未设置时仍用 SQLite。

`.env.example` 片段：

```bash
DATABASE_URL=postgresql://game:game@localhost:5432/game_analyzer
```

## 从 SQLite 迁移数据

1. 确保 Postgres 已启动且 `DATABASE_URL` 已 export  
2. 运行（会 `init_database()` 建表后按表拷贝）：

```bash
export DATABASE_URL=postgresql://game:game@localhost:5432/game_analyzer
python scripts/migrate_sqlite_to_postgres.py

# 仅查看将迁移的表
python scripts/migrate_sqlite_to_postgres.py --dry-run
```

3. 用新库启动应用：

```bash
export DATABASE_URL=postgresql://...
./scripts/dev.sh
```

**说明：** `ON CONFLICT DO NOTHING` 可重复执行；主键冲突行会跳过。迁移后 MVP 文件、导入 CSV 仍在 `data/` 目录，与 DB 分离。

## 实现要点

| 模块 | 作用 |
|------|------|
| `src/db_dialect.py` | 解析 `DATABASE_URL`、`?` → `%s` 占位符适配 |
| `src/db_schema_postgres.py` | Postgres DDL（与 SQLite `init_database` 对齐） |
| `database.py` | `CompatConnection` 包装；`db_type=postgresql` 时走 PG 建表 |

## Render / Railway

在平台环境变量添加：

```bash
DATABASE_URL=<托管 Postgres 连接串>
APP_ENV=production
ALLOW_DEMO_ACCOUNTS=false
```

Render：新建 **PostgreSQL** 实例 → 复制 **Internal Database URL** 到 Web Service 的 `DATABASE_URL`。

**不要**再把 SQLite 文件当作唯一持久化层；可保留 `data/` 卷存放 MVP 产物与上传文件。

## 验证

```bash
./scripts/run_tests.sh tests/test_db_dialect.py -q
curl -s http://127.0.0.1:8080/api/health | jq '.database_type'
./scripts/validate_production_env.sh
```

## 限制与后续

- 当前为 **单库多租户**（`username` 列隔离），非 schema-per-tenant。  
- 连接池：每请求新建连接（POC）；高并发可接 PgBouncer 或 SQLAlchemy pool。  
- 全文检索、JSON 列优化、Alembic 版本迁移可按客户规模再加。

参见 [COMMERCIAL_LAUNCH.md](./COMMERCIAL_LAUNCH.md) 试点检查项。
