# -*- coding: utf-8 -*-
"""一次性拉取纳指100完整历史数据（Yahoo Finance），存到本地

运行方式：
  1. 开启 VPN（能访问 Yahoo Finance）
  2. python fetch_ndx_full.py
  3. 数据会保存到 ../step4-planner/cache/ndx_full_history.pkl
"""
import time
import pandas as pd
import requests
from datetime import datetime
from io import StringIO
import os

def fetch_yahoo_full(symbol, start_year, end_year):
    """从 Yahoo Finance 下载完整历史数据"""
    p1 = int(datetime(start_year, 1, 1).timestamp())
    p2 = int(datetime(end_year, 12, 31).timestamp())
    url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}?period1={p1}&period2={p2}&interval=1d&events=history"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print(f"正在下载 {symbol} ({start_year}~{end_year})...")
    t0 = time.time()
    r = requests.get(url, headers=headers, timeout=60)
    elapsed = time.time() - t0

    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text[:200]}")

    df = pd.read_csv(StringIO(r.text))
    print(f"✅ 下载完成: {len(df)} 行, 耗时 {elapsed:.1f}s")
    return df


def main():
    # 纳指100 从 1985 年到 2026 年
    symbol = "^NDX"
    df = fetch_yahoo_full(symbol, 1985, 2026)

    # 数据清洗
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

    print(f"数据范围: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")
    print(f"最新收盘: {df['close'].iloc[-1]:.2f}")

    # 保存到 step4-planner/cache/
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "step4-planner", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    out_path = os.path.join(cache_dir, "ndx_full_history.pkl")
    df.to_pickle(out_path)
    print(f"\n✅ 已保存到: {out_path}")
    print(f"文件大小: {os.path.getsize(out_path) / 1024:.1f} KB")

    # 同时保存一份 CSV（可读）
    csv_path = os.path.join(cache_dir, "ndx_full_history.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✅ CSV 备份: {csv_path}")


if __name__ == "__main__":
    main()
