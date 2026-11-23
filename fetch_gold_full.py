# -*- coding: utf-8 -*-
"""一次性拉取黄金完整历史数据（Yahoo Finance），存到本地

运行方式：
  1. 开启 VPN（能访问 Yahoo Finance）
  2. python fetch_gold_full.py
  3. 数据会保存到 ../step4-planner/cache/gold_full_history.pkl
"""
import time
import pandas as pd
import yfinance as yf
import os


def fetch_gold_full():
    """拉取黄金的完整历史数据"""
    # GC=F 是 COMEX 黄金期货，1970 年至今
    # XAUUSD=X 是伦敦金现货，2003 年至今
    symbols = {
        "GC=F": "COMEX 黄金期货（1970~今）",
        "XAUUSD=X": "伦敦金现货（2003~今）",
    }

    results = {}
    for symbol, desc in symbols.items():
        print(f"\n正在下载 {symbol} ({desc})...")
        t0 = time.time()
        try:
            df = yf.download(symbol, start="1970-01-01", end="2026-12-31", progress=False)
            elapsed = time.time() - t0

            if len(df) == 0:
                print(f"  ⚠️ 无数据，跳过")
                continue

            # 展平多层索引
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df = df.reset_index()
            df = df.rename(columns={"Date": "date", "Close": "close", "Open": "open",
                                    "High": "high", "Low": "low", "Volume": "volume"})
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

            print(f"  ✅ {len(df)} 行, 耗时 {elapsed:.1f}s")
            print(f"     {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}")
            print(f"     最新: {df['close'].iloc[-1]:.2f}")

            results[symbol] = df

        except Exception as e:
            print(f"  ❌ 失败: {type(e).__name__}: {str(e)[:80]}")

    return results


def main():
    results = fetch_gold_full()

    if not results:
        print("\n❌ 所有数据源都失败了，请检查 VPN 连接")
        return

    # 优先用 GC=F（历史最长），否则用 XAUUSD=X
    if "GC=F" in results:
        df = results["GC=F"]
        source = "GC=F (COMEX 黄金期货)"
    elif "XAUUSD=X" in results:
        df = results["XAUUSD=X"]
        source = "XAUUSD=X (伦敦金现货)"
    else:
        return

    # 保存到 step4-planner/cache/
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "step4-planner", "cache")
    os.makedirs(cache_dir, exist_ok=True)

    out_path = os.path.join(cache_dir, "gold_full_history.pkl")
    df.to_pickle(out_path)
    print(f"\n✅ 已保存到: {out_path}")
    print(f"   来源: {source}")
    print(f"   文件大小: {os.path.getsize(out_path) / 1024:.1f} KB")

    # CSV 备份
    csv_path = os.path.join(cache_dir, "gold_full_history.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✅ CSV 备份: {csv_path}")

    # 同时保存一份到上海金缓存（让沙盘直接能用）
    sge_path = os.path.join(cache_dir, "gold_sge.pkl")
    df.to_pickle(sge_path)
    print(f"✅ 已同步到 gold_sge.pkl（沙盘直接可用）")


if __name__ == "__main__":
    main()
