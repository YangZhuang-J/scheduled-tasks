# -*- coding: utf-8 -*-
"""参数标定：网格搜索「状态边界」，找最优分位切分点。

用法：
python grid_search.py --index 沪深300 --states 3
python grid_search.py --index 沪深300 --states 5
"""
import argparse
import pandas as pd
import config_loader
import engine
from backtest import INDEX_SYMBOLS

DEFAULT_SELL = {
    "min_valuation_pct": 70,
    "ladder": [
        {"profit": 20, "ratio": 0.25},
        {"profit": 30, "ratio": 0.25},
        {"profit": 50, "ratio": 0.5},
    ],
}

# 动作模板（只搜索边界，动作固定）
ACTIONS_3 = [
    {"freq": "daily", "amount": 10},
    {"freq": "weekly", "amount": 10},
    {"freq": "biweekly", "amount": 10},
]
ACTIONS_5 = [
    {"freq": "monthly", "amount": 100},
    {"freq": "monthly", "amount": 80},
    {"freq": "monthly", "amount": 50},
    {"freq": "monthly", "amount": 10},
    {"freq": "monthly", "amount": 0},
]


def make_config(bounds, actions, sell):
    states = []
    prev = 0
    for b, act in zip(bounds + [100], actions):
        states.append({"range": [prev, b], "freq": act["freq"], "amount": act["amount"]})
        prev = b
    return {"name": "grid", "buy_states": states, "sell": sell}


def max_drawdown(daily):
    val = daily["shares"] * daily["close"] + daily["cash"]
    peak = val.cummax()
    return (val / peak - 1).min()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--states", type=int, choices=[3, 5], default=3)
    args = ap.parse_args()

    symbol = args.symbol or INDEX_SYMBOLS[args.index]
    df = engine.get_data(args.index, symbol, args.window)

    if args.states == 3:
        actions = ACTIONS_3
        combos = [(b1, b2) for b1 in [20, 30, 40] for b2 in [60, 70, 80] if b1 < b2]
    else:
        actions = ACTIONS_5
        combos = [
            (20, 40, 60, 80),
            (15, 35, 60, 80),
            (25, 45, 65, 85),
            (20, 40, 70, 85),
            (15, 40, 60, 80),
        ]

    rows = []
    for bounds in combos:
        cfg = make_config(list(bounds), actions, DEFAULT_SELL)
        res = engine.simulate(df, cfg, sell_mode="B")
        xr = engine.xirr(res["trades"], res["final_position"], df["date"].iloc[-1])
        dd = max_drawdown(res["daily"])
        n_sell = sum(1 for t in res["trades"] if t["action"] == "sell")
        n_buy = sum(1 for t in res["trades"] if t["action"] == "buy")
        rows.append({
            "边界": "/".join(map(str, bounds)),
            "XIRR%": round(xr * 100, 2),
            "总收益率%": round(res["total_return"] * 100, 1),
            "最大回撤%": round(dd * 100, 1),
            "买入": n_buy,
            "卖出": n_sell,
        })

    out = pd.DataFrame(rows).sort_values("XIRR%", ascending=False)
    print(f"=== {args.index}  {args.states}档 边界网格搜索（按 XIRR 排序）===")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
