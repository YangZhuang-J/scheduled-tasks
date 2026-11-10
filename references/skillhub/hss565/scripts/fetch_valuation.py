#!/usr/bin/env python3
"""
指数基金估值数据抓取脚本

当 WebFetch 无法直接解析页面时，使用本脚本从公开 API/数据源抓取估值数据。
支持从蛋卷基金指数估值 API、天天基金等源获取数据。

用法:
    python fetch_valuation.py --index <指数简称或代码>
    python fetch_valuation.py --index 沪深300
    python fetch_valuation.py --index 000300 --fund 510300
    python fetch_valuation.py --list           # 列出蛋卷支持的所有指数

输出: JSON 格式的估值数据，可直接用于生成报告。

依赖: 仅使用 Python 标准库（urllib, json），无需额外安装。

注意:
    - 数据源为公开接口，请适度使用，避免高频请求。
    - 数据每日收盘后更新，盘中数据可能为前一交易日。
    - 本脚本仅作数据抓取辅助，估值结论需结合完整分析。
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime


# ============ 数据源配置 ============

# 蛋卷基金指数估值 API（公开接口，返回 JSON）
DANJUAN_INDEX_EVA_URL = "https://danjuanfunds.com/djapi/index_eva/dj"

# 天天基金基金详情页（用于补充基金层信息）
EASTMONEY_FUND_URL = "http://fundgz.1234567.com.cn/js/{fund_code}.js"


# ============ HTTP 请求工具 ============

def http_get_json(url, headers=None, timeout=10):
    """发起 GET 请求并解析 JSON 响应。"""
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            data = resp.read().decode(charset)
            return json.loads(data)
    except urllib.error.URLError as e:
        print(f"[网络错误] {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"[JSON解析错误] {e}", file=sys.stderr)
        return None


def http_get_text(url, headers=None, timeout=10):
    """发起 GET 请求并返回文本。"""
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset)
    except urllib.error.URLError as e:
        print(f"[网络错误] {e}", file=sys.stderr)
        return None


# ============ 蛋卷基金指数估值 ============

def fetch_danjuan_all_indices():
    """从蛋卷 API 获取所有指数估值列表。"""
    data = http_get_json(DANJUAN_INDEX_EVA_URL)
    if not data:
        return None
    # 响应格式: {"result_code": 0, "data": {"items": [...]}}
    items = data.get("data", {}).get("items", [])
    return items


def find_index_in_danjuan(items, keyword):
    """在蛋卷指数列表中查找匹配的指数。"""
    keyword = keyword.strip().lower()
    results = []
    for item in items:
        name = item.get("name", "")
        code = item.get("code", "")
        # 名称或代码匹配
        if keyword in name.lower() or keyword == code.lower():
            results.append(item)
    return results


def parse_danjuan_item(item):
    """解析蛋卷指数估值条目。"""
    # 蛋卷字段说明：
    # name: 指数名称
    # code: 指数代码
    # pe: 市盈率
    # pe_percentile: PE 历史分位（0-1）
    # pb: 市净率
    # pb_percentile: PB 历史分位
    # dividend_yield: 股息率
    # roe: 净资产收益率
    # ts: 数据时间戳
    return {
        "source": "蛋卷基金",
        "index_name": item.get("name", ""),
        "index_code": item.get("code", ""),
        "pe": item.get("pe"),
        "pe_percentile": item.get("pe_percentile"),
        "pe_percentile_pct": f"{item.get('pe_percentile', 0) * 100:.1f}%" if item.get("pe_percentile") is not None else None,
        "pb": item.get("pb"),
        "pb_percentile": item.get("pb_percentile"),
        "pb_percentile_pct": f"{item.get('pb_percentile', 0) * 100:.1f}%" if item.get("pb_percentile") is not None else None,
        "dividend_yield": item.get("dividend_yield"),
        "dividend_yield_pct": f"{item.get('dividend_yield', 0) * 100:.2f}%" if item.get("dividend_yield") is not None else None,
        "roe": item.get("roe"),
        "timestamp": item.get("ts"),
        "data_date": _ts_to_date(item.get("ts")),
    }


def valuation_status(percentile):
    """根据分位（0-1）判断估值状态。"""
    if percentile is None:
        return "未知"
    p = percentile * 100
    if p < 20:
        return "极度低估"
    elif p < 40:
        return "低估"
    elif p < 60:
        return "适中"
    elif p < 80:
        return "高估"
    else:
        return "极度高估"


def _ts_to_date(ts):
    """将时间戳转为日期字符串，自动识别秒/毫秒。"""
    if not ts:
        return None
    try:
        # 毫秒级时间戳（13位）转为秒
        if ts > 1e12:
            ts = ts / 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (OSError, ValueError, OverflowError):
        return None


# ============ 天天基金实时估值 ============

def fetch_eastmoney_fund_rtg(fund_code):
    """从天天基金获取基金实时估值（盘中估算）。"""
    url = EASTMONEY_FUND_URL.format(fund_code=fund_code)
    text = http_get_text(url)
    if not text:
        return None
    # 响应格式: jsonpgz({...});
    text = text.strip()
    if text.startswith("jsonpgz("):
        text = text[8:-2]
    try:
        data = json.loads(text)
        return {
            "source": "天天基金",
            "fund_code": data.get("fundcode"),
            "fund_name": data.get("name"),
            "estimated_nav": data.get("gsz"),
            "estimated_change_pct": data.get("gszzl"),
            "nav_date": data.get("jzrq"),
            "estimated_time": data.get("gztime"),
        }
    except json.JSONDecodeError:
        return None


# ============ 主流程 ============

def cmd_list():
    """列出蛋卷支持的所有指数。"""
    print("正在从蛋卷基金获取指数估值列表...")
    items = fetch_danjuan_all_indices()
    if not items:
        print("获取失败", file=sys.stderr)
        sys.exit(1)
    print(f"共 {len(items)} 个指数：\n")
    print(f"{'指数名称':<16} {'代码':<12} {'PE':<8} {'PE分位':<10} {'PB':<8} {'股息率':<8}")
    print("-" * 70)
    for item in items:
        name = item.get("name", "")
        code = item.get("code", "")
        pe = item.get("pe", "-")
        pe_p = item.get("pe_percentile")
        pe_p_str = f"{pe_p*100:.1f}%" if pe_p is not None else "-"
        pb = item.get("pb", "-")
        dv = item.get("dividend_yield")
        dv_str = f"{dv*100:.2f}%" if dv is not None else "-"
        print(f"{name:<16} {code:<12} {pe!s:<8} {pe_p_str:<10} {pb!s:<8} {dv_str:<8}")


def cmd_fetch(index_keyword, fund_code=None):
    """抓取指定指数的估值数据。"""
    print(f"正在查询指数: {index_keyword}")
    items = fetch_danjuan_all_indices()
    if not items:
        print("从蛋卷获取数据失败，请检查网络或稍后重试", file=sys.stderr)
        sys.exit(1)

    matches = find_index_in_danjuan(items, index_keyword)
    if not matches:
        print(f"未找到匹配 '{index_keyword}' 的指数", file=sys.stderr)
        print(f"蛋卷共支持 {len(items)} 个指数，可使用 --list 查看完整列表", file=sys.stderr)
        sys.exit(1)

    if len(matches) > 1:
        print(f"找到 {len(matches)} 个匹配指数，请选择更精确的关键词：\n", file=sys.stderr)
        for m in matches:
            print(f"  - {m.get('name')} ({m.get('code')})", file=sys.stderr)
        sys.exit(1)

    result = parse_danjuan_item(matches[0])
    result["valuation_status"] = valuation_status(matches[0].get("pe_percentile"))

    # 若提供基金代码，补充基金实时估值
    if fund_code:
        print(f"正在补充基金 {fund_code} 实时估值...")
        fund_data = fetch_eastmoney_fund_rtg(fund_code)
        if fund_data:
            result["fund_realtime"] = fund_data
        else:
            result["fund_realtime"] = None
            print(f"[提示] 未能获取基金 {fund_code} 的实时估值", file=sys.stderr)

    # 输出结果
    print("\n" + "=" * 50)
    print("估值数据（JSON）")
    print("=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 友好摘要
    print("\n" + "=" * 50)
    print("估值摘要")
    print("=" * 50)
    print(f"指数名称: {result['index_name']} ({result['index_code']})")
    print(f"数据日期: {result['data_date']}")
    if result.get("pe") is not None:
        print(f"PE-TTM:  {result['pe']}  分位: {result['pe_percentile_pct']}  状态: {result['valuation_status']}")
    if result.get("pb") is not None:
        print(f"PB:      {result['pb']}  分位: {result['pb_percentile_pct']}")
    if result.get("dividend_yield_pct"):
        print(f"股息率:  {result['dividend_yield_pct']}")
    if result.get("fund_realtime"):
        fr = result["fund_realtime"]
        print(f"\n基金实时估值: {fr.get('fund_name')} ({fr.get('fund_code')})")
        print(f"  估算净值: {fr.get('estimated_nav')}  涨跌: {fr.get('estimated_change_pct')}%")
        print(f"  估算时间: {fr.get('estimated_time')}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="指数基金估值数据抓取脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python fetch_valuation.py --index 沪深300
  python fetch_valuation.py --index 000300 --fund 510300
  python fetch_valuation.py --list
        """,
    )
    parser.add_argument("--index", help="指数名称或代码（如 '沪深300' 或 '000300'）")
    parser.add_argument("--fund", help="基金代码（可选，补充基金实时估值）")
    parser.add_argument("--list", action="store_true", help="列出蛋卷支持的所有指数")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.index:
        cmd_fetch(args.index, args.fund)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
