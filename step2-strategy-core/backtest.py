# -*- coding: utf-8 -*-
"""回测入口：
python backtest.py --config config-3state.json --index 沪深300
"""
import argparse
import pandas as pd
import config_loader
import engine

INDEX_SYMBOLS = {
    "沪深300": "sh000300",
    "中证500": "sh000905",
    "上证50": "sh000016",
    "中证1000": "sh000852",
    "创业板指": "sz399006",
    "上证红利": "sh000015",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--symbol", default=None, help="新浪指数代码，如 sh000300（缺省按内置映射）")
    ap.add_argument("--window", type=int, default=60, help="分位滚动窗口（月），默认60=5年")
    ap.add_argument("--out", default=None, help="交易明细 CSV 输出路径")
    args = ap.parse_args()

    cfg = config_loader.load_config(args.config)
    symbol = args.symbol or INDEX_SYMBOLS[args.index]
    window = cfg.get("window_months", args.window)

    print("=" * 70)
    print(f"标的: {args.index} ({symbol})   配置: {args.config}  [{cfg.get('name', '')}]")
    print(f"分位窗口: {window} 个月")

    df = engine.get_data(args.index, symbol, window)

    res = engine.simulate(df, cfg)
    xr = engine.xirr(res["trades"], res["final_position"], df["date"].iloc[-1])

    print("-" * 70)
    print(f"回测区间: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}  （{len(df)} 个交易日）")
    print(f"总投入:      {res['invested']:,.0f} 元")
    print(f"剩余仓位市值: {res['final_position']:,.0f} 元")
    print(f"已落袋现金:   {res['cash']:,.0f} 元")
    print(f"最终总值:     {res['final_value']:,.0f} 元")
    print(f"总收益率:     {res['total_return']*100:.1f}%")
    print(f"年化(XIRR):   {xr*100:.2f}%")
    buys = [t for t in res["trades"] if t["action"] == "buy"]
    sells = [t for t in res["trades"] if t["action"] == "sell"]
    print(f"买入 {len(buys)} 次，卖出 {len(sells)} 次")
    print("-" * 70)

    if sells:
        print("卖出记录:")
        for t in sells[-10:]:
            print(f"  {t['date'].date()}  盈利{t['rung']}%档  卖{t['shares']}份 @ {t['price']}")

    if args.out:
        pd.DataFrame(res["trades"]).to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\n交易明细已存: {args.out}")


if __name__ == "__main__":
    main()
