# 第 1 步：每日运行 + 微信提醒

每天自动：拉取最新估值 → 重算模拟定投持仓 → 检测状态迁移 → PushPlus 推送到微信。

## 工作原理

- **无状态**：每天用最新数据从 `start_date` 重算一遍模拟（引擎是向量化的，秒级），无需复杂增量状态机。
- **提醒**：① 状态迁移（低估↔正常↔高估）② 每日摘要（分位/动作/累计投入/盈亏）。
- **只模拟、不下单**：数据仅供参考，跟不跟、跟多少你自己决定。

## 部署步骤（GitHub Actions，免费）

1. 把整个 `fund-dca-agent` 目录推到一个 **GitHub 私有仓库**。

2. **改 `settings.json`**：
   - `start_date`：你"开始跟投"的日期（从这天开始模拟）
   - `track`：跟踪的指数（name/symbol/config 三件套）
   - `notify`：开关状态迁移提醒 / 每日摘要

3. **改金额**：`config-hs300.json` 等里的 `amount` 是示例（300/100/0 元），改成你自己的金额。

4. **配置 PushPlus Token**：
   - 打开 https://www.pushplus.plus ，微信扫码登录，复制你的 `token`
   - 在 GitHub 仓库 `Settings → Secrets and variables → Actions → New repository secret`
   - Name 填 `PUSHPLUS_TOKEN`，Value 填 token

5. **启用 Actions**：仓库 `Actions` 页签 → 启用 `daily-dca` 工作流。手动点一次 "Run workflow" 测试。

6. 之后每天（工作日）北京时间 18:30 自动运行并推送。

## 本地测试

```bash
# 在 step1-monitor-fork 目录下，venv 里
python daily.py          # 无 token：打印消息预览
PUSHPLUS_TOKEN=你的token python daily.py   # 真实推送
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `settings.json` | 跟踪标的、开始日期、通知开关 |
| `state.json` | 上次推送的数据日期（避免节假日重复推送，自动更新）|
| `trade_log.jsonl` | 每日买卖记录（追加，自动提交）|
| `config-hs300.json` 等 | 各指数策略配置（金额可自改）|
| `daily.py` | 每日运行主脚本 |
| `notify.py` | PushPlus 推送封装 |

## 已知限制

- 节假日：GitHub 定时可能照常触发，但脚本检测"数据没更新"就跳过推送。
- 改配置会按新配置重算整个历史（"what-if"语义），不是逐日固化。
- 数据源：legulegu（估值）+ 新浪（价格），免费，偶有限流。
