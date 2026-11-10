"""同花顺创业板低估定投策略：自然语言参数修改与范围校验。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NUMBER_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)")


def within_skill(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("配置文件必须位于 skill 目录内：%s" % resolved) from exc
    return resolved


def load_cfg(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cfg(path: Path, cfg: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def all_params(cfg: dict) -> list:
    return list(cfg.get("tunable_params", [])) + list(cfg.get("fund_params", []))


def _value_from_text(text: str, param: dict, other_tokens=()) -> tuple:
    label = param.get("label", param.get("key"))
    key = param.get("key", label)
    clause = text
    for sep in ["，", ",", "；", ";", "。", "、"]:
        parts = text.split(sep)
        hit = [part for part in parts if label in part or key in part]
        if hit:
            clause = hit[0]
            break
    pos = clause.find(label)
    token = label
    if pos < 0:
        pos = clause.find(key)
        token = key
    segment = clause[pos + len(token):] if pos >= 0 else clause
    stops = [segment.find(t) for t in other_tokens if t and segment.find(t) >= 0]
    if stops:
        segment = segment[: min(stops)]
    match = NUMBER_RE.search(segment)
    if not match:
        return None, "没有识别到数值"
    value = float(match.group(1))
    if "%" in segment and param.get("max", 1) <= 1:
        value /= 100.0
    return value, None


def _validate(param: dict, value: float) -> tuple:
    label = param.get("label", param.get("key"))
    if "min" in param and value < param["min"]:
        return False, "%s 合法范围为 %s~%s" % (label, param["min"], param["max"])
    if "max" in param and value > param["max"]:
        return False, "%s 合法范围为 %s~%s" % (label, param["min"], param["max"])
    return True, None


def _refresh_explanation(cfg: dict) -> None:
    explanation = cfg.setdefault("explanation", {})
    explanation["rules"] = (
        "创业板指五年 PE 分位决定基础申购倍数；赎回现金占比决定加速系数；"
        "分位 ≥%g%% 触发每日 %g%% 高位赎回，<%g%% 重置；现金按年化 %g%% 计息"
        % (
            float(cfg.get("trigger_percentile", 70)),
            float(cfg.get("daily_redeem_ratio", 0.01)) * 100.0,
            float(cfg.get("reset_percentile", 70)),
            float(cfg.get("cash_interest_rate", 0.014)) * 100.0,
        )
    )
    explanation["params"] = "、".join(
        p.get("label", p.get("key", "")) for p in cfg.get("tunable_params", [])
    )


def apply_param_updates(text: str, cfg: dict, params=None) -> tuple:
    params = list(params if params is not None else all_params(cfg))
    labels = [p.get("label", p.get("key")) for p in params]
    by_key = {p["key"]: p for p in params}
    messages = []
    matched = False
    changed = False
    processed = set()

    freq_param = by_key.get("extra_contribution_freq")
    if freq_param:
        freq_requested = (
            freq_param.get("label", "") in text
            or freq_param["key"] in text
            or ("新增" in text and any(choice in text for choice in freq_param.get("choices", [])))
        )
        if freq_requested:
            matched = True
            choices = [choice for choice in freq_param.get("choices", []) if choice in text]
            if choices:
                cfg[freq_param["key"]] = choices[-1]
                messages.append("%s -> %s" % (freq_param["label"], choices[-1]))
                changed = True
            else:
                messages.append(
                    "%s 仅支持：%s"
                    % (freq_param["label"], "/".join(freq_param.get("choices", [])))
                )
            processed.add(freq_param["key"])

    amount_param = by_key.get("extra_contribution_amount")
    if amount_param and "新增" in text and amount_param["label"] not in text and amount_param["key"] not in text:
        match = re.search(r"新增[^\d+-]*([+-]?\d+(?:\.\d+)?)", text)
        if match:
            matched = True
            value = float(match.group(1))
            ok, error = _validate(amount_param, value)
            if ok:
                cfg[amount_param["key"]] = value
                messages.append("%s -> %s" % (amount_param["label"], value))
                changed = True
            else:
                messages.append("超出范围：" + error)
            processed.add(amount_param["key"])

    for param in params:
        key = param["key"]
        if key in processed or "choices" in param:
            continue
        label = param.get("label", key)
        if label not in text and key not in text:
            continue
        matched = True
        value, error = _value_from_text(text, param, labels)
        if error:
            messages.append(label + "：" + error)
            continue
        ok, error = _validate(param, value)
        if not ok:
            messages.append("超出范围：" + error)
            continue
        cfg[key] = value
        messages.append("%s -> %s" % (label, value))
        changed = True

    if not matched and any(word in text for word in ("改成", "调整", "调参", "新增")):
        messages.append("没有识别到可调参数，候选参数：" + "、".join(labels))
    if changed:
        _refresh_explanation(cfg)
    return cfg, messages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--set", action="append", required=True)
    args = parser.parse_args()
    config_path = within_skill(args.config)
    cfg = load_cfg(config_path)
    for instruction in args.set:
        cfg, messages = apply_param_updates(instruction, cfg)
        for message in messages:
            print(message)
    save_cfg(config_path, cfg)


if __name__ == "__main__":
    main()
