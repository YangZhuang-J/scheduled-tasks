# -*- coding: utf-8 -*-
"""绕过 akshare 硬编码的 12 个指数，直接调 legulegu API 测任意 indexCode"""
import time
import pandas as pd
import py_mini_racer
from datetime import datetime
import akshare as ak

# 从 akshare 内部拿到 token 计算所需的 hash_code / http / cookie
g = ak.stock_index_pe_lg.__globals__
hash_code = g["hash_code"]
http = g["http"]
get_cookie_csrf = g["get_cookie_csrf"]


def lg_pe(indexCode):
    js = py_mini_racer.MiniRacer()
    js.eval(hash_code)
    token = js.call("hex", datetime.now().date().isoformat()).lower()
    url = "https://legulegu.com/api/stockdata/index-basic-pe"
    params = {"token": token, "indexCode": indexCode}
    r = http.get(url, params=params,
                 **get_cookie_csrf(url="https://legulegu.com/stockdata/sz50-ttm-lyr"))
    j = r.json()
    if not j.get("data"):
        return None
    df = pd.DataFrame(j["data"])
    return df


def lg_pb(indexCode):
    js = py_mini_racer.MiniRacer()
    js.eval(hash_code)
    token = js.call("hex", datetime.now().date().isoformat()).lower()
    url = "https://legulegu.com/api/stockdata/index-basic-pb"
    params = {"token": token, "indexCode": indexCode}
    r = http.get(url, params=params,
                 **get_cookie_csrf(url="https://legulegu.com/stockdata/sz50-ttm-lyr"))
    j = r.json()
    if not j.get("data"):
        return None
    return pd.DataFrame(j["data"])


tests = [
    # (indexCode, 名称)
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
    ("000922.CSI", "中证红利(.CSI)"),
    ("000922.SH",  "中证红利(.SH)"),
    ("930050.CSI", "中证A50"),
    ("399997.SZ", "中证白酒(行业)"),
    ("399933.SZ", "中证医药(行业)"),
    ("399975.SZ", "证券公司(行业)"),
    ("000819.SH", "有色金属(行业)"),
    ("HSTECH",    "恒生科技"),
    ("HSI",       "恒生指数"),
    ("SPX",       "标普500"),
    ("NDX",       "纳斯达克100"),
    (".INX",      "标普500(.INX)"),
    (".NDX",      "纳斯达克100(.NDX)"),
]

print("="*100)
print("PE 接口测试 (index-basic-pe)")
print("="*100)
for code, name in tests:
    try:
        df = lg_pe(code)
        if df is None:
            print(f"  {name:<18} {code:<16} ❌ 无数据")
        else:
            print(f"  {name:<18} {code:<16} ✅ {len(df)}行  {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    except Exception as e:
        print(f"  {name:<18} {code:<16} ❌ {type(e).__name__}: {str(e)[:90]}")
    time.sleep(0.8)

print()
print("="*100)
print("PB 接口测试 (index-basic-pb)")
print("="*100)
for code, name in tests[:12]:
    try:
        df = lg_pb(code)
        if df is None:
            print(f"  {name:<18} {code:<16} ❌ 无数据")
        else:
            print(f"  {name:<18} {code:<16} ✅ {len(df)}行")
    except Exception as e:
        print(f"  {name:<18} {code:<16} ❌ {type(e).__name__}: {str(e)[:90]}")
    time.sleep(0.8)
