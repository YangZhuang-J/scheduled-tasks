"""同花顺创业板低估定投策略：估值分位阶梯申购 + 高位赎回 + 赎回现金加速回投。

规则以 config/strategy.json 为事实源，详细口径见 references/rules.md；
默认标的使用 Fuyao 可取的创业板基金，回测周期默认近 5 年。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_client import DataClient
from font_config import configure_chinese_font


ROOT = Path(__file__).resolve().parents[1]
RISK_WARNING = "历史回测结果基于历史数据与既定规则模拟，不代表未来收益；市场有风险，投资需谨慎。本 skill 输出仅为决策参考，不构成投资建议。"
configure_chinese_font(plt)

BASE_MULTIPLES = [(20, 3.5), (30, 2.5), (45, 1.0), (65, 0.5), (70, 0.25), (101, 0.0)]
FINAL_CAPS = [(20, 6.0), (30, 5.0), (45, 3.0), (65, 1.5), (80, 0.5), (101, 0.0)]
ACCEL = [(10, 1.0), (15, 1.25), (20, 1.5), (30, 2.0), (101, 2.5)]
EXTRA_FREQ_MODES = {
    "每周": "weekly",
    "每月": "monthly",
    "每季": "quarterly",
    "每年": "annual",
}
FUND_PARAMS_DEFAULT = [
    {"key": "initial_capital", "label": "初始资金", "default": 50000, "min": 0, "max": 1000000, "step": 5000, "unit": "元"},
    {"key": "extra_contribution_amount", "label": "定期新增金额", "default": 5000, "min": 0, "max": 100000, "step": 1000, "unit": "元/次"},
    {"key": "extra_contribution_freq", "label": "定期新增频率", "default": "每月", "choices": ["每周", "每月", "每季", "每年"]},
]


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def within_skill(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("文件路径必须位于 skill 目录内：%s" % resolved) from exc
    return resolved


def _fund_params(cfg: dict) -> list:
    fp = cfg.get("fund_params")
    if fp:
        return fp
    return FUND_PARAMS_DEFAULT


def _format_param_list(params: list, cfg: dict) -> str:
    parts = []
    for p in params:
        key = p["key"]
        label = p.get("label", key)
        value = cfg.get(key, p.get("default", ""))
        if "min" in p and "max" in p:
            rng = "%s~%s" % (p["min"], p["max"])
        elif "choices" in p:
            rng = "/".join(str(c) for c in p["choices"])
        else:
            rng = ""
        parts.append("%s=%s(%s)" % (label, value, rng))
    return "；".join(parts)


def extra_period_key(t, mode: str) -> tuple:
    if mode == "weekly":
        return (t.year, t.week)
    if mode == "monthly":
        return (t.year, t.month)
    if mode == "quarterly":
        return (t.year, (t.month - 1) // 3 + 1)
    return (t.year,)


def explain_strategy(cfg: dict) -> str:
    expl = cfg.get("explanation") or {}
    fund_labels = "、".join(p.get("label", p.get("key", "")) for p in _fund_params(cfg))
    return "\n".join(
        [
            "理念：%s" % expl.get("idea", ""),
            "规则：%s" % expl.get("rules", ""),
            "仓位/费率：%s" % expl.get("position", ""),
            "可调参数（策略，≤5）：%s" % expl.get("params", ""),
            "资金参数：%s（均不计入≤5，可调整）" % fund_labels,
        ]
    )


def format_params(cfg: dict) -> str:
    return _format_param_list(cfg.get("tunable_params", []), cfg)


def format_fund_params(cfg: dict) -> str:
    return _format_param_list(_fund_params(cfg), cfg)


def analyze_result(cfg: dict, result: dict) -> tuple:
    lines = []
    advice = []
    xirr = result["xirr"]
    cash_rate = float(cfg.get("cash_interest_rate", 0.014))
    if xirr < cash_rate:
        lines.append("按实际投入节奏折算的年化收益率为 %.2f%%，低于现金利率 %.2f%%，策略当前没有跑赢现金。" % (xirr * 100.0, cash_rate * 100.0))
        advice.append("可在允许范围内调整基础申购金额，并重新回测比较。")
    else:
        lines.append("按实际投入节奏折算的年化收益率为 %.2f%%，高于现金利率 %.2f%%。" % (xirr * 100.0, cash_rate * 100.0))
    insuff = int(result.get("insufficientBuyCount", 0) or 0)
    if insuff > 0:
        lines.append("回测中有 %d 周因现金不足未能按目标倍数全额买入。" % insuff)
        advice.append("可提高初始资金或定期新增金额，或降低基础申购金额，减少资金不足买入。")
    mdd = result["maxDrawdown"]
    if mdd < -0.35:
        lines.append("最大回撤 %.2f%%，回撤较大。" % (mdd * 100.0))
        advice.append("可比较不同基础申购金额与触发赎回分位的回测结果，权衡收益和回撤。")
    avg_cash = result["avgCashRatio"]
    if avg_cash > 0.40:
        lines.append("平均赎回现金占比 %.2f%%，现金拖累明显。" % (avg_cash * 100.0))
        advice.append("可在允许范围内调低每日赎回比例，并重新回测现金占用变化。")
    end_cash = result["endCashRatio"]
    if end_cash > 0.30:
        lines.append("期末赎回现金占比 %.2f%%，仍有较多资金闲置。" % (end_cash * 100.0))
        advice.append("可在允许范围内调整每日赎回比例，并重新回测期末现金占比。")
    if result["sells"] == 0:
        lines.append("回测期内未触发高位赎回。")
    if result["acceleratedWeeks"] == 0:
        lines.append("现金加速机制基本未触发。")
    if not lines:
        lines.append("当前参数组合表现均衡，无明显需要调整的问题。")
    if not advice:
        advice.append("保持当前参数，继续按规则执行。")
    return "\n".join(lines), "；".join(advice)


def band_value(pct: float, table) -> float:
    for upper, value in table:
        if pct < upper:
            return value
    return table[-1][1]


def fetch_weekly(cfg: dict) -> tuple:
    source = cfg.get("valuation_source", "pe_ttm_5y_pct")
    if source != "pe_ttm_5y_pct":
        raise ValueError("本 skill 仅支持 PE 五年分位信号源；其他信号源必须使用独立 skill")
    client = DataClient()
    df = client.fetch_series(cfg["fund_thscode"], "otc", years=cfg.get("years", 5))
    if df.empty:
        raise RuntimeError("fund data empty: %s" % cfg["fund_thscode"])
    df = df.set_index("date")
    df.index = pd.to_datetime(df.index)
    df["_data_date"] = df.index
    weekly = df.resample("W-SUN").last().dropna(subset=["adj_nav"])
    weekly.index = pd.to_datetime(weekly.pop("_data_date"))
    weekly.index.name = "date"

    market = client.fetch_index(cfg["index_thscode"], years=cfg.get("years", 5) + 1)

    if market.empty:
        market_weekly = pd.Series(np.nan, index=weekly.index)
    else:
        market = market.set_index("date")
        market.index = pd.to_datetime(market.index)
        market_weekly = market["close"].sort_index().reindex(weekly.index, method="ffill")
    weekly["valuation_pct"] = pd.to_numeric(
        weekly.get("pe_ttm_5y_pct", pd.Series(np.nan, index=weekly.index)),
        errors="coerce",
    )
    if weekly["valuation_pct"].notna().sum() == 0:
        raise RuntimeError("同花顺金融数据API 未返回可用的创业板指五年 PE 分位数据，无法生成回测与信号")

    return weekly, market_weekly


def xirr(cashflows: list, rate_lo: float = -0.9, rate_hi: float = 10.0) -> float:
    dates = pd.to_datetime([c[0] for c in cashflows])
    days = (dates - dates[0]).days.astype(float)
    amounts = np.array([c[1] for c in cashflows], dtype=float)

    def npv(rate):
        return float(np.sum(amounts / (1.0 + rate) ** (days / 365.0)))

    lo, hi = rate_lo, rate_hi
    if npv(lo) * npv(hi) > 0:
        return 0.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def simulate(cfg: dict, weekly: pd.DataFrame, market_weekly: pd.Series = None) -> dict:
    if weekly.empty:
        raise ValueError("回测数据为空，无法运行策略")
    initial = float(cfg.get("initial_capital", 50000))
    weekly_base = float(cfg.get("weekly_base_amount", 1000))
    growth = float(cfg.get("growth_rate", 0.07))
    cash_rate = float(cfg.get("cash_interest_rate", 0.014))
    trigger = float(cfg.get("trigger_percentile", 95))
    reset = float(cfg.get("reset_percentile", 80))
    daily_redeem = float(cfg.get("daily_redeem_ratio", 0.01))
    min_multiple = float(cfg.get("min_reinvest_multiple", 0.15))
    min_cash_ratio = float(cfg.get("min_reinvest_cash_ratio", 0.15))
    extra_amount = float(cfg.get("extra_contribution_amount", cfg.get("annual_extra_contribution", 0)))
    extra_freq = str(cfg.get("extra_contribution_freq", "每年"))
    extra_mode = EXTRA_FREQ_MODES.get(extra_freq, "annual")
    weeks = int(cfg.get("weeks_per_year", 52))
    trading_days = int(cfg.get("trading_days_per_week", 5))
    low_pct = float(cfg.get("min_reinvest_pct_low", 70))
    high_pct = float(cfg.get("min_reinvest_pct_high", 80))
    base_table = cfg.get("base_multiples") or BASE_MULTIPLES
    cap_table = cfg.get("final_caps") or FINAL_CAPS
    accel_table = cfg.get("acceleration") or ACCEL

    cash = initial
    contributed = initial
    shares = 0.0
    start_year = weekly.index[0].year
    last_year = start_year
    last_extra_key = None
    extra_count = 0
    insufficient_buy_count = 0
    insufficient_buy_dates = []
    total_shortfall = 0.0
    redeeming = False
    ref_shares = 0.0
    first_nav = float(weekly["adj_nav"].iloc[0])
    first_market = float(market_weekly.dropna().iloc[0]) if market_weekly is not None and not market_weekly.dropna().empty else np.nan
    strategy_index = 100.0
    prev_value = initial
    first_period = True

    rows = []
    trades = []
    cashflows = [(weekly.index[0], -initial)]
    accelerated_weeks = 0

    for t, row in weekly.iterrows():
        nav = float(row["adj_nav"])
        cash *= 1.0 + cash_rate / weeks
        fund_value = shares * nav
        value_pre = cash + fund_value
        if first_period:
            period_ret = 1.0
            first_period = False
        else:
            period_ret = value_pre / prev_value if prev_value > 0 else 1.0
        strategy_index *= period_ret

        if t.year != last_year:
            last_year = t.year

        if extra_amount > 0:
            extra_key = extra_period_key(t, extra_mode)
            if last_extra_key is not None and extra_key != last_extra_key:
                amount = extra_amount * (1.0 + growth) ** (t.year - start_year)
                cash += amount
                contributed += amount
                extra_count += 1
                cashflows.append((t, -amount))
            last_extra_key = extra_key

        pct_val = row.get("valuation_pct")
        if pd.isna(pct_val):
            pct_val = row.get("pe_ttm_5y_pct")
        pct = float(pct_val) if not pd.isna(pct_val) else np.nan
        base = band_value(pct, base_table) if not np.isnan(pct) else 0.0

        if not np.isnan(pct) and pct >= trigger and not redeeming:
            redeeming = True
            ref_shares = shares
        if redeeming and (np.isnan(pct) or pct < reset):
            redeeming = False
            ref_shares = 0.0

        if redeeming and ref_shares > 0 and shares > 0:
            sell_shares = min(shares, ref_shares * daily_redeem * trading_days)
            proceeds = sell_shares * nav
            cash += proceeds
            shares -= sell_shares
            trades.append(
                {"date": t.strftime("%Y-%m-%d"), "fund": cfg.get("fund_name", ""),
                 "side": "sell", "amount": proceeds, "fee": 0.0, "pnl": 0.0}
            )

        total = cash + shares * nav
        cash_ratio = cash / total if total > 0 else 1.0
        accel = band_value(cash_ratio * 100.0, accel_table)
        final = base * accel
        cap = band_value(pct, cap_table) if not np.isnan(pct) else 0.0
        final = min(final, cap)
        if (
            not np.isnan(pct)
            and cash_ratio > min_cash_ratio
            and low_pct < pct <= high_pct
        ):
            final = max(final, min_multiple)
            accelerated_weeks += 1

        weekly_base_current = weekly_base * (1.0 + growth) ** (last_year - start_year)
        desired_buy = final * weekly_base_current
        shortfall = max(0.0, desired_buy - cash)
        insufficient = desired_buy > cash + 1e-9 and desired_buy > 0
        buy_amount = min(desired_buy, cash)
        if buy_amount > 0:
            cash -= buy_amount
            shares += buy_amount / nav
            trades.append(
                {"date": t.strftime("%Y-%m-%d"), "fund": cfg.get("fund_name", ""),
                 "side": "buy", "amount": buy_amount, "fee": 0.0, "pnl": 0.0}
            )
        if insufficient:
            insufficient_buy_count += 1
            insufficient_buy_dates.append(t.strftime("%Y-%m-%d"))
            total_shortfall += shortfall

        total = cash + shares * nav
        market_close = float(market_weekly.loc[t]) if market_weekly is not None and not pd.isna(market_weekly.get(t, np.nan)) else np.nan
        rows.append(
            {
                "date": t.strftime("%Y-%m-%d"),
                "asset": total,
                "contributed": contributed,
                "cash": cash,
                "shares": shares,
                "nav": nav,
                "pct": pct,
                "cash_ratio": cash / total if total > 0 else 1.0,
                "base_multiple": base,
                "final_multiple": final,
                "desired_buy": desired_buy,
                "buy_amount": buy_amount,
                "insufficient_buy": bool(insufficient),
                "shortfall": shortfall,
                "strategy_index": strategy_index,
                "fund_index": nav / first_nav * 100.0,
                "market_index": market_close / first_market * 100.0 if not np.isnan(first_market) and not np.isnan(market_close) else np.nan,
            }
        )
        prev_value = cash + shares * nav

    df = pd.DataFrame(rows).set_index("date")
    final_asset = float(df["asset"].iloc[-1])
    cashflows.append((df.index[-1], final_asset))
    peak = df["strategy_index"].cummax()
    max_dd = float((df["strategy_index"] / peak - 1.0).min())
    buys = int(sum(1 for tr in trades if tr["side"] == "buy"))
    sells = int(sum(1 for tr in trades if tr["side"] == "sell"))
    result = {
        "final": final_asset,
        "contributed": contributed,
        "profit": final_asset - contributed,
        "xirr": xirr(cashflows),
        "maxDrawdown": max_dd,
        "avgCashRatio": float(df["cash_ratio"].mean()),
        "endCashRatio": float(df["cash_ratio"].iloc[-1]),
        "buys": buys,
        "sells": sells,
        "acceleratedWeeks": accelerated_weeks,
        "extraContributionCount": extra_count,
        "insufficientBuyCount": insufficient_buy_count,
        "insufficientBuyDates": insufficient_buy_dates,
        "totalShortfall": total_shortfall,
        "rows": df,
        "trades": pd.DataFrame(
            trades,
            columns=["date", "fund", "side", "amount", "fee", "pnl"],
        ),
    }
    return result


def plot_result(result: dict, cfg: dict, out_dir: Path) -> Path:
    df = result["rows"]
    eq = df["strategy_index"].astype(float)
    bm = df["fund_index"].astype(float)
    idx = pd.to_datetime(df.index)
    eq.index = idx
    bm.index = idx
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    ax1.plot(idx, eq.values, label="策略", color="#1f77b4", linewidth=1.8)
    ax1.plot(idx, bm.values, label="基准（买入持有）", color="#9e9e9e", linewidth=1.3, alpha=0.85)
    trades = result["trades"]
    if trades is not None and not trades.empty:
        eq_dates = set(idx)
        for side, color, label in (
            ("buy", "#d62728", "买入"),
            ("sell", "#2ca02c", "卖出"),
        ):
            sub = trades[trades["side"] == side]
            dates = []
            vals = []
            for _, tr in sub.iterrows():
                d = pd.Timestamp(tr["date"])
                if d in eq_dates:
                    dates.append(d)
                    vals.append(float(eq.loc[d]))
            if dates:
                ax1.scatter(dates, vals, color=color, s=36, zorder=5, label=label, edgecolors="white", linewidths=0.5)
    ax1.set_title("%s 低估定投策略回测" % cfg.get("fund_name", ""))
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.25)
    dd = eq / eq.cummax() - 1.0
    ax2.fill_between(idx, dd.values, 0, color="#ef5350", alpha=0.5)
    ax2.set_ylabel("回撤")
    ax2.grid(True, alpha=0.25)
    metric_lines = [
        "年化收益 %.2f%%" % (result["xirr"] * 100.0),
        "最大回撤 %.2f%%" % (result["maxDrawdown"] * 100.0),
        "平均现金占比 %.2f%%" % (result["avgCashRatio"] * 100.0),
        "期末现金占比 %.2f%%" % (result["endCashRatio"] * 100.0),
        "申购 %d 周" % result["buys"],
        "赎回 %d 周" % result["sells"],
    ]
    ax1.text(
        0.99,
        0.03,
        "    ".join(metric_lines),
        transform=ax1.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "#cccccc"},
    )
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "cash_pool.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "strategy.json")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "gem_cash_pool")
    args = ap.parse_args()
    config_path = within_skill(args.config)
    out_dir = within_skill(args.out_dir)
    cfg = load_json(config_path)
    weekly, market_weekly = fetch_weekly(cfg)
    result = simulate(cfg, weekly, market_weekly)
    analysis, advice = analyze_result(cfg, result)
    out_dir.mkdir(parents=True, exist_ok=True)
    result["rows"].to_csv(out_dir / "cash_pool_daily.csv", encoding="utf-8-sig")
    result["trades"].to_csv(out_dir / "trades.csv", index=False, encoding="utf-8-sig")
    png = plot_result(result, cfg, out_dir)

    rows = result["rows"]
    strategy_return = float(rows["strategy_index"].iloc[-1] / 100.0 - 1.0)
    benchmark_return = float(rows["fund_index"].iloc[-1] / 100.0 - 1.0)

    summary = {
        "回测区间": "%s 至 %s" % (rows.index[0], rows.index[-1]),
        "基准": "同一基金买入持有（复权净值）",
        "策略时间加权收益率": strategy_return,
        "基准收益率": benchmark_return,
        "比一直持有多赚（百分点）": "%.2f 个百分点" % ((strategy_return - benchmark_return) * 100.0),
        "期末资产": result["final"],
        "累计投入": result["contributed"],
        "累计盈利": result["profit"],
        "按实际投入节奏折算的年化收益率": result["xirr"],
        "最大回撤": result["maxDrawdown"],
        "平均赎回现金占比": result["avgCashRatio"],
        "期末赎回现金占比": result["endCashRatio"],
        "申购周数": result["buys"],
        "赎回周数": result["sells"],
        "加速周数": result["acceleratedWeeks"],
        "新增资金次数": result["extraContributionCount"],
        "资金不足买入周数": result["insufficientBuyCount"],
        "资金不足缺口合计": result["totalShortfall"],
        "策略解释": explain_strategy(cfg),
        "策略可调参数": format_params(cfg),
        "资金参数": format_fund_params(cfg),
        "分析": analysis,
        "修改建议": advice,
        "风险提示": RISK_WARNING,
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n===== 策略解释 =====")
    print(explain_strategy(cfg))
    print("策略可调参数当前值：" + format_params(cfg))
    print("资金参数当前值：" + format_fund_params(cfg))
    print("\n===== 同花顺创业板低估定投策略回测 =====")
    for k, v in summary.items():
        if isinstance(v, float):
            print("%s: %.4f" % (k, v))
        else:
            print("%s: %s" % (k, v))
    print("图：" + str(png))
    print("图内容：策略收益曲线、基准（买入持有）曲线、买入红点/卖出绿点、回撤子图。")
    print("\n===== 分析与修改建议 =====")
    print(analysis)
    print("修改建议：" + advice)

    last = result["rows"].iloc[-1]
    print("\n===== 最新信号 =====")
    print("日期：%s" % last.name)
    print("分位：%.2f" % last["pct"])
    print("基础倍数：%.2f  最终倍数：%.2f" % (last["base_multiple"], last["final_multiple"]))
    if last["buy_amount"] > 0:
        print("动作：计划买入 %.2f 元" % last["buy_amount"])
    else:
        print("动作：暂停，本期计划买入金额为 0.00 元")
    print("说明：这是基于上述数据日期计算的参考信号，不是实时信号。")
    print("\n" + RISK_WARNING)


if __name__ == "__main__":
    main()
