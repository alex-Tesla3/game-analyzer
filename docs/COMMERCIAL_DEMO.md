# 商业化 Demo 剧本

面向制作人 / 策划 / 运营的产品演示与客户 POC 检查清单。约 **5–8 分钟**。

## 环境准备

```bash
cd game_analyzer
source .venv/bin/activate
export PYTHONPATH=src
./scripts/seed_demo.sh          # 可选：预置 CS2/Dota2 离线样本
uvicorn src.web_app:app --host 127.0.0.1 --port 8080 --reload
```

- 演示账号：`demo` / `demo123`
- 对外入口：http://127.0.0.1:8080 （`/` 产品首页，`/welcome` 自动跳转）
- 数据看板：http://127.0.0.1:8080/dashboard
- 支付为**模拟流程**，页面有明确「演示环境」提示

## 5 分钟演示路径

| 步骤 | 页面 | 话术要点 | 验收点 |
|------|------|----------|--------|
| 1 | `/` | 「3 分钟从游戏名到可执行报告，支持 Steam / TapTap / Google Play」 | 点击「一键体验 Demo」 |
| 2 | `/guide` | 「自动抓取公开评论 → AI/规则报告 → 自动归档」 | 状态显示 ✅，出现 P0/P1 行动清单 |
| 3 | `/work` | 「落地指导：分析→导出→分享→复测，进度一目了然」 | 工作流 4 步、行动清单可导出 |
| 4 | `/games/review#archives` | 「案例库沉淀，2 周后可一键复测对比口碑」 | 选中归档 → 生成分享链接 |
| 5 | `/team` | 「团队看共享报告，无需重复导出 PDF」 | 创建团队 / 邀请成员 |
| 6 | `/pricing` | 「按 API 配额订阅，当前为演示支付」 | 显示「本月 API 剩余 x / y」 |

## 各场景一句话价值

- **分析向导**：输入「原神」或 AppID，不用查数字 ID。
- **落地指导**：把报告变成 backlog，不是看完就关。
- **竞品工作台**：横向对比 + 六维评分 + AI 总结。
- **团队协作**：分享链接只读，适合策划/运营同步。
- **复测闭环**：好评率变化自动更新 P0 验证状态。

## 常见问题（客户 Q&A）

**Q：数据是真实的吗？**  
Steam / TapTap / Google Play 口碑来自公开评论（真数据）。看板高级漏斗/实时曲线在数据不足时标注 `simulated: true`。Owner DAU/收入需 CSV 导入。

**Q：没有 LLM 能用吗？**  
可以。未配置 LLM 时自动使用规则引擎生成报告，流程不变。

**Q：TapTap 中文名怎么搜？**  
分析向导选 TapTap 平台，输入「原神, 王者荣耀」即可。

**Q：支付是真的吗？**  
当前 POC 为模拟支付，扫码后点「支付完成」即可演示升级，无真实扣款。

**Q：API 配额怎么算？**  
按用户月度 `api_quota` 计数；管理员/坐席不限。Header 与定价页显示剩余次数。

## 演示前检查清单

- [ ] 服务已启动，`/api/health` 返回 200
- [ ] 使用 `demo` 账号登录成功
- [ ] （可选）已运行 `./scripts/seed_demo.sh` 加速向导
- [ ] 浏览器无痕窗口，避免旧 token 干扰
- [ ] 确认定价页显示「演示环境」横幅

## 自动化验证

```bash
# 单元测试（不含浏览器）
PYTHONPATH=src:. pytest tests/ -q -m "not browser"

# 浏览器 E2E（含商业化路径 test_00_commercial_flow）
PLAYWRIGHT_CHANNEL=chrome ./scripts/run_browser_e2e.sh
```

E2E 服务自动设置 `GA_E2E_DISABLE_LLM=1`、`GA_E2E_DISABLE_RATE_LIMIT=1`，避免 LLM 超时与 IP 限流干扰。

关键 E2E 用例：`test_commercial_welcome_to_work_flow`（welcome → guide → work）。

## 下一步（生产落地）

1. 配置 `SECRET_KEY`、关闭 `ALLOW_DEMO_ACCOUNTS`
2. 接入真实支付回调（替换 Mock 二维码）
3. 配置 LLM（OpenAI / Ollama）提升报告质量
4. 按客户平台启用 TapTap / Google Play 抓取凭证
