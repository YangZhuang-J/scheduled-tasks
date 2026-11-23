# -*- coding: utf-8 -*-
"""解读层：把计算结果说成人话（对「计划」说理，不是对「市场」说理）

铁律：数字全部来自确定性计算，这里只做解读。
LLM 可选（浅层），未配置时用确定性模板。
"""
import os


def _fmt(v):
    if v >= 10000:
        return f"{v/10000:.1f} 万"
    return f"{v:,.0f}"


def _worst_stress(stress_res):
    if not stress_res:
        return 0.0
    return max((s["期间最大浮亏"] for s in stress_res), default=0.0)


def build_narrative(profile, check_res, mc_res, stress_res):
    """生成结构性说理（确定性，不依赖 LLM）"""
    parts = []

    # 第一段：撑不撑得住
    if not check_res["passed"]:
        fails = [i for i in check_res["items"] if i["level"] == "fail"]
        parts.append("### ⛔ 先说最重要的：这个计划现在撑不住\n")
        for f in fails:
            parts.append(f"**{f['name']}**：{f['msg']}")
        parts.append(
            "\n> 在解决这些问题之前，讨论收益没有意义。"
            "**定投的失败，八成不是选错标的，而是计划撑不住、中途被迫离场。**"
        )
        return "\n\n".join(parts)

    parts.append("### ✅ 先看能不能撑住：能\n")
    parts.append("现金流、应急资金、压力测试都过关。这是定投能成功的前提。")
    for w in [i for i in check_res["items"] if i["level"] == "warn"]:
        parts.append(f"- ⚠️ **{w['name']}**：{w['msg']}")

    # 第二段：要承受什么
    worst = _worst_stress(stress_res)
    p90_loss = mc_res["max_loss_p90"] * 100
    parts.append("\n### 😰 你要承受什么（这是最该先看的）\n")
    parts.append(
        f"- 历史回放的真实最坏情况：账面最深亏过 **{worst:.1f}%**\n"
        f"- 模拟中位数：约有 **{mc_res['loss_month_ratio']*100:.0f}% 的月份**是浮亏状态\n"
        f"- 一半的模拟情形，最大浮亏不超过 **{mc_res['max_loss_p50']*100:.0f}%**；"
        f"较糟的一半情形，最大浮亏可达 **{p90_loss:.0f}%**"
    )
    parts.append(
        f"\n> **关键问题不是「能不能赚」，而是「亏到 {p90_loss:.0f}% 时你会不会跑」。**"
        "如果你确定那时会割肉，就说明金额设太大了，应该往下调。"
    )

    # 第三段：大概能怎样
    parts.append("\n### 📈 大概能怎样（不代表未来）\n")
    parts.append(
        f"- 累计投入约 **{_fmt(mc_res['invested_median'])} 元**\n"
        f"- 悲观（10% 分位）：**{_fmt(mc_res['final_p10'])} 元**\n"
        f"- 中性（50% 分位）：**{_fmt(mc_res['final_p50'])} 元**\n"
        f"- 乐观（90% 分位）：**{_fmt(mc_res['final_p90'])} 元**"
    )
    if mc_res["goal_prob"] is not None:
        gp = mc_res["goal_prob"] * 100
        if gp >= 70:
            level = "🎯 很有希望"
        elif gp >= 40:
            level = "⚖️ 有机会，但要加点力"
        else:
            level = "⚠️ 大概率达不成"
        parts.append(
            f"\n**目标 {_fmt(mc_res['goal_amount'])} 元**：达成概率约 **{gp:.0f}%** —— {level}"
        )
        if gp < 70:
            parts.append(
                "> 想提高达成率，有两条路：**增加每期投入**（但先确认现金流撑得住），"
                "或者**延长期限**。不要靠「赌一个更好的策略」来解决。"
            )

    # 第四段：纪律
    parts.append("\n### 🧭 最后一句\n")
    parts.append(
        "这套计划的价值不在「预测」，而在**让你在最难的时候有个明确的规则可以依赖**。"
        "真正决定结果的是：**你能不能在浮亏里继续按计划投入。**"
    )
    return "\n\n".join(parts)


def llm_narrative(profile, check_res, mc_res, stress_res, api_key=None, model="deepseek-chat"):
    """可选：用 LLM 把事实重写成更自然的解读。未配置 key 时返回 None。"""
    key = api_key or os.environ.get("LLM_API_KEY")
    if not key:
        return None
    try:
        import requests
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content":
                    "你是一位理性的投资教练。任务：解读已算好的定投计划结果。"
                    "重点帮用户理性看待风险；绝不预测收益、绝不推荐具体产品。"
                    "必须忠实于给定数字，不得编造。语气直接、诚实、不说教。"},
                {"role": "user", "content":
                    f"用户财务画像：{profile}\n\n"
                    f"现实性校验：{check_res['items']}\n\n"
                    f"沙盘结果：P10={mc_res['final_p10']:.0f}, P50={mc_res['final_p50']:.0f}, "
                    f"P90={mc_res['final_p90']:.0f}, 达成概率={mc_res['goal_prob']}, "
                    f"最大浮亏中位={mc_res['max_loss_p50']*100:.0f}%, "
                    f"浮亏月占比={mc_res['loss_month_ratio']*100:.0f}%\n\n"
                    f"历史压力测试：{stress_res}\n\n"
                    "请写一段 300 字以内的中文解读：先说撑不撑得住，再说要承受什么，最后说大概能怎样。"},
            ],
        }
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=60,
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[LLM] 调用失败，回退模板：{type(e).__name__}: {e}")
        return None
