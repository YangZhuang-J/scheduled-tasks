# -*- coding: utf-8 -*-
"""定投计划设计器 v2 —— 以图为主，直观感受参数影响

启动：streamlit run app.py
"""
import os
import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import engine
import finance
import charts

st.set_page_config(page_title="定投沙盘", page_icon="📈", layout="wide")

FREQ_MAP = {"每日": "daily", "每周": "weekly", "每双周": "biweekly", "每月": "monthly"}
FREQ_PER_YEAR = {"daily": 250, "weekly": 52, "biweekly": 26, "monthly": 12}

INDEX_OPTIONS = {
    # 宽基
    "沪深300": "sh000300",
    "中证500": "sh000905",
    "中证1000": "sh000852",
    "中证800": "sh000906",
    "中证100": "sh000903",
    "上证50": "sh000016",
    "上证180": "sh000010",
    "深证100": "sz399330",
    "创业板指": "sz399006",
    "创业板50": "sz399673",
    # 红利
    "上证红利": "sh000015",
    "深证红利": "sz399324",
    "中证红利": "CSI:000922.CSI",   # CSI 代码，价格用 legulegu 自身
    # 美股
    "标普500": "SP500",   # 特殊标记：价格用新浪 .INX，估值用席勒PE
    "纳指100": "NDX",     # 特殊标记：价格用新浪 .NDX，无 PE 用价格分位
    # 商品
    "黄金": "GOLD",       # 特殊标记：上海金 Au99.99，无 PE 用价格分位
}

PRESETS = {
    "3档 · 20/80（沪深300标定）": [(0, 20), (20, 80), (80, 100)],
    "3档 · 30/70（业内通用）": [(0, 30), (30, 70), (70, 100)],
    "5档 · 20/40/60/80（等分）": [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)],
    "5档 · 15/35/70/85（天天基金式）": [(0, 15), (15, 35), (35, 70), (70, 85), (85, 100)],
}


TTL_HOURS = 4


def _price_from_legulegu(index_name):
    """从 legulegu 原始 PE 数据里提取价格（中证系指数用）

    legulegu 的 index-basic-pe 接口返回的数据同时包含：
    date / close / 等权TTM / 中位TTM / 加权TTM ...
    这里取 close 作为价格序列。
    """
    import legulegu_api as lg
    d = lg.get_pe(lg.resolve(index_name))
    d = d[["date", "close"]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)



def _ak_us_daily(symbol_us):
    """兼容 akshare 新旧版本的美股指数日线接口"""
    import akshare as ak
    if hasattr(ak, "index_us_stock_sina"):
        return ak.index_us_stock_sina(symbol=symbol_us)
    return ak.index_us_daily_sina(symbol=symbol_us)


@st.cache_data(ttl=TTL_HOURS * 3600, show_spinner=False, persist="disk")
def load_full_price(symbol):
    """获取全历史价格（2002~今，用于参考视图，不受 PE 限制）"""
    if symbol.startswith("CSI:"):
        # CSI 指数：用 legulegu 的完整历史
        import legulegu_api as lg
        d = lg.get_pe(lg.resolve(symbol.replace("CSI:", "")))
        d = d[["date", "close"]].copy()
        d["date"] = pd.to_datetime(d["date"])
        return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if symbol == "SP500":
        # 标普500：用席勒PE自带的价格（1871~今）
        d = engine.get_sp500_shiller_raw(ttl_hours=TTL_HOURS)
        d = d[["date", "sp500_close"]].copy()
        d.columns = ["date", "close"]
        d["date"] = pd.to_datetime(d["date"])
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if symbol == "NDX":
        # 纳指100：优先用本地完整历史（1985~今）
        full_path = os.path.join(engine.CACHE_DIR, "ndx_full_history.pkl")
        if os.path.exists(full_path):
            d = pd.read_pickle(full_path).copy()
            if "date" not in d.columns:
                d = d.reset_index()
            d = d[["date", "close"]].copy()
            d["date"] = pd.to_datetime(d["date"])
            d["close"] = pd.to_numeric(d["close"], errors="coerce")
            return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        import akshare as ak
        d = _ak_us_daily(".NDX")[["date", "close"]]
        d["date"] = pd.to_datetime(d["date"])
        d["close"] = pd.to_numeric(d["close"], errors="coerce")
        return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if symbol == "GOLD":
        # 黄金：上海金 Au99.99，优先用本地缓存
        gold_path = os.path.join(engine.CACHE_DIR, "gold_sge.pkl")
        if os.path.exists(gold_path):
            d = pd.read_pickle(gold_path).copy()
            # 缓存里 date 可能是索引，重置回来
            if "date" not in d.columns:
                d = d.reset_index()
            d["date"] = pd.to_datetime(d["date"])
            d["close"] = pd.to_numeric(d["close"], errors="coerce")
            return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        import akshare as ak
        d = ak.spot_golden_benchmark_sge()
        d["date"] = pd.to_datetime(d["交易时间"])
        d["close"] = pd.to_numeric(d["早盘价"], errors="coerce")
        return d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return engine.load_price_daily(symbol)


@st.cache_data(ttl=TTL_HOURS * 3600, show_spinner=False, persist="disk")
def load_data(index, symbol, _bust=0):
    if symbol.startswith("CSI:"):
        # 中证指数：价格 + PE 都来自 legulegu（新浪/东财取不到）
        pe = engine.load_pe_percentile(index, 60, ttl_hours=TTL_HOURS)
        px = _price_from_legulegu(index)
        return engine.build_daily(px, pe)
    if symbol == "SP500":
        # 标普500：席勒PE 自带价格（sp500_close），月度数据，1871~今
        # 不需要单独拉价格源（新浪/东财都慢且限流）
        d = engine.load_sp500_shiller_percentile(60, ttl_hours=TTL_HOURS)
        df = d[["date", "sp500_close", "pct"]].copy()
        df.columns = ["date", "close", "pct"]
        df["date"] = pd.to_datetime(df["date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close", "pct"]).sort_values("date").reset_index(drop=True)
        return df
    if symbol == "NDX":
        # 纳指100：优先用本地完整历史（1985~今），否则用新浪（2014~今）
        # ⚠️ 美股长牛，价格分位天然偏高，策略容易"永远觉得贵"
        full_path = os.path.join(engine.CACHE_DIR, "ndx_full_history.pkl")
        if os.path.exists(full_path):
            px = pd.read_pickle(full_path)[["date", "close"]].copy()
            px["date"] = pd.to_datetime(px["date"])
        else:
            import akshare as ak
            px = _ak_us_daily(".NDX")[["date", "close"]]
            px["date"] = pd.to_datetime(px["date"])
            px["close"] = pd.to_numeric(px["close"], errors="coerce")
            px = px.dropna().sort_values("date").reset_index(drop=True)
        # 用价格历史分位（60 个月窗口）
        px["pct"] = (
            px["close"]
            .rolling(250 * 12 // 12, min_periods=250 * 12 // 12)
            .apply(lambda x: (x <= x.iloc[-1]).sum() / len(x) * 100, raw=False)
        )
        return px.dropna(subset=["pct"]).reset_index(drop=True)
    if symbol == "GOLD":
        # 黄金：上海金 Au99.99，无 PE → 用价格分位
        # ⚠️ 黄金是避险资产，价格驱动因素跟股票完全不同，估值分位参考意义有限
        # 优先用本地缓存（避免上海金交易所接口超时）
        gold_path = os.path.join(engine.CACHE_DIR, "gold_sge.pkl")
        if os.path.exists(gold_path):
            d = pd.read_pickle(gold_path).copy()
            d["date"] = pd.to_datetime(d["date"])
        else:
            import akshare as ak
            d = ak.spot_golden_benchmark_sge()
            d["date"] = pd.to_datetime(d["交易时间"])
            d["close"] = pd.to_numeric(d["早盘价"], errors="coerce")
            d = d.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        # 用价格历史分位（60 个月窗口）
        d["pct"] = (
            d["close"]
            .rolling(250 * 12 // 12, min_periods=250 * 12 // 12)
            .apply(lambda x: (x <= x.iloc[-1]).sum() / len(x) * 100, raw=False)
        )
        return d.dropna(subset=["pct"]).reset_index(drop=True)
    return engine.get_data(index, symbol, 60, ttl_hours=TTL_HOURS)


def build_states_df(ranges, freqs, amounts):
    return pd.DataFrame({
        "分位下界": [r[0] for r in ranges],
        "分位上界": [r[1] for r in ranges],
        "频率": freqs,
        "金额(元)": amounts,
    })


def df_to_config(df, gate, ladder):
    states = []
    for _, r in df.iterrows():
        lo, hi = int(r["分位下界"]), int(r["分位上界"])
        if hi <= lo:
            continue
        states.append({"range": [lo, hi], "freq": FREQ_MAP[r["频率"]], "amount": float(r["金额(元)"])})
    states.sort(key=lambda s: s["range"][0])
    return {
        "buy_states": states,
        "sell": {"min_valuation_pct": gate, "ladder": ladder},
    }


def monthly_equiv(df):
    total = 0.0
    for _, r in df.iterrows():
        total += float(r["金额(元)"]) * FREQ_PER_YEAR[FREQ_MAP[r["频率"]]] / 12
    return total


def run_backtest(df_market, cfg, start, end):
    sub = df_market[(df_market["date"] >= pd.Timestamp(start)) & (df_market["date"] <= pd.Timestamp(end))]
    sub = sub.reset_index(drop=True)
    if len(sub) < 10:
        return None

    # 标普500 是月度数据：强制所有档位用 monthly（引擎按"每月第一天"执行）
    if symbol == "SP500":
        cfg = dict(cfg)
        cfg["buy_states"] = [{**st, "freq": "monthly"} for st in cfg["buy_states"]]
    res = engine.simulate(sub, cfg, sell_mode="B")
    # 累计投入序列
    inv_series = []
    cum = 0.0
    buy_by_date = {}
    sell_by_date = {}
    for t in res["trades"]:
        d = t["date"]
        if t["action"] == "buy":
            buy_by_date.setdefault(d, []).append(t)
        else:
            sell_by_date.setdefault(d, []).append(t)
    for d in sub["date"]:
        for t in buy_by_date.get(d, []):
            cum += t["amount"]
        inv_series.append(round(cum, 2))

    daily = res["daily"]
    value_series = [round(float(s * c + h), 2) for s, c, h in
                    zip(daily["shares"], daily["close"], daily["cash"])]
    ret_series = [None if pd.isna(x) else round(float(x), 2) for x in daily["pos_return"]]

    buys = [[t["date"].strftime("%Y-%m-%d"), t["price"]] for t in res["trades"] if t["action"] == "buy"]
    sells = [[t["date"].strftime("%Y-%m-%d"), t["price"]] for t in res["trades"] if t["action"] == "sell"]

    last_price = float(sub["close"].iloc[-1])
    final_value = res["shares"] * last_price + res["cash"]
    maxdd = 0.0
    invested_peak = 0.0
    for i, v in enumerate(value_series):
        if inv_series[i] > invested_peak:
            invested_peak = inv_series[i]
        if invested_peak > 1e-9:
            dd = v / invested_peak - 1
            if dd < maxdd:
                maxdd = dd
    days = (sub["date"].iloc[-1] - sub["date"].iloc[0]).days
    months = days / 30.44
    if months < 1.0:
        months = 1.0

    return {
        "res": res,
        "sub": sub,
        "dates": [d.strftime("%Y-%m-%d") for d in sub["date"]],
        "close": [round(float(x), 2) for x in sub["close"]],
        "pct": [round(float(x), 1) for x in sub["pct"]],
        "invested_series": inv_series,
        "value_series": value_series,
        "return_series": ret_series,
        "buys": buys,
        "sells": sells,
        "final_value": final_value,
        "invested": res["invested"],
        "total_return": (final_value / res["invested"] - 1) * 100 if res["invested"] > 0 else 0,
        "n_buys": len(buys),
        "n_sells": len(sells),
        "max_loss": min(0.0, maxdd) * 100,
        "avg_monthly": res["invested"] / months,
        "months": months,
    }


# ==================== 侧边栏 ====================
st.sidebar.title("⚙️ 配置")

index_name = st.sidebar.selectbox("标的", list(INDEX_OPTIONS.keys()))
symbol = INDEX_OPTIONS[index_name]

theme_choice = st.sidebar.selectbox(
    "图表配色", ["自动", "浅色", "深色"], index=0,
    help="自动会跟随页面主题；若自动判断不对，可手动指定",
)
THEME = {"自动": "auto", "浅色": "light", "深色": "dark"}[theme_choice]

df_market = load_data(index_name, symbol)
dmin, dmax = df_market["date"].min().date(), df_market["date"].max().date()
age = engine.cache_age_hours(index_name, symbol)
age_txt = "无缓存" if age is None else (
    "刚刚更新" if age < 0.05 else (f"{age*60:.0f} 分钟前" if age < 1 else f"{age:.1f} 小时前")
)
st.sidebar.caption(f"📅 数据截至 **{dmax}**（{age_txt}，TTL {TTL_HOURS}h）")

if st.sidebar.button("🔄 刷新数据（拉最新）", width="stretch"):
    for fname in (f"{index_name}_{symbol}_60.pkl", f"pe_{index_name}.pkl"):
        fp = os.path.join(engine.CACHE_DIR, fname)
        if os.path.exists(fp):
            os.remove(fp)
    st.cache_data.clear()
    st.rerun()

c1, c2 = st.sidebar.columns(2)
default_start = max(pd.Timestamp("2015-01-04").date(), dmin)
# 标普500 数据从 1995 年开始（5年分位需要前置数据），默认从 2000 年开始更合理
if symbol == "SP500":
    default_start = max(pd.Timestamp("2000-01-01").date(), dmin)
start = c1.date_input("开始", value=default_start, min_value=dmin, max_value=dmax, key=f"start_{index_name}")
end = c2.date_input("结束", value=dmax, min_value=dmin, max_value=dmax, key=f"end_{index_name}")

st.sidebar.subheader("档位设置")
preset_name = st.sidebar.selectbox("预设", list(PRESETS.keys()))
preset = PRESETS[preset_name]
st.sidebar.caption("← 档位细节在主区顶部调整")

with st.sidebar.expander("止盈设置（卖出）"):
    gate = st.slider("估值分位 ≥ 该值才卖出", 0, 100, 80, step=5,
                     help="0 = 关闭估值闸门，只看盈利")
    p1 = st.number_input("第一档盈利 %", 0, 200, 30, step=5)
    r1 = st.slider("卖出比例 1", 0.0, 1.0, 0.33, step=0.01)
    p2 = st.number_input("第二档盈利 %", 0, 300, 50, step=5)
    r2 = st.slider("卖出比例 2", 0.0, 1.0, 0.33, step=0.01)
    p3 = st.number_input("第三档盈利 %", 0, 500, 80, step=5)
    r3 = st.slider("卖出比例 3", 0.0, 1.0, 0.34, step=0.01)
ladder = [{"profit": p1, "ratio": r1}, {"profit": p2, "ratio": r2}, {"profit": p3, "ratio": r3}]

with st.sidebar.expander("💰 财务校验"):
    income = st.number_input("月收入（税后）", 0, 1_000_000, 20000, step=1000)
    expense = st.number_input("月固定支出", 0, 1_000_000, 10000, step=500)
    cash_on_hand = st.number_input("手上现金（元）", 0, 100_000_000, 60000, step=10000)
    drop = st.slider("假设收入下降 %", 0, 80, 30, step=5)

# ==================== 主区 ====================
st.title("📈 定投沙盘")

# ===== 档位设置（主区，宽度足够）=====
with st.expander("⚙️ 档位设置（可直接修改）", expanded=True):
    n = len(preset)
    default_amounts = {3: [10, 10, 0], 5: [100, 80, 50, 10, 0]}.get(n, [10] * n)
    key_suffix = str(abs(hash(preset_name)) % 100000)

    hdr = st.columns([0.8, 0.8, 1.1, 1.1, 1.0])
    hdr[0].markdown("**分位下界**")
    hdr[1].markdown("**分位上界**")
    hdr[2].markdown("**定投频率**")
    hdr[3].markdown("**金额(元)**")
    hdr[4].markdown("**月等效**")

    states_config = []
    for i, (lo, hi) in enumerate(preset):
        c1, c2, c3, c4, c5 = st.columns([0.8, 0.8, 1.1, 1.1, 1.0])
        lo_v = c1.number_input("下界", value=int(lo), min_value=0, max_value=99, key=f"lo_{i}_{key_suffix}", label_visibility="collapsed")
        hi_v = c2.number_input("上界", value=int(hi), min_value=1, max_value=100, key=f"hi_{i}_{key_suffix}", label_visibility="collapsed")
        freq_v = c3.selectbox("频率", list(FREQ_MAP.keys()), index=1, key=f"freq_{i}_{key_suffix}", label_visibility="collapsed")
        amt_v = c4.number_input("金额", value=float(default_amounts[i]), min_value=0.0, step=10.0, key=f"amt_{i}_{key_suffix}", label_visibility="collapsed")
        me_i = amt_v * FREQ_PER_YEAR[FREQ_MAP[freq_v]] / 12
        c5.caption(f"{me_i:,.0f} 元/月")
        states_config.append({"range": [lo_v, hi_v], "freq": FREQ_MAP[freq_v], "amount": amt_v})

    total_me = sum(s["amount"] * FREQ_PER_YEAR[s["freq"]] / 12 for s in states_config)
    st.caption(f"各档合计（若同时投入）约 **{total_me:,.0f} 元/月**；实际平均投入见下方指标。")

cfg = {"buy_states": states_config, "sell": {"min_valuation_pct": gate, "ladder": ladder}}

# 校验区间连续性
ranges_ok = True
prev = 0
for s in sorted(states_config, key=lambda x: x["range"][0]):
    if s["range"][0] != prev:
        ranges_ok = False
    prev = s["range"][1]

if not ranges_ok:
    st.error("分位区间不连续（应从 0 开始、连续到 100）。请检查档位设置。")
    st.stop()

result = run_backtest(df_market, cfg, start, end)
if result is None:
    st.warning("所选时间范围内数据不足，请调整日期。")
    st.stop()

# ---- 关键指标 ----
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("累计投入", f"{result['invested']:,.0f}")
k2.metric("平均月投入", f"{result['avg_monthly']:,.0f}")
k3.metric("最终市值", f"{result['final_value']:,.0f}")
k4.metric("总收益率", f"{result['total_return']:+.1f}%")
k5.metric("最大浮亏", f"{result['max_loss']:.1f}%")
k6.metric("买入/卖出", f"{result['n_buys']}/{result['n_sells']}")

# ---- 图1：价格 + 买卖点 + 分位 ----
bounds = [s["range"][1] for s in sorted(states_config, key=lambda x: x["range"][0])][:-1]
fig1 = charts.price_chart(result["dates"], result["close"], result["pct"],
                          result["buys"], result["sells"], bounds, gate, theme=THEME)
components.html(fig1, height=390, scrolling=False)

# ---- 对比区 ----
if "saved" not in st.session_state:
    st.session_state.saved = []

colA, colB = st.columns([1, 3])
with colA:
    label = st.text_input("这条配置的名字", value=f"配置{len(st.session_state.saved) + 1}", key="label_in")
    if st.button("📌 保存用于对比", width="stretch"):
        st.session_state.saved.append({
            "label": label,
            "invested_series": result["invested_series"],
            "value_series": result["value_series"],
            "return_series": result["return_series"],
            "dates": result["dates"],
            "summary": {
                "投入": result["invested"], "市值": result["final_value"],
                "收益": result["total_return"], "浮亏": result["max_loss"],
            },
        })
        st.rerun()
with colB:
    if st.session_state.saved:
        st.write("已保存：" + "、".join(s["label"] for s in st.session_state.saved))
        if st.button("🗑 清空对比"):
            st.session_state.saved = []
            st.rerun()

# ---- 图2：市值 vs 投入（含对比）----
all_inv = [result["invested_series"]] + [s["invested_series"] for s in st.session_state.saved]
all_val = [result["value_series"]] + [s["value_series"] for s in st.session_state.saved]
all_labels = ["当前"] + [s["label"] for s in st.session_state.saved]
fig2 = charts.value_chart(result["dates"], all_inv, all_val, all_labels, theme=THEME)
components.html(fig2, height=350, scrolling=False)

# ---- 图3：收益率（含对比）----
all_ret = [result["return_series"]] + [s["return_series"] for s in st.session_state.saved]
ladder_vals = [p1, p2, p3]
fig3 = charts.return_chart(result["dates"], all_ret, all_labels, ladder_vals, theme=THEME)
components.html(fig3, height=310, scrolling=False)

# ---- 对比汇总表 ----
if st.session_state.saved:
    st.subheader("📊 配置对比")
    rows = [{"配置": "当前", **{k: (f"{v:,.0f}" if k in ("投入", "市值") else f"{v:+.1f}%")
                              for k, v in {"投入": result["invested"], "市值": result["final_value"],
                                           "收益": result["total_return"], "浮亏": result["max_loss"]}.items()}}]
    for s in st.session_state.saved:
        rows.append({"配置": s["label"], **{k: (f"{v:,.0f}" if k in ("投入", "市值") else f"{v:+.1f}%")
                                           for k, v in s["summary"].items()}})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---- 财务校验 ----
ck = finance.check({
    "monthly_income": income, "monthly_expense": expense,
    "savings": cash_on_hand, "emergency_months": 6,
    "weekly_invest": result["avg_monthly"] * 12 / 52, "income_drop_pct": drop,
})
st.subheader("💰 财务校验")
cols = st.columns(len(ck["items"]))
for c, item in zip(cols, ck["items"]):
    icon = {"ok": "✅", "warn": "⚠️", "fail": "⛔"}[item["level"]]
    c.markdown(f"**{icon} {item['name']}**")
    c.caption(item["msg"])

st.divider()
st.caption("沙盘基于历史数据回放，不代表未来收益。仅用于理解参数影响，不构成投资建议。")

# ==================== 全历史价格参考 ====================
with st.expander("📊 全历史价格参考（2002~今，含 2008 金融危机）"):
    full_px = load_full_price(symbol)
    full_dates = [d.strftime("%Y-%m-%d") for d in full_px["date"]]
    full_close = [round(float(x), 2) for x in full_px["close"]]

    # 重大危机事件标注（仅股票类指数有意义，商品/美股不适用）
    crisis_events = []
    if symbol not in ("SP500", "NDX", "GOLD"):
        crisis_events = [
            {"date": "2008-10-16", "label": "2008 金融危机（最高 5877）"},
            {"date": "2008-11-04", "label": "2008 金融危机（最低 1628，-72%）"},
            {"date": "2015-06-12", "label": "2015 股灾（5178）"},
            {"date": "2016-02-29", "label": "2015 股灾（2687，-48%）"},
            {"date": "2018-12-28", "label": "2018 熊市"},
        ]
        # 只保留数据范围内的事件
        crisis_events = [e for e in crisis_events if full_px["date"].min() <= pd.Timestamp(e["date"]) <= full_px["date"].max()]

    # 数据范围提示
    data_years = (full_px["date"].max() - full_px["date"].min()).days / 365.25
    if data_years < 15:
        st.caption(f"⚠️ 该标的数据仅覆盖最近 {data_years:.1f} 年（{full_px['date'].min().date()} ~ {full_px['date'].max().date()}），"
                   "未包含 2008 金融危机等更早的历史事件。")
    elif symbol in ("SP500", "NDX"):
        st.caption(f"📅 该标的数据覆盖 {data_years:.1f} 年（{full_px['date'].min().date()} ~ {full_px['date'].max().date()}）。")

    fig_ref = charts.long_term_price_chart(full_dates, full_close, crisis_events, height=320, theme=THEME)
    components.html(fig_ref, height=330, scrolling=False)

    st.warning(
        "⚠️ **历史警示**：2008 年金融危机期间，上证曾从 6124 点跌至 1664 点（-73%），"
        "沪深300 从 5877 点跌至 1628 点（-72%）。"
        "**本沙盘的回测只能从 2010 年开始，未覆盖该极端情况。**"
        "你看到的『最大浮亏』并非史上最坏，仓位设计应按『能承受 -50% 以上浮亏』来考虑。"
    )

# ==================== 导出 ====================
import os
import json

SLUG = {
    "沪深300": "hs300", "中证500": "zz500", "上证50": "sz50", "创业板指": "cyb",
    "中证1000": "zz1000", "中证800": "zz800", "中证100": "zz100",
    "上证180": "sh180", "深证100": "sz100", "创业板50": "cyb50",
    "上证红利": "hongli_sh", "深证红利": "hongli_sz", "中证红利": "hongli_zz",
    "标普500": "sp500",
    "纳指100": "ndx",
    "黄金": "gold",
}
slug = SLUG.get(index_name, "plan")
config_filename = f"config-{slug}.json"
today = pd.Timestamp.now().strftime("%Y-%m-%d")

export_config = {
    "name": f"{index_name}-{len(states_config)}档",
    "window_months": 60,
    "buy_states": states_config,
    "sell": cfg["sell"],
}
export_settings = {
    "start_date": today,
    "track": [{"index": index_name, "symbol": symbol, "config": config_filename}],
    "notify": {"on_transition": True, "daily_digest": True, "humanize": True},
}

st.header("📤 导出到推送配置（累加，不覆盖）")

# 负担确认
me_ratio = (result["avg_monthly"] / (income - expense) * 100) if (income - expense) > 0 else None
flags = "｜".join(f"{ {'ok':'✅','warn':'⚠️','fail':'⛔'}[i['level']] }{i['name']}" for i in ck["items"])
st.info(
    f"**当前标的：{index_name}**｜月均投入约 **{result['avg_monthly']:,.0f} 元**"
    + (f"，占月结余 {(income - expense):,.0f} 的 **{me_ratio:.1f}%**。" if me_ratio is not None else "。")
    + f"\n\n现实性校验：{flags}"
    + f"\n\n历史回放（{start} ~ {end}）：总收益 **{result['total_return']:+.1f}%**，"
      f"最大浮亏 **{result['max_loss']:.1f}%**。—— 历史不代表未来。"
)

# ---------- 读取现有 settings.json ----------
HERE = os.path.dirname(os.path.abspath(__file__))
MONITOR_DIR = os.path.abspath(os.path.join(HERE, "..", "step1-monitor-fork"))
SETTINGS_PATH = os.path.join(MONITOR_DIR, "settings.json")
local_mode = os.path.isdir(MONITOR_DIR)

def _load_current():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

current = _load_current()
existing_track = (current or {}).get("track", [])

# 当前配置中的标的
st.markdown("**当前推送配置包含的标的：**")
if existing_track:
    st.dataframe(
        pd.DataFrame([{"标的": t["index"], "配置文件": t["config"]} for t in existing_track]),
        hide_index=True, width="stretch",
    )
    st.caption(f"起始日：{(current or {}).get('start_date', '—')}")
else:
    st.caption("（还没有推送配置）")

# ---------- 合并预览 ----------
merged_track = [t for t in existing_track if t["index"] != index_name]
merged_track.append({"index": index_name, "symbol": symbol, "config": config_filename})
merged_settings = {
    "start_date": (current or {}).get("start_date") or today,
    "track": merged_track,
    "notify": (current or {}).get("notify") or {"on_transition": True, "daily_digest": True, "humanize": True},
}

added = len(merged_track) > len(existing_track)
updated = any(t["index"] == index_name for t in existing_track)
if added:
    st.success(f"添加后，推送配置将包含 **{len(merged_track)} 个标的**：" + "、".join(t["index"] for t in merged_track))
elif updated:
    st.info(f"「{index_name}」已在配置中，导出将**更新**它的参数（其他标的保留）。")

# ---------- 两列预览 + 下载 ----------
colL, colR = st.columns(2)
with colL:
    st.markdown(f"**1️⃣ `{config_filename}`**（{index_name} 的档位 + 止盈）")
    st.code(json.dumps(export_config, ensure_ascii=False, indent=2), language="json")
    st.download_button(
        f"💾 下载 {config_filename}",
        data=json.dumps(export_config, ensure_ascii=False, indent=2),
        file_name=config_filename, mime="application/json", width="stretch",
        key="dl_config",
    )
with colR:
    st.markdown(f"**2️⃣ `settings.json`**（合并后，{len(merged_track)} 个标的）")
    st.code(json.dumps(merged_settings, ensure_ascii=False, indent=2), language="json")
    st.download_button(
        "💾 下载 settings.json",
        data=json.dumps(merged_settings, ensure_ascii=False, indent=2),
        file_name="settings.json", mime="application/json", width="stretch",
        key="dl_settings",
    )

# ---------- 写入 ----------
if local_mode:
    st.markdown(f"**直接写入**：`{MONITOR_DIR}`")
    b1, b2 = st.columns(2)
    with b1:
        if st.button(f"➕ 把「{index_name}」写入推送配置", type="primary", width="stretch"):
            try:
                with open(os.path.join(MONITOR_DIR, config_filename), "w", encoding="utf-8") as f:
                    json.dump(export_config, f, ensure_ascii=False, indent=2)
                with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                    json.dump(merged_settings, f, ensure_ascii=False, indent=2)
                st.success(f"✅ 已写入。当前推送配置含 {len(merged_track)} 个标的："
                           + "、".join(t["index"] for t in merged_track))
                st.rerun()
            except Exception as e:
                st.error(f"写入失败：{e}")
    with b2:
        if updated and st.button(f"➖ 把「{index_name}」从配置中移除", width="stretch"):
            try:
                new_track = [t for t in existing_track if t["index"] != index_name]
                new_settings = {**current, "track": new_track}
                with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                    json.dump(new_settings, f, ensure_ascii=False, indent=2)
                st.success(f"已移除「{index_name}」。剩余：" + ("、".join(t['index'] for t in new_track) or "无"))
                st.rerun()
            except Exception as e:
                st.error(f"移除失败：{e}")
else:
    st.caption("（云端模式：仅提供下载，请手动上传到仓库）")
