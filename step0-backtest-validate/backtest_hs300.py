# -*- coding: utf-8 -*-
"""
第 0 步 · 回测引擎 v1
对比「无脑定投」vs「估值分位定投」（只比较买入节奏，卖出端第 2 步再加）。

估值分位规则（温度表草案）：
  PE 5年历史分位  <20 → 2.0x  | 20~40 → 1.5x | 40~60 → 1.0x | 60~80 → 0.5x | >80 → 0x(停买)

输出：两种策略的 总投入 / 最终市值 / 总收益率 / 平均成本 / 年化(XIRR) / 份额
"""
import numpy as np
import pandas as pd

def load_hs300():
    """沪深300：日线价格(新浪) + 月度PE(乐咕乐股)"""
    import akshare as ak
    px = ak.stock_zh_index_daily(symbol="sh000300")          # date, close...
    pe = ak.stock_index_pe_lg(symbol="沪深300")              # 日期, 滚动市盈率...
    px = px[["date", "close"]].copy()
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values("date").dropna()

    pe = pe[["日期", "滚动市盈率"]].copy()
    pe.columns = ["date", "pe_ttm"]
    pe["date"] = pd.to_datetime(pe["date"])
    pe["pe_ttm"] = pd.to_numeric(pe["pe_ttm"], errors="coerce")
    pe = pe.sort_values("date").dropna()
    return px, pe

def monthly_series(px, pe, warmup_months=60):
    """把日线价格与月度PE合并成月度序列，并计算PE历史分位"""
    # 每月取最后一个交易日收盘价
    m = px.set_index("date")["close"].resample("ME").last().dropna().rename("close")
    p = pe.set_index("date")["pe_ttm"].resample("ME").last()
    # 用最近可得PE前向填充
    df = pd.DataFrame({"close": m})
    df["pe_ttm"] = p.reindex(df.index).ffill()
    df = df.dropna(subset=["pe_ttm"])

    # PE 历史分位（滚动 warmup_months 个月窗口）
    def pct_rank(x):
        x = x.dropna()
        cur = x.iloc[-1]
        return (x <= cur).sum() / len(x) * 100
    df["pe_pct"] = df["pe_ttm"].rolling(warmup_months, min_periods=warmup_months).apply(pct_rank, raw=False)
    return df

def multiplier(pe_pct):
    if np.isnan(pe_pct):
        return 1.0
    if pe_pct < 20: return 2.0
    if pe_pct < 40: return 1.5
    if pe_pct < 60: return 1.0
    if pe_pct < 80: return 0.5
    return 0.0

def run_dca(df, base=1000.0, strategy="naive"):
    """按月定投，返回现金流与持仓；strategy: naive | valuation"""
    shares = 0.0
    invested = 0.0
    flows = []  # (date, cashflow)
    for dt, row in df.iterrows():
        mult = 1.0 if strategy == "naive" else multiplier(row["pe_pct"])
        amt = base * mult
        if amt > 0:
            shares += amt / row["close"]
            invested += amt
            flows.append((dt, -amt))
    final_value = shares * df["close"].iloc[-1]
    avg_cost = invested / shares if shares else np.nan
    return dict(shares=shares, invested=invested, final_value=final_value,
                avg_cost=avg_cost, flows=flows)

def xirr(flows, final_value):
    """简单二分法算年化(资金加权)。flows: [(date, cashflow负值)]"""
    dates = [f[0] for f in flows]
    amts = [f[1] for f in flows]
    # 期末加一笔回款
    dates.append(df_last_date)
    amts.append(final_value)
    t = np.array([(d - dates[0]).days / 365.25 for d in dates])
    a = np.array(amts, dtype=float)
    lo, hi = -0.999, 10.0
    def npv(r): return np.sum(a / (1 + r) ** t)
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2

if __name__ == "__main__":
    import akshare as ak
    px, pe = load_hs300()
    df = monthly_series(px, pe, warmup_months=60)
    df_last_date = df.index[-1]
    print("月度数据范围:", df.index[0].date(), "→", df.index[-1].date(), " 共", len(df), "个月")
    print("PE 区间: %.2f ~ %.2f  最新 PE=%.2f (分位 %.1f%%)" %
          (df["pe_ttm"].min(), df["pe_ttm"].max(), df["pe_ttm"].iloc[-1], df["pe_pct"].iloc[-1]))
    print()

    res_naive = run_dca(df, strategy="naive")
    res_val = run_dca(df, strategy="valuation")

    rows = []
    for name, r in [("无脑定投(每月1x)", res_naive), ("估值定投(分位调仓)", res_val)]:
        r["xirr"] = xirr(r["flows"], r["final_value"])
        rows.append(dict(策略=name,
                         总投入=round(r["invested"], 0),
                         最终市值=round(r["final_value"], 0),
                         总收益率=f'{r["final_value"]/r["invested"]*100-100:.1f}%',
                         平均成本=round(r["avg_cost"], 3),
                         累计份额=round(r["shares"], 2),
                         年化XIRR=f'{r["xirr"]*100:.2f}%'))
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))

    out.to_csv("backtest_result_hs300.csv", index=False, encoding="utf-8-sig")
    print("\n结果已保存: backtest_result_hs300.csv")

    # 顺便看每档各出现了多少个月
    df["档位"] = df["pe_pct"].apply(lambda p: np.nan if np.isnan(p) else
                                    ("<20" if p<20 else "20-40" if p<40 else "40-60" if p<60 else "60-80" if p<80 else ">80"))
    print("\n各温度档位出现月数:")
    print(df["档位"].value_counts().reindex(["<20","20-40","40-60","60-80",">80"]).to_string())
