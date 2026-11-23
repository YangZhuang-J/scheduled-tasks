# -*- coding: utf-8 -*-
"""历史压力测试：用真实历史区间回放这个计划，看账面最惨到多少。

比蒙特卡洛更有说服力 —— 因为它用的是真实发生过的行情。
"""
import pandas as pd
import montecarlo as mc

# 真实的历史压力区间（起始日 → 结束日）
CRISES = [
    ("2007 金融危机", "2007-10-16", "2009-03-03"),
    ("2015 股灾", "2015-06-12", "2016-02-29"),
    ("2018 熊市", "2018-01-24", "2019-01-03"),
    ("2021 高点回落", "2021-12-13", "2024-02-05"),
]


def _path_within(df, start, end):
    m = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df[m].reset_index(drop=True)


def run(df, config, weekly_base):
    """对每个历史危机区间回放定投，返回结果列表"""
    scaled = mc.scale_states(config, weekly_base)
    sell_cfg = config.get("sell")
    out = []

    for name, start, end in CRISES:
        sub = _path_within(df, start, end)
        if len(sub) < 30:
            continue
        r = mc._simulate_one(
            sub["close"].values.astype(float),
            sub["pct"].values.astype(float),
            scaled, sell_cfg,
        )
        final = r["final_value"]
        invested = r["invested"]
        out.append({
            "区间": name,
            "起止": f"{sub['date'].iloc[0].date()} ~ {sub['date'].iloc[-1].date()}",
            "累计投入": invested,
            "期末市值": final,
            "期末盈亏": (final / invested - 1) * 100 if invested > 0 else 0,
            "期间最大浮亏": r["max_loss"] * 100,
            "浮亏月占比": r["loss_month_ratio"] * 100,
        })
    return out
