# -*- coding: utf-8 -*-
"""探索 akshare 里可用的指数估值(PE/PB)历史接口"""
import akshare as ak
import inspect

print("=== akshare 中与 估值/PE/PB 相关的函数名 ===")
names = [n for n in dir(ak) if any(k in n.lower() for k in ["pe", "pb", "value", "valuation", "index_lg", "stock_index"])]
for n in sorted(names):
    print("  ", n)

print()
print("=== 逐个尝试拉取沪深300 PE/PB 历史 ===")
def probe(name, fn):
    try:
        df = fn()
        print(f"[OK]   {name}  shape={getattr(df,'shape',None)}")
        if hasattr(df, "columns"):
            print(f"       cols={list(df.columns)}")
            print(df.head(3).to_string())
            print("       tail:"); print(df.tail(2).to_string())
        else:
            print(df)
    except Exception as e:
        print(f"[FAIL] {name}  -> {type(e).__name__}: {str(e)[:150]}")
    finally:
        print("-"*100)

probe("stock_index_pe_lg(沪深300)", lambda: ak.stock_index_pe_lg(symbol="沪深300"))
probe("stock_index_pb_lg(沪深300)", lambda: ak.stock_index_pb_lg(symbol="沪深300"))

print("=== stock_zh_index_value_csindex 签名 ===")
try:
    print(inspect.signature(ak.stock_zh_index_value_csindex))
except Exception as e:
    print("sig err", e)

print("=== stock_index_pe_lg 签名 ===")
try:
    print(inspect.signature(ak.stock_index_pe_lg))
except Exception as e:
    print("sig err", e)
