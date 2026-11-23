# -*- coding: utf-8 -*-
"""配置加载与校验"""
import json

VALID_FREQS = {"daily", "weekly", "biweekly", "monthly"}


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    validate(cfg)
    return cfg


def validate(cfg):
    states = cfg.get("buy_states")
    if not states:
        raise ValueError("缺少 buy_states")

    prev_hi = 0.0
    for i, s in enumerate(states):
        lo, hi = s["range"]
        if lo != prev_hi:
            raise ValueError(f"第{i+1}档区间不连续: 上档结束={prev_hi}, 本档开始={lo}")
        if hi <= lo:
            raise ValueError(f"第{i+1}档区间非法: [{lo}, {hi}]")
        if s["freq"] not in VALID_FREQS:
            raise ValueError(f"第{i+1}档频率非法: {s['freq']}，允许 {sorted(VALID_FREQS)}")
        if s["amount"] < 0:
            raise ValueError(f"第{i+1}档金额需 ≥ 0，当前 {s['amount']}")
        prev_hi = hi
    if prev_hi != 100:
        raise ValueError(f"最后一档应到 100，当前结束于 {prev_hi}")

    sell = cfg.get("sell") or {}
    mp = sell.get("min_valuation_pct", 70)
    if not (0 <= mp <= 100):
        raise ValueError(f"min_valuation_pct 需在 0~100，当前 {mp}")

    ladder = sell.get("ladder") or []
    profits = []
    for i, r in enumerate(ladder):
        if not (0 < r["ratio"] <= 1):
            raise ValueError(f"ladder 第{i+1}级 ratio 需在 (0,1]，当前 {r['ratio']}")
        profits.append(r["profit"])
    if profits != sorted(profits):
        raise ValueError(f"ladder 的 profit 需升序，当前 {profits}")

    return cfg
