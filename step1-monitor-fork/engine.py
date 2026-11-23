# -*- coding: utf-8 -*-
"""策略核心引擎：数据加载 + 估值分位 + 状态判定 + 回测模拟（向量化）"""
import os
import time
import numpy as np
import pandas as pd
import akshare as ak
import legulegu_api as lg

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
FREQS = ["daily", "weekly", "biweekly", "monthly"]
FREQ_IDX = {f: i for i, f in enumerate(FREQS)}


def load_price_daily(symbol):
    # 兼容 akshare 新旧版本：
    #   旧版(<=1.20.43): ak.stock_zh_index_daily
    #   新版(>=1.20.44): ak.index_zh_daily_sina
    if hasattr(ak, "stock_zh_index_daily"):
        px = ak.stock_zh_index_daily(symbol=symbol)[["date", "close"]]
    else:
        px = ak.index_zh_daily_sina(symbol=symbol)[["date", "close"]]
    px["date"] = pd.to_datetime(px["date"])
    px["close"] = pd.to_numeric(px["close"], errors="coerce")
    return px.dropna().sort_values("date").reset_index(drop=True)


def get_pe_raw(index_name, use_cache=True, ttl_hours=4):
    """拉取原始 PE(TTM) 月度数据，带 TTL 缓存（不同分位窗口复用同一份）"""
    cache_file = os.path.join(CACHE_DIR, f"pe_{index_name}.pkl")
    if use_cache and os.path.exists(cache_file):
        age_h = (time.time() - os.path.getmtime(cache_file)) / 3600
        if age_h < ttl_hours:
            return pd.read_pickle(cache_file)
    d = lg.get_pe_clean(lg.resolve(index_name))
    pe = d[["日期", "加权TTM_PE"]].copy()
    pe["日期"] = pd.to_datetime(pe["日期"])
    pe = pe.sort_values("日期").dropna(subset=["加权TTM_PE"]).reset_index(drop=True)
    pe.to_pickle(cache_file)
    return pe


def get_sp500_shiller_raw(use_cache=True, ttl_hours=4):
    """标普500 席勒PE（legulegu），带 TTL 缓存"""
    cache_file = os.path.join(CACHE_DIR, "sp500_shiller.pkl")
    if use_cache and os.path.exists(cache_file):
        age_h = (time.time() - os.path.getmtime(cache_file)) / 3600
        if age_h < ttl_hours:
            return pd.read_pickle(cache_file)
    d = lg.get_sp500_shiller()
    d["date"] = pd.to_datetime(d["date"])
    d.to_pickle(cache_file)
    return d


def load_sp500_shiller_percentile(window_months=60, use_cache=True, ttl_hours=4):
    """标普500 席勒PE 的滚动分位"""
    d = get_sp500_shiller_raw(use_cache, ttl_hours).copy()
    d["pct"] = (
        d["shiller_pe"]
        .rolling(window_months, min_periods=window_months)
        .apply(lambda x: (x <= x.iloc[-1]).sum() / len(x) * 100, raw=False)
    )
    return d


def load_pe_percentile(index_name, window_months=60, use_cache=True, ttl_hours=4):
    pe = get_pe_raw(index_name, use_cache, ttl_hours).copy()
    pe["pct"] = (
        pe["加权TTM_PE"]
        .rolling(window_months, min_periods=window_months)
        .apply(lambda x: (x <= x.iloc[-1]).sum() / len(x) * 100, raw=False)
    )
    return pe


def build_daily(px, pe_monthly):
    pe = pe_monthly.rename(columns={"日期": "date"})[["date", "pct"]].sort_values("date")
    df = pd.merge_asof(px.sort_values("date"), pe, on="date", direction="backward")
    return df.dropna(subset=["pct"]).reset_index(drop=True)


def get_data(index, symbol, window=60, use_cache=True, ttl_hours=4):
    """加载市场数据（价格+分位），带 TTL 缓存，避免反复请求 legulegu"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{index}_{symbol}_{window}.pkl")
    if use_cache and os.path.exists(cache_file):
        age_h = (time.time() - os.path.getmtime(cache_file)) / 3600
        if age_h < ttl_hours:
            return pd.read_pickle(cache_file)
    px = load_price_daily(symbol)
    pe = load_pe_percentile(index, window, ttl_hours=ttl_hours)
    df = build_daily(px, pe)
    df.to_pickle(cache_file)
    return df


def cache_age_hours(index, symbol, window=60):
    """返回缓存文件存在的小时数；无缓存返回 None"""
    cache_file = os.path.join(CACHE_DIR, f"{index}_{symbol}_{window}.pkl")
    if os.path.exists(cache_file):
        return (time.time() - os.path.getmtime(cache_file)) / 3600
    return None


def execution_mask(dates, freq):
    # 统一转成 datetime64，避免 datetime.date / datetime 混用导致 .dt 访问器失败
    d = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    if freq == "daily":
        return pd.Series(True, index=d.index)
    if freq == "weekly":
        iso = d.dt.isocalendar()
        key = iso.year.astype(str) + "-" + iso.week.astype(str)
        return ~key.duplicated()
    if freq == "biweekly":
        iso = d.dt.isocalendar()
        key = iso.year.astype(str) + "-" + (iso.week // 2).astype(str)
        return ~key.duplicated()
    if freq == "monthly":
        return ~d.dt.to_period("M").duplicated()
    raise ValueError(f"未知频率: {freq}")


def simulate(df, cfg, sell_mode="B", reset_line=0.0):
    """向量化回测。sell_mode: once / A / B；收益率口径=持仓收益率。"""
    df = df.reset_index(drop=True)
    states = cfg["buy_states"]
    sell = cfg.get("sell") or {}
    min_pct = sell.get("min_valuation_pct", 70)
    ladder = sell.get("ladder") or []

    dates = list(df["date"].dt.to_pydatetime())
    close = df["close"].values.astype(float)
    pcts = df["pct"].values.astype(float)
    n = len(df)

    # 执行日矩阵（4 种频率）
    exec_m = np.zeros((n, len(FREQS)), dtype=bool)
    for f in FREQS:
        exec_m[:, FREQ_IDX[f]] = execution_mask(df["date"], f).values

    # 每个交易日的状态 → 金额 + 频率下标（向量化 find_state）
    state_amount = np.zeros(n)
    state_freq = np.zeros(n, dtype=int)
    for st in states:
        lo, hi = st["range"]
        m = (pcts >= lo) & (pcts < hi)
        state_amount[m] = float(st["amount"])
        state_freq[m] = FREQ_IDX[st["freq"]]
    state_freq[pcts >= 100] = FREQ_IDX[states[-1]["freq"]]
    state_amount[pcts >= 100] = float(states[-1]["amount"])

    shares = 0.0
    cost_basis = 0.0
    total_invested = 0.0
    cash = 0.0
    trades = []

    armed = [True] * len(ladder)
    fired = set()
    exhausted = False

    daily_shares = np.zeros(n)
    daily_cash = np.zeros(n)
    daily_pos = np.full(n, np.nan)

    for i in range(n):
        p = close[i]
        pct = pcts[i]
        amount = state_amount[i]

        # 买入
        if exec_m[i, state_freq[i]] and amount > 0:
            shares += amount / p
            cost_basis += amount
            total_invested += amount
            trades.append({"date": dates[i], "action": "buy", "pct": round(pct, 1),
                           "amount": amount, "price": round(p, 3),
                           "shares": round(amount / p, 4)})

        pos_ret = (shares * p / cost_basis - 1) if (shares > 0 and cost_basis > 0) else np.nan

        # 卖出
        if pct >= min_pct and shares > 0 and cost_basis > 0 and not np.isnan(pos_ret):
            if sell_mode == "B":
                for j, rung in enumerate(ladder):
                    th = rung["profit"] / 100.0
                    if armed[j] and pos_ret >= th:
                        sold = shares * rung["ratio"]
                        cash += sold * p
                        shares -= sold
                        cost_basis *= (1 - rung["ratio"])
                        armed[j] = False
                        trades.append({"date": dates[i], "action": "sell", "pct": round(pct, 1),
                                       "rung": rung["profit"], "price": round(p, 3),
                                       "shares": round(sold, 4), "proceeds": round(sold * p, 2),
                                       "pos_return": round(pos_ret * 100, 2)})
                        pos_ret = (shares * p / cost_basis - 1) if shares > 0 else np.nan
                        # 保护：卖光或 cost_basis 归零后，不再触发后续档位
                        if shares <= 1e-9 or cost_basis <= 1e-9:
                            break
                    elif (not armed[j]) and pos_ret < th:
                        armed[j] = True
            elif sell_mode == "A":
                if exhausted and pos_ret <= reset_line:
                    fired.clear()
                    exhausted = False
                if not exhausted:
                    for j, rung in enumerate(ladder):
                        th = rung["profit"] / 100.0
                        if j not in fired and pos_ret >= th:
                            sold = shares * rung["ratio"]
                            cash += sold * p
                            shares -= sold
                            cost_basis *= (1 - rung["ratio"])
                            fired.add(j)
                            trades.append({"date": dates[i], "action": "sell", "pct": round(pct, 1),
                                           "rung": rung["profit"], "price": round(p, 3),
                                           "shares": round(sold, 4), "proceeds": round(sold * p, 2),
                                           "pos_return": round(pos_ret * 100, 2)})
                            pos_ret = (shares * p / cost_basis - 1) if shares > 0 else np.nan
                    if len(fired) == len(ladder):
                        exhausted = True
            else:  # once
                for j, rung in enumerate(ladder):
                    th = rung["profit"] / 100.0
                    if j not in fired and pos_ret >= th:
                        sold = shares * rung["ratio"]
                        cash += sold * p
                        shares -= sold
                        cost_basis *= (1 - rung["ratio"])
                        fired.add(j)
                        trades.append({"date": dates[i], "action": "sell", "pct": round(pct, 1),
                                       "rung": rung["profit"], "price": round(p, 3),
                                       "shares": round(sold, 4), "proceeds": round(sold * p, 2),
                                       "pos_return": round(pos_ret * 100, 2)})
                        pos_ret = (shares * p / cost_basis - 1) if shares > 0 else np.nan

        daily_shares[i] = shares
        daily_cash[i] = cash
        daily_pos[i] = pos_ret * 100 if not np.isnan(pos_ret) else np.nan

    daily_df = pd.DataFrame({
        "date": dates, "close": close, "pct": pcts,
        "pos_return": daily_pos, "shares": daily_shares, "cash": daily_cash,
    })
    last_price = close[-1]
    final_position = shares * last_price
    final_value = final_position + cash
    total_return = (final_value / total_invested - 1) if total_invested > 0 else 0.0

    return {
        "invested": total_invested,
        "final_position": final_position,
        "cash": cash,
        "final_value": final_value,
        "total_return": total_return,
        "shares": shares,
        "trades": trades,
        "daily": daily_df,
    }


def xirr(trades, final_position, last_date):
    dates = []
    amounts = []
    for t in trades:
        dates.append(t["date"])
        if t["action"] == "buy":
            amounts.append(-t["amount"])
        else:
            amounts.append(t["proceeds"])
    dates.append(pd.Timestamp(last_date))
    amounts.append(final_position)

    t = np.array([(d - dates[0]).days / 365.25 for d in dates], dtype=float)
    a = np.array(amounts, dtype=float)

    def npv(r):
        return np.sum(a / (1 + r) ** t)

    lo, hi = -0.999, 10.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
