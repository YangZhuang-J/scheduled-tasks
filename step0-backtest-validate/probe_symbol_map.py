# -*- coding: utf-8 -*-
import akshare as ak
import inspect

print("=== stock_index_pe_lg 内部支持的符号映射 ===")
try:
    src = inspect.getsource(ak.stock_index_pe_lg)
    # 打印源码里 symbol 相关的映射部分
    import re
    for line in src.splitlines():
        if any(k in line for k in ["symbol", "映射", ":", "{"]) and ("指数" in line or "300" in line or "50" in line or "500" in line or "红利" in line or "创业" in line or "科创" in line or "恒生" in line or "纳斯达克" in line or "标普" in line):
            print("   ", line.strip()[:150])
except Exception as e:
    print("  get source fail:", e)

# 直接尝试打印函数 docstring 里可能有的说明
try:
    doc = ak.stock_index_pe_lg.__doc__
    print("\n=== docstring 前 600 字 ===")
    print(doc[:600] if doc else "(无 docstring)")
except Exception as e:
    print(e)
