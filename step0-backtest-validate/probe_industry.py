# -*- coding: utf-8 -*-
import akshare as ak

print("=== 行业指数价格：中证行业指数(新浪) ===")
for sym, name in [("sz399997","中证白酒"), ("sz399933","中证医药"), ("sz399975","证券公司"),
                  ("sh000819","有色金属"), ("sz399986","中证银行"), ("sh000827","中证环保")]:
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
        print(f"  {name:<8} {sym}  {len(df)}天 {df['date'].iloc[0]}~{df['date'].iloc[-1]}")
    except Exception as e:
        print(f"  {name:<8} {sym}  ❌ {type(e).__name__}: {str(e)[:70]}")

print()
print("=== 申万行业指数(新版 index_hist_sw) ===")
try:
    df = ak.sw_index_first_info()
    print("  一级行业数:", len(df), " 列:", list(df.columns)[:8])
    print(df.head(3).to_string())
except Exception as e:
    print("  ❌", type(e).__name__, str(e)[:120])

print()
print("=== 申万行业指数历史行情 ===")
try:
    df = ak.index_hist_sw(symbol="801780", period="day")  # 银行
    print("  801780(银行):", len(df), "天", list(df.columns))
except Exception as e:
    print("  ❌", type(e).__name__, str(e)[:120])

print()
print("=== 巨潮行业市盈率 stock_industry_pe_ratio_cninfo ===")
try:
    df = ak.stock_industry_pe_ratio_cninfo(symbol="证监会行业分类", date="20241105")
    print("  shape:", df.shape, " 列:", list(df.columns))
    print(df.head(5).to_string())
except Exception as e:
    print("  ❌", type(e).__name__, str(e)[:150])
