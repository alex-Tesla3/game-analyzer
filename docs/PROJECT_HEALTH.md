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

- **数据需先抓取**：看板不再默认 mock；评论/指标来自 `/guide` 或 `/mvp` 抓取（Steam / TapTap / Google Play），或用户 CSV 导入
- **演示支付**：定价页扫码为模拟流程，非真实收款（见 `docs/COMMERCIAL_LAUNCH.md`）
- **web_app.py 单体路由**：部分 API 仍在 `web_app.py`，与 `routers/` 并存，后续可继续拆分

## GitHub 仓库

- **Canonical：** https://github.com/alex-Tesla3/game-analyzer  
- 日常 `git push origin main` 即可同步；CI 见 Actions  
- 若仍从 Hermes monorepo 子目录开发，见 `docs/GITHUB_PUBLISH.md` 导出说明
