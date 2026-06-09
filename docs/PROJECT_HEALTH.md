# 项目健康检查清单

面向本地开发与上线前自检。

## 已落实（2026-06）

| 项 | 说明 |
|----|------|
| 统一鉴权 | `src/deps.py` 的 `get_current_user` 同时支持 `Depends`、Bearer、`?token=` |
| Bearer 桥接 | `BearerTokenQueryBridgeMiddleware` 为旧接口补全 query token |
| 评论/指标数据 | `restrict_catalog_to_dataset` + 无效 session 筛选回退 |
| 会话时长 | 开发默认 8h；生产默认 2h；可用 `ACCESS_TOKEN_EXPIRE_MINUTES` 覆盖 |
| 前端 | `authFetch`、`CatalogFilters`、数据来源横幅（`DataProvenance`） |

## 上线前必做

1. `APP_ENV=production` + `SECRET_KEY`（`openssl rand -hex 32`）
2. 关闭或限制 Demo：`ALLOW_DEMO_ACCOUNTS=false`
3. 配置真实支付与 Webhook（见 `docs/COMMERCIAL_LAUNCH.md`）
4. 将稳定 Demo URL 写入 README / 简历材料

## 已知限制

- **演示 vs 真数据**：未跑一键采集时，评论/指标为 mock；Steam 真数据需 `/guide` 采集
- **web_app.py 单体路由**：部分 API 仍在 `web_app.py`，与 `routers/` 并存，后续可继续拆分
- **双仓库**：开发目录 `Hermes-Agent/game_analyzer` 与导出目录 `~/Projects/game-analyzer` 需手动同步

## 恢复源码

若 `src/*.py` 误删，可从备份同步：

```bash
rsync -a --exclude='.venv' --exclude='__pycache__' \
  ~/Projects/game-analyzer/ /Users/wly/Hermes-Agent/game_analyzer/
```

然后重新应用本仓库中的鉴权与数据修复提交。
