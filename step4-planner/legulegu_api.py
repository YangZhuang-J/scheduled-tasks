# -*- coding: utf-8 -*-
"""
乐咕乐股(legulegu.com) 指数估值 API —— 绕过 akshare 硬编码的 12 个指数

能力：
  - get_pe(index_code) / get_pb(index_code)   # A股宽基+行业+红利 等 37+，恒生 HSI 也可
  - get_sp500_shiller()                        # 标普500 席勒PE(CAPE)，1871~今
  - list_indices() / resolve(name_or_code)     # 完整指数代码表 + 中文名解析

说明：
  - 依赖 akshare(借用其内部 token 算法) + py_mini_racer
  - legulegu 有速率限制，连续请求请 sleep 3~5s
  - indexCode 后缀很讲究：.SH(上交所) / .SZ(深交所) / .CSI(中证) / 小写h(全收益)，大小写敏感
"""
import os
import pandas as pd
import py_mini_racer
from datetime import datetime
import akshare as ak

_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "legulegu_index_map.csv")

_g = ak.stock_index_pe_lg.__globals__
_HASH_CODE = _g["hash_code"]
_HTTP = _g["http"]
_COOKIE = _g["get_cookie_csrf"]

# akshare 硬编码的 12 个（作为基础映射补充）
_AKSHARE_12 = {
    "上证50": "000016.SH", "沪深300": "000300.SH", "上证380": "000009.SH",
    "创业板50": "399673.SZ", "中证500": "000905.SH", "上证180": "000010.SH",
    "深证红利": "399324.SZ", "深证100": "399330.SZ", "中证1000": "000852.SH",
    "上证红利": "000015.SH", "中证100": "000903.SH", "中证800": "000906.SH",
}
# 手动确认不在上述任何清单里的
_EXTRA = {
    "创业板指": "399006.SZ", "科创50": "000688.SH", "恒生指数": "HSI",
    "中证500成长": "000905.SH",  # 占位，避免 KeyError
}


def _token():
    js = py_mini_racer.MiniRacer()
    js.eval(_HASH_CODE)
    return js.call("hex", datetime.now().date().isoformat()).lower()


def _get(endpoint, params, referer):
    r = _HTTP.get(f"https://legulegu.com/api/stockdata/{endpoint}",
                  params=params, **_COOKIE(url=referer))
    return r.json()


def _norm(df):
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("Asia/Shanghai").dt.date
    return df


def get_pe(index_code):
    """
    指数 PE 历史（月度）。

    字段口径（重要！legulegu 的 PE 分三种算法）：
      addTtmPe / addLyrPe   = 加权(整体法 ∑市值/∑净利) = 【标准指数PE】，定投用它
      ttmPe    / lyrPe      = 等权(算术平均)，受高PE小票影响偏大
      middleTtmPe/middleLyrPe = 中位数
    例(沪深300 2026-11): 加权TTM=12.68  等权TTM=30.13  中位数TTM=17.78
    """
    j = _get("index-basic-pe", {"token": _token(), "indexCode": index_code},
             "https://legulegu.com/stockdata/sz50-ttm-lyr")
    if not j.get("data"):
        raise ValueError(f"PE 无数据: {index_code}（检查后缀 .SH/.SZ/.CSI 与大小写）")
    return _norm(pd.DataFrame(j["data"]))


def get_pe_clean(index_code):
    """返回中文清晰列名的关键 PE 字段（便于直接用）"""
    d = get_pe(index_code)
    return d.rename(columns={
        "date": "日期", "close": "收盘",
        "addTtmPe": "加权TTM_PE", "ttmPe": "等权TTM_PE", "middleTtmPe": "中位数TTM_PE",
        "addLyrPe": "加权静态_PE", "lyrPe": "等权静态_PE",
        "totalMv": "总市值", "ttmPeQuantile": "加权TTM分位",
    })


def get_pb(index_code):
    """指数 PB 历史（月度）"""
    j = _get("index-basic-pb", {"token": _token(), "indexCode": index_code},
             "https://legulegu.com/stockdata/sz50-ttm-lyr")
    if not j.get("data"):
        raise ValueError(f"PB 无数据: {index_code}")
    return _norm(pd.DataFrame(j["data"]))


def get_sp500_shiller():
    """标普500 席勒市盈率(CAPE)，1871~今（月度）"""
    j = _get("sp500-shiller-pe", {"token": _token()},
             "https://legulegu.com/stockdata/sp500-shiller-pe")
    df = pd.DataFrame({
        "date": pd.to_datetime(j["dates"]).date,
        "shiller_pe": pd.to_numeric(j["shillerPe"], errors="coerce"),
        "sp500_close": pd.to_numeric(j["sp500Close"], errors="coerce"),
    })
    return df


def build_map():
    """合并 akshare12 + 官网43 + 手动补充 → 完整代码表，存 CSV"""
    rows = []
    for name, code in {**_AKSHARE_12, **_EXTRA}.items():
        rows.append({"indexCode": code, "name": name})
    # 读取已抓取的官网清单
    p = _MAP_PATH
    if os.path.exists(p):
        scraped = pd.read_csv(p)
        for _, r in scraped.iterrows():
            name = str(r["name"]).replace("市盈率", "").replace("市净率", "").strip()
            if name and name not in ("恐慌&贪心指标(情绪指标)",):
                rows.append({"indexCode": str(r["indexCode"]).strip(), "name": name})
    df = pd.DataFrame(rows).drop_duplicates(subset=["indexCode"]).reset_index(drop=True)
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return df


def list_indices():
    if not os.path.exists(_MAP_PATH):
        return build_map()
    return pd.read_csv(_MAP_PATH)


def resolve(name_or_code):
    m = list_indices()
    if name_or_code in set(m["indexCode"]):
        return name_or_code
    hit = m[m["name"] == name_or_code]
    if len(hit):
        return hit.iloc[0]["indexCode"]
    raise ValueError(f"未在映射表中找到: {name_or_code}")


if __name__ == "__main__":
    m = build_map()
    print(f"完整指数映射表：{len(m)} 个")
    print(m.to_string(index=False))
