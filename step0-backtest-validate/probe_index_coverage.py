# -*- coding: utf-8 -*-
"""验证：除了沪深300，还有哪些指数能拿到 价格 + PE/PB 估值历史"""
import akshare as ak
import pandas as pd

def try_pe(symbol):
    try:
        df = ak.stock_index_pe_lg(symbol=symbol)
        return f"PE有 {len(df)}个月 {df['日期'].iloc[0]}~{df['日期'].iloc[-1]}"
    except Exception as e:
        return f"❌ {type(e).__name__}: {str(e)[:80]}"

def try_pb(symbol):
    try:
        df = ak.stock_index_pb_lg(symbol=symbol)
        return f"PB有 {len(df)}个月"
    except Exception as e:
        return f"❌ {type(e).__name__}: {str(e)[:80]}"

print("="*90)
print("一、乐咕乐股(legulegu) 指数 PE/PB 覆盖情况 —— 逐个试")
print("="*90)
symbols = ["沪深300","上证50","中证500","中证1000","中证A50","中证100",
           "中证800","中证红利","创业板指","科创50","上证180","深证成指",
           "恒生指数","纳斯达克100","标普500"]
for s in symbols:
    print(f"  {s:<10}  {try_pe(s)}")
print()

print("="*90)
print("二、价格数据覆盖（新浪 index 日线）—— 试宽基 + 行业指数代码")
print("="*90)
def try_price(sym):
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
        return f"价格有 {len(df)}天 {df['date'].iloc[0]}~{df['date'].iloc[-1]}"
    except Exception as e:
        return f"❌ {type(e).__name__}: {str(e)[:80]}"

for sym, name in [("sh000905","中证500"), ("sh000016","上证50"), ("sz399006","创业板指"),
                  ("sh000688","科创50"), ("sh000300","沪深300"), ("sh000852","中证1000")]:
    print(f"  {name:<8} {sym:<10} {try_price(sym)}")
print()

print("="*90)
print("三、行业指数：巨潮行业市盈率 stock_industry_pe_ratio_cninfo")
print("="*90)
try:
    df = ak.stock_industry_pe_ratio_cninfo(symbol="证监会行业分类标准")
    print("  可用符号/分类:", list(df.columns) if hasattr(df,'columns') else df)
except Exception as e:
    print("  ❌", type(e).__name__, str(e)[:150])

# 列出可选的行业分类symbol
print("\n  尝试列出巨潮行业分类符号：")
try:
    import inspect
    print("  签名:", inspect.signature(ak.stock_industry_pe_ratio_cninfo))
except Exception as e:
    print("  ", e)
