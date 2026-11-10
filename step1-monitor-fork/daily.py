#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日运行：重算模拟定投 → 检测状态迁移 → PushPlus 通知 → 记录日志"""
import os
import json
import pandas as pd

import engine
import config_loader
import notify

BASE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE, "settings.json")
STATE_PATH = os.path.join(BASE, "state.json")
LOG_PATH = os.path.join(BASE, "trade_log.jsonl")

DEFAULT_LABELS = {3: ["低估", "正常", "高估"], 5: ["极低估", "低估", "正常", "高估", "极高估"]}


def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def labels_of(cfg):
    n = len(cfg["buy_states"])
    return cfg.get("labels") or DEFAULT_LABELS.get(n, [f"档{i}" for i in range(n)])


def bucket_idx(pct, states):
    for i, s in enumerate(states):
        if s["range"][0] <= pct < s["range"][1]:
            return i
    return len(states) - 1


def fmt(v):
    return f"{v:,.0f}"


def main():
    settings = load_json(SETTINGS_PATH)
    if not settings:
        print("缺少 settings.json，退出")
        return

    state = load_json(STATE_PATH) or {"last_data_date": None}
    notify_cfg = settings.get("notify", {})

    digest_lines = []
    transitions = []
    log_lines = []
    latest_data_date = None

    for t in settings.get("track", []):
        idx = t["index"]
        symbol = t["symbol"]
        cfg = config_loader.load_config(os.path.join(BASE, t["config"]))
        labels = labels_of(cfg)
        window = cfg.get("window_months", 60)

        df = engine.get_data(idx, symbol, window)
        if len(df) == 0:
            continue

        start = settings.get("start_date")
        sim_df = df[df["date"] >= pd.Timestamp(start)] if start else df
        if len(sim_df) == 0:
            print(f"{idx}: 开始日期 {start} 之后尚无数据（最新 {df['date'].iloc[-1].date()}），等待首个交易日")
            continue

        res = engine.simulate(sim_df, cfg, sell_mode="B")

        last_date = df["date"].iloc[-1]
        latest_data_date = last_date if latest_data_date is None else max(latest_data_date, last_date)

        pct_last = float(df["pct"].iloc[-1])
        cur_bucket = bucket_idx(pct_last, cfg["buy_states"])
        cur_label = labels[cur_bucket]

        # 状态迁移（最近两个交易日对比）
        if len(df) >= 2 and notify_cfg.get("on_transition", True):
            prev_bucket = bucket_idx(float(df["pct"].iloc[-2]), cfg["buy_states"])
            if prev_bucket != cur_bucket:
                transitions.append((idx, labels[prev_bucket], cur_label))

        # 今日动作
        last_d = last_date.date()
        today_trades = [x for x in res["trades"] if x["date"].date() == last_d]
        buys = [x for x in today_trades if x["action"] == "buy"]
        sells = [x for x in today_trades if x["action"] == "sell"]
        if buys:
            act = f"买入 {fmt(sum(x['amount'] for x in buys))} 元"
        elif sells:
            act = f"卖出 {len(sells)} 笔"
        else:
            act = "无操作"

        # 盈亏
        p_last = float(df["close"].iloc[-1])
        val = res["shares"] * p_last + res["cash"]
        prof = (val / res["invested"] - 1) * 100 if res["invested"] > 0 else 0.0

        digest_lines.append(
            f"**{idx}**：分位 {pct_last:.0f}%（{cur_label}）｜{act}｜"
            f"累计投入 {fmt(res['invested'])}｜当前总值 {fmt(val)}｜盈亏 {prof:+.1f}%"
        )

        for x in today_trades:
            log_lines.append(json.dumps({
                "date": str(last_d), "index": idx, "action": x["action"],
                "amount": x.get("amount"), "price": x.get("price"),
                "shares": x.get("shares"), "rung": x.get("rung"),
            }, ensure_ascii=False))

    # 数据没更新（节假日/非交易日）→ 不推送
    if latest_data_date is None:
        print("所有标的都还没有开始日期之后的数据，等待首个交易日")
        return
    if state.get("last_data_date") and str(latest_data_date.date()) <= state["last_data_date"]:
        print(f"数据未更新（截至 {latest_data_date.date()}），跳过推送")
        return

    # 组装消息
    title_parts = []
    content = []
    for idx, old, new in transitions:
        title_parts.append(f"{idx} {old}→{new}")
        content.append(f"🔔 **{idx}** 状态迁移：{old} → **{new}**")
    if notify_cfg.get("daily_digest", True):
        title_parts.append("定投日报")
        content.append("📊 每日摘要：")
        content.extend(digest_lines)

    title = " ".join(title_parts) if title_parts else "定投日报"
    body = "\n\n".join(content)

    # 保存状态与日志
    state["last_data_date"] = str(latest_data_date.date())
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    if log_lines:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")

    # 推送
    token = os.environ.get("PUSHPLUS_TOKEN")
    if token:
        ok, resp = notify.push(token, title, body)
        print("PushPlus 推送:", "成功" if ok else f"失败 {resp}")
    else:
        print("未设置 PUSHPLUS_TOKEN，本地预览：")
        print("标题:", title)
        print(body)


if __name__ == "__main__":
    main()
