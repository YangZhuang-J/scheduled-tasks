"""场外基金数据取数层：仅使用同花顺金融数据API（fuyao.aicubes.cn），统一本地缓存。

网络要点：本机系统代理不可用，必须 bypass 代理（requests trust_env=False）。
数据缺失或接口异常时直接报错退出，不做兜底切换（规范 §5.1：数据源仅同花顺金融数据API）。
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


FUYAO_BASE = "https://fuyao.aicubes.cn"
SKILL_ID = "gem-cash-pool-strategy"
SKILL_VERSION = "0.3.25"  # 保留供兼容调用方读取；不再写入请求头。
SKILL_ROOT = Path(__file__).resolve().parents[1]


def _load_env_key() -> str:
    return os.environ.get("FUYAO_API_KEY", "").strip()


def _latest_completed_weekday(today: Optional[datetime] = None) -> str:
    """返回最近一个已结束的工作日；回测和信号不使用当天未收盘数据。"""
    current = (today or datetime.now()) - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.strftime("%Y-%m-%d")


def _within_skill(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(SKILL_ROOT)
    except ValueError as exc:
        raise ValueError("文件路径必须位于 skill 目录内：%s" % resolved) from exc
    return resolved


def now_ms() -> int:
    return int(time.time() * 1000)


def ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def date_to_ms(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp() * 1000)


def _make_session() -> requests.Session:
    sess = requests.Session()
    # 关键：本机系统代理无法连接，直接绕过。
    sess.trust_env = False
    sess.headers["User-Agent"] = "fund-strategy-skill/0.1"
    return sess


class FuyaoClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        ai_platform: Optional[str] = None,
        run_id: Optional[str] = None,
        skill_action: str = "env_check",
        trade_plan_state: str = "none",
    ):
        self.api_key = api_key or _load_env_key()
        if not self.api_key:
            raise RuntimeError(
                "未配置 同花顺金融数据API数据密钥。请将 Key 配置为环境变量 FUYAO_API_KEY；"
                "可以在当前操作中临时提供 Key；请勿回显或将 Key 写入任何文件。"
            )
        self.session = _make_session()
        self.session.headers["X-api-key"] = self.api_key
        # 兼容旧调用方保留上下文参数；按策略规范 v0.29 不将其写入请求头。
        self.session.headers["X-THS-Skill-Id"] = SKILL_ID

    def set_context(
        self,
        *,
        skill_action: Optional[str] = None,
        trade_plan_state: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """兼容旧版上下文调用；v0.29 仅发送策略 ID。"""
        return None

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not path.startswith("/") or "://" in path:
            raise ValueError("同花顺金融数据API路径必须是站内绝对路径")
        request_headers = {"X-THS-Skill-Id": SKILL_ID}
        r = self.session.get(
            FUYAO_BASE + path,
            params=params,
            headers=request_headers,
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
        code = payload.get("code")
        if code == 2001:
            raise RuntimeError(
                "同花顺金融数据API数据密钥缺失或无效（code=2001）。请重新提供 Key，或配置环境变量 FUYAO_API_KEY。"
            )
        if code == 2003:
            raise RuntimeError(
                "当前同花顺金融数据API数据密钥无权访问该接口（code=2003），请在 Fuyao 管理页确认权限。"
            )
        if code not in (0, None):
            raise RuntimeError(
                "同花顺金融数据API 接口错误（code=%s）：%s"
                % (code, payload.get("message") or "未提供错误信息")
            )
        return payload

    def search(self, q: str, asset_type: str = "fund-otc", limit: int = 20) -> List[Dict[str, Any]]:
        data = self._get(
            "/api/meta/tickers/search",
            {"q": q, "asset_type": asset_type, "limit": limit},
        ).get("data") or {}
        return data.get("item") or []

    def list_tickers(self, asset_type: str = "fund-otc") -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        offset = 0
        limit = 1000
        while True:
            data = self._get(
                "/api/meta/tickers/list",
                {"asset_type": asset_type, "limit": limit, "offset": offset},
            ).get("data") or {}
            items = data.get("item") or []
            out.extend(items)
            if len(items) < limit:
                break
            offset += limit
        return out

    def profile(self, thscode: str, fund_type: str = "otc") -> Dict[str, Any]:
        data = self._get(
            "/api/fund/profile/detail",
            {"fund_type": fund_type, "thscode": thscode},
        ).get("data") or {}
        items = data.get("item") or []
        return items[0] if items else {}

    def nav(
        self,
        thscode: str,
        fund_type: str = "otc",
        range_: str = "fyear",
        nav_type: str = "adj",
    ) -> pd.DataFrame:
        data = self._get(
            "/api/fund/performance/nav",
            {
                "fund_type": fund_type,
                "thscode": thscode,
                "range": range_,
                "nav_type": nav_type,
            },
        ).get("data") or {}
        items = data.get("item") or []
        df = pd.DataFrame(items)
        if df.empty:
            return pd.DataFrame(columns=["date", "adj_nav", "unit_nav"])
        df["date"] = df["nav_date"].map(ms_to_date)
        df = df.rename(
            columns={
                "adj_nav": "adj_nav",
                "unit_nav": "unit_nav",
            }
        )
        cols = ["date"]
        if "adj_nav" in df.columns:
            cols.append("adj_nav")
        if "unit_nav" in df.columns:
            cols.append("unit_nav")
        return df[cols]

    def indicators(
        self,
        thscode: str,
        start_ms: int,
        end_ms: int,
        fund_type: str = "otc",
    ) -> pd.DataFrame:
        data = self._get(
            "/api/fund/performance/indicators-historical",
            {
                "fund_type": fund_type,
                "thscode": thscode,
                "start": start_ms,
                "end": end_ms,
            },
        ).get("data") or {}
        items = data.get("item") or []
        df = pd.DataFrame(items)
        expected = ["date", "rsi_pct", "donchian_channel", "pe_ttm_5y_pct"]
        if df.empty:
            return pd.DataFrame(columns=expected)
        if "date_ms" in df.columns:
            df["date"] = df["date_ms"].map(ms_to_date)
        df = df.rename(
            columns={
                "rsi_pct": "rsi_pct",
                "donchian_channel": "donchian_channel",
                "track_index_pe_ttm_five_year_percentile": "pe_ttm_5y_pct",
            }
        )
        return df.reindex(columns=expected)

    def returns(self, thscode: str, fund_type: str = "otc") -> Dict[str, Any]:
        data = self._get(
            "/api/fund/performance/returns",
            {"fund_type": fund_type, "thscode": thscode},
        ).get("data") or {}
        items = data.get("item") or []
        return items[0] if items else {}

    def drawdowns(self, thscode: str, fund_type: str = "otc") -> Dict[str, Any]:
        data = self._get(
            "/api/fund/performance/drawdowns",
            {"fund_type": fund_type, "thscode": thscode},
        ).get("data") or {}
        items = data.get("item") or []
        return items[0] if items else {}

    def index_history(self, thscode: str, start_ms: int, end_ms: int) -> pd.DataFrame:
        data = self._get(
            "/api/a-share-index/prices/historical",
            {"thscode": thscode, "interval": "1d", "start": start_ms, "end": end_ms},
        ).get("data") or {}
        items = data.get("item") or []
        df = pd.DataFrame(items)
        if df.empty:
            return pd.DataFrame(columns=["date", "close"])
        df["date"] = df["date_ms"].map(ms_to_date)
        df = df.rename(columns={"close_price": "close"})
        return df[["date", "close"]]


class DataClient:
    """统一取数入口：仅使用同花顺金融数据API（fuyao.aicubes.cn），落本地缓存。

    缓存命中最近一个已结束工作日时直接复用；缓存落后时按接口支持的范围更新并合并回缓存。
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        *,
        api_key: Optional[str] = None,
        ai_platform: Optional[str] = None,
        run_id: Optional[str] = None,
        skill_action: str = "backtest",
        trade_plan_state: str = "none",
    ):
        self.fuyao = FuyaoClient(
            api_key=api_key,
            ai_platform=ai_platform,
            run_id=run_id,
            skill_action=skill_action,
            trade_plan_state=trade_plan_state,
        )
        self.cache_dir = _within_skill(cache_dir or SKILL_ROOT / "data_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, thscode: str, kind: str) -> Path:
        safe_code = re.sub(r"[^A-Za-z0-9_-]", "_", thscode)
        safe_kind = re.sub(r"[^A-Za-z0-9_-]", "_", kind)
        return _within_skill(self.cache_dir / f"{safe_code}_{safe_kind}.csv")

    def _read_cache(self, path: Path) -> Optional[pd.DataFrame]:
        if path.exists():
            return pd.read_csv(path, dtype={"date": str})
        return None

    @staticmethod
    def _latest_cache_date(frame: Optional[pd.DataFrame]) -> Optional[pd.Timestamp]:
        if frame is None or frame.empty or "date" not in frame.columns:
            return None
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
        if dates.empty:
            return None
        return dates.max().normalize()

    @classmethod
    def _cache_is_current(cls, frame: Optional[pd.DataFrame]) -> bool:
        latest = cls._latest_cache_date(frame)
        if latest is None:
            return False
        return latest >= pd.Timestamp(_latest_completed_weekday())

    @classmethod
    def _incremental_start_ms(cls, frame: Optional[pd.DataFrame], requested_start_ms: int) -> int:
        latest = cls._latest_cache_date(frame)
        if latest is None:
            return requested_start_ms
        next_date = (latest + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        return max(requested_start_ms, date_to_ms(next_date))

    @staticmethod
    def _merge_cache(cached: Optional[pd.DataFrame], fresh: pd.DataFrame) -> pd.DataFrame:
        frames = [frame for frame in (cached, fresh) if frame is not None and not frame.empty]
        if not frames:
            return pd.DataFrame()
        merged = pd.concat(frames, ignore_index=True)
        if "date" in merged.columns:
            merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            merged = merged.dropna(subset=["date"])
            merged = merged.drop_duplicates(subset=["date"], keep="last").sort_values("date")
        return merged.reset_index(drop=True)

    def fetch_nav(
        self,
        thscode: str,
        fund_type: str = "otc",
        range_: str = "fyear",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        cache = self._cache_path(thscode, "nav")
        cached = self._read_cache(cache) if use_cache else None
        if use_cache and self._cache_is_current(cached):
            return cached  # type: ignore[return-value]
        df = self.fuyao.nav(thscode, fund_type, range_, nav_type="adj")
        if not df.empty:
            df = self._merge_cache(cached, df)
            df.to_csv(cache, index=False)
            return df
        return cached if cached is not None else df

    def fetch_indicators(
        self,
        thscode: str,
        start_ms: int,
        end_ms: int,
        fund_type: str = "otc",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        cache = self._cache_path(thscode, "indicators")
        cached = self._read_cache(cache) if use_cache else None
        if use_cache and self._cache_is_current(cached):
            return cached  # type: ignore[return-value]
        request_start_ms = self._incremental_start_ms(cached, start_ms) if use_cache else start_ms
        df = self.fuyao.indicators(thscode, request_start_ms, end_ms, fund_type)
        if not df.empty:
            df = self._merge_cache(cached, df)
            df.to_csv(cache, index=False)
            return df
        return cached if cached is not None else df

    def fetch_series(
        self,
        thscode: str,
        fund_type: str = "otc",
        years: int = 5,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """合并净值 + 指标，得到本地回测所需的完整序列。"""
        end_ms = now_ms()
        start_ms = end_ms - int(years * 365 * 24 * 3600 * 1000)
        nav = self.fetch_nav(thscode, fund_type, "fyear", use_cache)
        ind = self.fetch_indicators(thscode, start_ms, end_ms, fund_type, use_cache)
        if nav.empty:
            return nav
        if ind.empty:
            return nav
        df = nav.merge(ind, on="date", how="left").sort_values("date").reset_index(drop=True)
        return df

    def fetch_index(
        self,
        index_thscode: str,
        years: int = 10,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        cache = self._cache_path(index_thscode, "index")
        cached = self._read_cache(cache) if use_cache else None
        if use_cache and self._cache_is_current(cached):
            return cached  # type: ignore[return-value]
        end_ms = now_ms()
        start_ms = end_ms - int(years * 365 * 24 * 3600 * 1000)
        request_start_ms = self._incremental_start_ms(cached, start_ms) if use_cache else start_ms
        df = self.fuyao.index_history(index_thscode, request_start_ms, end_ms)
        if not df.empty:
            df = self._merge_cache(cached, df)
            df.to_csv(cache, index=False)
            return df
        return cached if cached is not None else df


def _self_test() -> None:
    client = DataClient()
    print("search 沪深300:")
    for item in client.fuyao.search("沪深300", asset_type="fund-otc", limit=5):
        print("  ", item.get("thscode"), item.get("ticker"), item.get("name"), item.get("asset_type"))

    print("nav/indicators for 025480.OF:")
    df = client.fetch_series("025480.OF", "otc", years=5, use_cache=False)
    print(df.head())
    print(df.tail())
    print("rows:", len(df))


if __name__ == "__main__":
    _self_test()
