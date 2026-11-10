# 可调参数

以下参数可在 `config/strategy.json` 中修改，或用自然语言让 Codex 修改。

## 策略可调参数（≤5）

- 基础申购金额（weekly_base_amount）：当前值 1000.0，范围 100~10000
- 每年增幅（growth_rate）：当前值 0.07，范围 0.0~0.2
- 触发赎回分位（trigger_percentile）：当前值 70.0%，范围 70~100
- 每日赎回比例（daily_redeem_ratio）：当前值 0.01，范围 0.001~0.05
- 现金利率（cash_interest_rate）：当前值 0.014，范围 0.0~0.05

## 资金参数（不计入≤5，可调整）

- 初始资金（initial_capital）：当前值 50000.0，范围 0~1000000
- 定期新增金额（extra_contribution_amount）：当前值 5000.0，范围 0~100000
- 定期新增频率（extra_contribution_freq）：当前值 每月，范围 每周/每月/每季/每年

## 参数修改示例

```bash
python scripts/params.py --config config/strategy.json --set "基础申购金额 1000.0"
python scripts/params.py --config config/strategy.json --set "初始资金 60000"
python scripts/params.py --config config/strategy.json --set "每月新增 5000"
```

所有数值参数均按配置中的最小值、最大值校验；越界时拒绝修改并提示合法范围。定期新增频率只允许每周、每月、每季、每年。
