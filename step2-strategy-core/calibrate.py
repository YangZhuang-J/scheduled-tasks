# -*- coding: utf-8 -*-
"""全参数标定：分位窗口 × 动作强度 × 卖出闸门 × 卖出阶梯 × 状态边界

用法：python calibrate.py --index 沪深300
"""
import argparse
import pandas as pd
import engine
from backtest import INDEX_SYMBOLS

# 分位窗口（月）
WINDOWS = [36, 60, 120]

# 动作强度：低估档 / 中性档 / 高估档 的相对投入倍数（绝对金额由用户定，这里只标定比例）
AGGR = {
    "温和": [1.5, 1.0, 0.5],
    "标准": [2.0, 1.0, 0.0],
    "激进": [3.0, 1.0, 0.0],
}

# 卖出闸门（估值分位 ≥ 该值才允许卖）
GATES = [60, 70, 80]

# 卖出阶梯模板
LADDERS = {
    "A激进止盈": [{"profit": 15, "ratio": 0.25}, {"profit": 25, "ratio": 0.25}, {"profit": 40, "ratio": 0.5}],
    "B标准":     [{"profit": 20, "ratio": 0.25}, {"profit": 30, "ratio": 0.25}, {"profit": 50, "ratio": 0.5}],
    "C保守":     [{"profit": 30, "ratio": 0.33}, {"profit": 50, "ratio": 0.33}, {"profit": 80, "ratio": 0.34}],
    "D两档":     [{"profit": 20, "ratio": 0.5},  {"profit": 40, "ratio": 0.5}],
}

BOUNDARIES = {
    "沪深300": [[20, 80], [30, 70], [20, 70]],
    "中证500": [[40, 70], [30, 70], [40, 80]],
}


def make_config(boundary, aggr, gate, ladder):
    b1, b2 = boundary
    base = 100.0
    states = [
        {"range": [0, b1], "freq": "weekly", "amount": round(base * aggr[0], 1)},
        {"range": [b1, b2], "freq": "weekly", "amount": round(base * aggr[1], 1)},
        {"range": [b2, 100], "freq": "weekly", "amount": round(base * aggr[2], 1)},
    ]
    return {"name": "calib", "buy_states": states,
            "sell": {"min_valuation_pct": gate, "ladder": ladder}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    symbol = args.symbol or INDEX_SYMBOLS[args.index]
    bounds = BOUNDARIES.get(args.index, [[30, 70], [20, 80], [40, 70]])

    rows = []
    for window in WINDOWS:
        df = engine.get_data(args.index, symbol, window)
        for b in bounds:
            for aggr_name, aggr in AGGR.items():
                for gate in GATES:
                    for lad_name, ladder in LADDERS.items():
                        cfg = make_config(b, aggr, gate, ladder)
                        res = engine.simulate(df, cfg, sell_mode="B")
                        xr = engine.xirr(res["trades"], res["final_position"], df["date"].iloc[-1])
                        val = res["daily"]["shares"] * res["daily"]["close"] + res["daily"]["cash"]
                        maxdd = (val / val.cummax() - 1).min()
                        n_sell = sum(1 for t in res["trades"] if t["action"] == "sell")
                        rows.append({
                            "窗口年": window // 12,
                            "边界": f"{b[0]}/{b[1]}",
                            "强度": aggr_name,
                            "闸门": gate,
                            "阶梯": lad_name,
                            "XIRR%": round(xr * 100, 2),
                            "总收益%": round(res["total_return"] * 100, 1),
                            "回撤%": round(maxdd * 100, 1),
                            "卖出": n_sell,
                        })

    out = pd.DataFrame(rows).sort_values("XIRR%", ascending=False)
    print(f"=== {args.index} 全参数标定 TOP{args.top}（按 XIRR 排序）===")
    print(out.head(args.top).to_string(index=False))

    # 各维度单独看：窗口、强度、闸门、阶梯 的平均 XIRR
    print("\n--- 分维度平均 XIRR ---")
    for dim in ["窗口年", "强度", "闸门", "阶梯"]:
        g = out.groupby(dim)["XIRR%"].mean().round(2).sort_values(ascending=False)
        print(f"[{dim}]  " + "  ".join(f"{k}={v}" for k, v in g.items()))


if __name__ == "__main__":
    main()
