# fund-dca-agent 智能定投智能体

> 目标：一个每天自动运行的智能体，抓取估值/趋势/情绪等因子，判断指数基金定投节奏
> （低估加倍、高估放缓/停买、高位分批止盈），并给出可解释的当日投资策略。

## 核心原则

1. **决策由确定性规则引擎出，LLM 只做解释和资讯整合**（可回测、可留痕、可复现）。
2. **判断贵贱用估值分位（PE/PB 历史百分位），不用价格/点位**。
3. **只提醒、不自动下单**，交易由人最终确认。

## 定投标的（初步）

- 纳指 100（Nasdaq-100）
- 标普 500（S&P 500）
- 国内宽基：沪深 300 等

## 四步路线图

| 步骤 | 目录 | 目标 | 状态 |
|---|---|---|---|
| 第 0 步 | `step0-backtest-validate/` | 用现成工具回测验证「估值分位定投 vs 无脑定投」 | ✅ 完成（见 CONCLUSION.md）|
| 第 1 步 | `step1-monitor-fork/` | 每日运行 + PushPlus 微信提醒（GitHub Actions）| ✅ 完成（见 README.md）|
| 第 2 步 | `step2-strategy-core/` | 估值温度表策略核心 + 回测引擎 + 全参数标定 | ✅ 完成（见 DESIGN.md / CALIBRATION.md）|
| 第 3 步 | `step3-llm-copilot/` | LLM 副驾（策略解释 + 资讯整合） | ⏳ 待开始 |

## 关键参考资料

- 数据/因子：akshare（https://github.com/akfamily/akshare）
- 运行外壳：Koko-ry/fund-monitor（https://github.com/Koko-ry/fund-monitor）
- 回测工具：SunshowerC/fund-strategy（https://github.com/SunshowerC/fund-strategy）
- LLM 多 agent 架构：virattt/ai-hedge-fund（https://github.com/virattt/ai-hedge-fund）
