# -*- coding: utf-8 -*-
"""
第 0 步 · 通用对比回测
- 沪深300：真实 PE(TTM) 历史分位
- 纳指100 / 标普500：免费 PE 源缺失，用「价格历史分位」作估值代理（仅示意）

每个标的 × 每种分位窗口 × 两种策略(无脑/估值) → 输出对比表
"""
import numpy as np
import pandas as pd
import akshare as ak


def multiplier(pct):
    if np.isnan(pct): return 1.0
    if pct < 20: return 2.0
    if pct < 40: return 1.5
    if pct < 60: return 1.0
    if pct < 80: return 0.5
    return 0.0


def pct_rank_series(val, window):
    """滚动窗口内的历史分位（含当前值），window=None 用全历史"""
    def f(x):
        x = x.dropna()
        if len(x) < 1: return np.nan
        cur = x.iloc[-1]
        return (x <= cur).sum() / len(x) * 100
    if window is None:
        # 全历史：从第 60 个月开始给分位（需要足够样本）
        def full_rank(v):
            out = pd.Series(index=v.index, dtype=float)
            for i in range(len(v)):
                if i + 1 >= 60:
                    out.iloc[i] = (v.iloc[:i+1] <= v.iloc[i]).sum() / (i+1) * 100
            return out
        return full_rank(val)
    return val.rolling(window, min_periods=window).apply(f, raw=False)


def build_monthly(px, val, window):
    m = px.set_index("date")["close"].resample("ME").last().dropna().rename("close")
    df = pd.DataFrame({"close": m})
    df["val"] = val.reindex(df.index).ffill()
    df = df.dropna(subset=["val"])
    df["pct"] = pct_rank_series(df["val"], window)
    return df


def run_dca(df, base=1000.0, strategy="naive"):
    shares = 0.0; invested = 0.0; flows = []
    for dt, row in df.iterrows():
        mult = 1.0 if strategy == "naive" else multiplier(row["pct"])
        amt = base * mult
        if amt > 0:
            shares += amt / row["close"]
            invested += amt
            flows.append((dt, -amt))
    final_value = shares * df["close"].iloc[-1]
    avg_cost = invested / shares if shares else np.nan
    return dict(shares=shares, invested=invested, final_value=final_value,
                avg_cost=avg_cost, flows=flows)


def xirr(flows, final_value, last_date):
    dates = [f[0] for f in flows] + [last_date]
    amts = [f[1] for f in flows] + [final_value]
    t = np.array([(d - dates[0]).days / 365.25 for d in dates])
    a = np.array(amts, dtype=float)
    lo, hi = -0.999, 10.0
    def npv(r): return np.sum(a / (1 + r) ** t)
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(mid) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def compare(df, label, window_name):
    n = run_dca(df, strategy="naive")
    v = run_dca(df, strategy="valuation")
    out = []
    for tag, r in [("无脑", n), ("估值", v)]:
        r["xirr"] = xirr(r["flows"], r["final_value"], df.index[-1])
        out.append(dict(标的=label, 分位窗口=window_name, 策略=tag,
                         投入=round(r["invested"]),
                         市值=round(r["final_value"]),
                         总收益=f'{r["final_value"]/r["invested"]*100-100:.1f}%',
                         平均成本=round(r["avg_cost"], 2),
                         XIRR=f'{r["xirr"]*100:.2f}%',
                         停买月=(df["pct"] >= 80).sum() if tag == "估值" else 0))
    return out


def load_hs300():
    px = ak.stock_zh_index_daily(symbol="sh000300")[["date", "close"]]
    px["date"] = pd.to_datetime(px["date"])
    pe = ak.stock_index_pe_lg(symbol="沪深300")[["日期", "滚动市盈率"]]
    pe.columns = ["date", "val"]
    pe["date"] = pd.to_datetime(pe["date"])
    pe["val"] = pd.to_numeric(pe["val"], errors="coerce")
    return px.sort_values("date").dropna(), pe.sort_values("date").dropna()

def load_us(symbol, name):
    px = ak.index_us_stock_sina(symbol=symbol)[["date", "close"]]
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values("date").dropna()
    px["close"] = pd.to_numeric(px["close"], errors="coerce")
    # 估值代理 = 月度收盘价（即价格分位）
    val = px.set_index("date")["close"].resample("ME").last().dropna().to_frame(name="val")
    val.index = pd.to_datetime(val.index)
    return px, val


if __name__ == "__main__":
    results = []
    print("加载数据中...")

    px, pe = load_hs300()
    for w, wn in [(60, "5年"), (120, "10年"), (None, "全历史")]:
        df = build_monthly(px, pe.set_index("date")["val"], w)
        results += compare(df, "沪深300(PE)", wn)
        print(f"  沪深300 {wn}窗口完成, 共{len(df)}个月")

    for sym, name in [(".NDX", "纳指100(价格代理)"), (".INX", "标普500(价格代理)")]:
        px, val = load_us(sym, name)
        for w, wn in [(60, "5年"), (120, "10年")]:
            df = build_monthly(px, val["val"], w)
            results += compare(df, name, wn)
            print(f"  {name} {wn}窗口完成, 共{len(df)}个月")

    out = pd.DataFrame(results)
    print()
    print(out.to_string(index=False))
    out.to_csv("backtest_compare.csv", index=False, encoding="utf-8-sig")
    print("\n已保存 backtest_compare.csv")
