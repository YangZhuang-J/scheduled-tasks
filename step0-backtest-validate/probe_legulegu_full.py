# -*- coding: utf-8 -*-
"""抓取 legulegu index-basic 页面的完整指数代码清单，并验证之前失败的代码"""
import re
import time
import pandas as pd
import py_mini_racer
from datetime import datetime
import requests
import akshare as ak

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

print("=== 抓取 legulegu index-basic 页面 ===")
html = requests.get("https://legulegu.com/stockdata/index-basic", headers={"User-Agent": UA}, timeout=40).text
# 提取 indexCode=XXX 和它后面的名称
pairs = re.findall(r'indexCode=([A-Za-z0-9.]+)[^>]*>([^<]+)', html)
seen = {}
for code, name in pairs:
    name = name.strip()
    if name and code not in seen:
        seen[code] = name
print(f"  共提取到 {len(seen)} 个指数代码")

df = pd.DataFrame([{"indexCode": k, "name": v} for k, v in seen.items()])
df.to_csv("legulegu_index_map.csv", index=False, encoding="utf-8-sig")
print(df.to_string(index=False))

# 验证之前失败的正确代码
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

print("\n=== 验证之前'无数据'的正确代码 ===")
for code, name in [("000933.SH", "中证医药(000933.SH)"), ("000510.SH", "中证A500"),
                   ("000991.SH", "全指医药"), ("000932.SH", "中证消费"),
                   ("931186.CSI", "中证科技"), ("000820.CSI", "煤炭指数")]:
    try:
        d = lg_pe(code)
        print(f"  {name:<22} {code:<14} {'✅ '+str(len(d))+'行 '+str(d['date'].iloc[0])+'~'+str(d['date'].iloc[-1]) if d is not None else '❌ 无数据'}")
    except Exception as e:
        print(f"  {name:<22} {code:<14} ❌ {type(e).__name__}: {str(e)[:70]}")
    time.sleep(4)
