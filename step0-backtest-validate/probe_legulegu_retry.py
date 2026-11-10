# -*- coding: utf-8 -*-
"""慢速重试：确认标普500/纳指100/恒生科技/有色/证券 在 legulegu 的真实支持情况"""
import time
import pandas as pd
import py_mini_racer
from datetime import datetime
import akshare as ak

g = ak.stock_index_pe_lg.__globals__
hash_code, http, get_cookie_csrf = g["hash_code"], g["http"], g["get_cookie_csrf"]

def lg_pe(indexCode):
    js = py_mini_racer.MiniRacer(); js.eval(hash_code)
    token = js.call("hex", datetime.now().date().isoformat()).lower()
    r = http.get("https://legulegu.com/api/stockdata/index-basic-pe",
                 params={"token": token, "indexCode": indexCode},
                 **get_cookie_csrf(url="https://legulegu.com/stockdata/sz50-ttm-lyr"))
    j = r.json()
    return pd.DataFrame(j["data"]) if j.get("data") else None

tests = [
    ("SPX", "标普500(SPX)"),
    ("NDX", "纳斯达克100(NDX)"),
    ("000819.SH", "有色金属"),
    ("399975.SZ", "证券公司"),
    ("HSTECH", "恒生科技(HSTECH)"),
    ("HSTECH.HI", "恒生科技(.HI)"),
    ("399933.SZ", "中证医药(399933.SZ)"),
    ("000933.CSI", "中证医药(000933.CSI)"),
    ("H30033.CSI", "中证医药(H30033.CSI)"),
]

for code, name in tests:
    try:
        df = lg_pe(code)
        if df is None:
            print(f"  {name:<24} {code:<14} ❌ 无数据")
        else:
            print(f"  {name:<24} {code:<14} ✅ {len(df)}行  {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    except Exception as e:
        print(f"  {name:<24} {code:<14} ❌ {type(e).__name__}: {str(e)[:80]}")
    time.sleep(5)
