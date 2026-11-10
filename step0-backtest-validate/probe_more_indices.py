# -*- coding: utf-8 -*-
"""验证：除沪深300外，其他宽基/行业指数的 价格 + 估值 数据是否同样可得"""
import akshare as ak
import pandas as pd

# (名称, 新浪价格代码, 乐咕乐股PE中文名)
targets = [
    ("上证50",          "sh000016", "上证50"),
    ("中证500",         "sh000905", "中证500"),
    ("中证1000",        "sh000852", "中证1000"),
    ("创业板指",        "sz399006", "创业板指"),
    ("中证A50(新宽基)", "sh000688", None),          # 太新，乐咕可能没有
    ("中证白酒(行业)",  "sz399997", "中证白酒"),
    ("全指医药(行业)",  "sh000991", "全指医药"),
    ("中证银行(行业)",  "sz399986", "中证银行"),
    ("中证传媒(行业)",  "sz399971", "中证传媒"),
    ("中证军工(行业)",  "sz399967", "中证军工"),
]

print(f"{'指数':<18}{'价格(新浪)':<28}{'估值PE(乐咕)':<28}")
print("-" * 76)
for name, code, lg in targets:
    # 价格
    try:
        df = ak.stock_zh_index_daily(symbol=code)
        px = f"OK {len(df)}条 {df['date'].iloc[0]}~{df['date'].iloc[-1]}"
    except Exception as e:
        px = f"FAIL {type(e).__name__}"
    # 估值
    if lg:
        try:
            df2 = ak.stock_index_pe_lg(symbol=lg)
            pe = f"OK {len(df2)}条 {df2['日期'].iloc[0]}~{df2['日期'].iloc[-1]}"
        except Exception as e:
            pe = f"FAIL {type(e).__name__}"
    else:
        pe = "(未试,太新)"
    print(f"{name:<18}{px:<28}{pe:<28}")

print()
print("=== 中证A50 估值：试中证官网接口(看能否拿到全历史) ===")
try:
    df = ak.stock_zh_index_value_csindex(symbol="930050")
    print("shape:", df.shape, "cols:", list(df.columns))
    print(df.head(2).to_string())
except Exception as e:
    print("FAIL", type(e).__name__, str(e)[:150])
