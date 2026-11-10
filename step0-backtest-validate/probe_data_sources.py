# -*- coding: utf-8 -*-
"""第 0 步 · 数据源探索：确认沪深300/纳指100/标普500 的价格与估值接口可用性"""
import akshare as ak
import pandas as pd

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 200)

def probe(name, fn):
    try:
        df = fn()
        if df is None or len(df) == 0:
            print(f"[空]   {name}")
            return None
        print(f"[OK]   {name}  shape={df.shape}")
        print(f"       columns={list(df.columns)}")
        print(df.head(2).to_string())
        print(f"       ...tail:")
        print(df.tail(2).to_string())
        return df
    except Exception as e:
        print(f"[FAIL] {name}  -> {type(e).__name__}: {str(e)[:200]}")
        return None
    finally:
        print("-" * 100)

print("=" * 100)
print("一、沪深300 指数日线价格")
print("=" * 100)
probe("index_zh_a_hist(symbol=000300, 东财)", lambda: ak.index_zh_a_hist(symbol="000300", period="daily", start_date="20140101", end_date="20251231"))
probe("stock_zh_index_daily(sh000300, 新浪)", lambda: ak.stock_zh_index_daily(symbol="sh000300"))

print("=" * 100)
print("二、沪深300 估值（PE/PB）")
print("=" * 100)
probe("stock_zh_index_value_csindex(000300, 中证官网)", lambda: ak.stock_zh_index_value_csindex(symbol="000300"))
probe("index_value_hist_funddb(沪深300 市盈率)", lambda: ak.index_value_hist_funddb(symbol="沪深300", indicator="市盈率"))
probe("index_value_hist_funddb(沪深300 市净率)", lambda: ak.index_value_hist_funddb(symbol="沪深300", indicator="市净率"))

print("=" * 100)
print("三、纳指100 / 标普500 日线价格")
print("=" * 100)
probe("index_global_hist_em(纳斯达克100)", lambda: ak.index_global_hist_em(symbol="纳斯达克100", start_date="20140101", end_date="20251231"))
probe("index_global_hist_em(标普500)", lambda: ak.index_global_hist_em(symbol="标普500", start_date="20140101", end_date="20251231"))
probe("index_us_stock_sina(.NDX 纳指100)", lambda: ak.index_us_stock_sina(symbol=".NDX"))
probe("index_us_stock_sina(.INX 标普500)", lambda: ak.index_us_stock_sina(symbol=".INX"))

print("=" * 100)
print("四、候选：全球指数 PE（若有）")
print("=" * 100)
probe("index_global_hist_em 支持符号列表", lambda: ak.index_global_hist_em(symbol="标普500"))
