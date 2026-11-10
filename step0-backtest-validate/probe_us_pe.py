# -*- coding: utf-8 -*-
"""探索美股指数 PE 历史数据源（纳指100 / 标普500）"""
import akshare as ak
import inspect
import pandas as pd
import requests

print("=== 候选接口签名 ===")
for n in ["stock_us_valuation_baidu", "stock_market_pe_lg", "stock_market_pb_lg"]:
    try:
        print(f"  {n}: {inspect.signature(getattr(ak, n))}")
    except Exception as e:
        print(f"  {n}: {e}")

print()
print("=== stock_market_pe_lg 试跑 ===")
try:
    df = ak.stock_market_pe_lg(symbol="上证")
    print(df.shape, list(df.columns)); print(df.head(2).to_string()); print(df.tail(2).to_string())
except Exception as e:
    print("FAIL", type(e).__name__, str(e)[:150])

print()
print("=== multpl.com S&P500 月度 PE 抓取 ===")
try:
    url = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
    hdr = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    tables = pd.read_html(requests.get(url, headers=hdr, timeout=30).text)
    print("tables found:", len(tables))
    for i, t in enumerate(tables[:3]):
        print(f"--- table {i} shape={t.shape} cols={list(t.columns)} ---")
        print(t.head(3).to_string())
except Exception as e:
    print("FAIL", type(e).__name__, str(e)[:300])
