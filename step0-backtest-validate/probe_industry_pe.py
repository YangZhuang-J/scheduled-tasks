# -*- coding: utf-8 -*-
"""绕过 akshare 固定映射，直接调乐咕 API 测试行业指数 PE 是否可得"""
import pandas as pd
import py_mini_racer
from datetime import datetime
from akshare.stock.valuation.stock_a_pe_and_pb import hash_code
from akshare.stock.valuation.stock_a_indicator import get_cookie_csrf
from akshare.utils import http


def index_pe_lg_any(index_code):
    js = py_mini_racer.MiniRacer()
    js.eval(hash_code)
    token = js.call("hex", datetime.now().date().isoformat()).lower()
    url = "https://legulegu.com/api/stockdata/index-basic-pe"
    params = {"token": token, "indexCode": index_code}
    r = http.get(url, params=params,
                 **get_cookie_csrf(url="https://legulegu.com/stockdata/sz50-ttm-lyr"))
    data = r.json()
    if "data" not in data or not data["data"]:
        return None
    df = pd.DataFrame(data["data"])
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("Asia/Shanghai").dt.date
    return df


codes = {
    "中证白酒": "399997.SZ",
    "全指医药": "000991.SH",
    "中证银行": "399986.SZ",
    "中证传媒": "399971.SZ",
    "中证军工": "399967.SZ",
    "全指消费": "000990.SH",
    "全指信息": "000993.SH",
    "中证医疗": "399989.SZ",
    "中证A50": "930050.CSI",
    "创业板指": "399006.SZ",
}
print(f"{'指数':<10}{'代码':<14}结果")
print("-" * 60)
for name, code in codes.items():
    try:
        df = index_pe_lg_any(code)
        if df is None or len(df) == 0:
            print(f"{name:<10}{code:<14}空/无数据")
        else:
            print(f"{name:<10}{code:<14}OK {len(df)}条 {df['date'].iloc[0]}~{df['date'].iloc[-1]}")
    except Exception as e:
        print(f"{name:<10}{code:<14}FAIL {type(e).__name__}: {str(e)[:60]}")
