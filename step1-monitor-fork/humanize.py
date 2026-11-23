# -*- coding: utf-8 -*-
"""模块 A：说人话 —— 把客观数据翻译成让人安心、能坚持的语言。
不引入任何新信息，只做"翻译"。所有话术都是确定性的，可复现。"""


def zone_of(pct, amount):
    """根据分位绝对值 + 是否停买，给人话的区域名。
    用分位绝对值而非配置档位边界，因为配置可能是宽档（如 [20,80]），
    但 77% 实际上已经偏贵，不应该笼统叫「中间区」。"""
    if amount <= 0:
        return "停买区", "按你的规则，这个位置该收手了。"
    if pct < 40:
        return "便宜区", "这是便宜的地方。"
    if pct < 60:
        return "中间区", "这里不便宜也不贵。"
    return "偏贵区", "这里已经不便宜了，但还没到完全收手的程度。"


def explain_percentile(pct):
    """把分位翻译成人话"""
    if pct >= 80:
        return f"当前估值处在历史 **{pct:.0f}% 分位**，也就是说——过去这么多年里，只有 {100-pct:.0f}% 的时间比现在更贵。"
    if pct >= 60:
        return f"当前估值处在历史 **{pct:.0f}% 分位**，比过去 {pct:.0f}% 的时间都要贵一些。"
    if pct >= 40:
        return f"当前估值处在历史 **{pct:.0f}% 分位**，正好在中不溜的位置。"
    if pct >= 20:
        return f"当前估值处在历史 **{pct:.0f}% 分位**，比过去 {pct:.0f}% 的时间都便宜。"
    return f"当前估值处在历史 **{pct:.0f}% 分位**——过去 {100-pct:.0f}% 的时间都比现在贵，这是很少见的便宜位置。"


def explain_action(amount, freq_label, zone_name):
    """解释今天为什么这么投"""
    if amount <= 0:
        return "今天不买入。**规则就是规则**——贵的时候管住手，是这套策略能赚钱的前提。"
    return f"所以今天按计划投 **{amount:g} 元**。这个位置适合的就是：不激进、不停手。"


def comfort(prof_pct, invested, n_buys, amount=100):
    """根据盈亏情况给一句"定心丸"（或提醒）。amount<=0 表示停买区，话术不同。"""
    if invested <= 0:
        return ""
    if prof_pct <= -15:
        return f"⚠️ 浮亏 {prof_pct:.1f}%，看着难受。但请注意：**浮亏不是亏损，只有卖出才变成真亏**。定投的意义就是在下跌时攒更多份额。"
    if prof_pct < -3:
        return f"💡 浮亏 {prof_pct:.1f}%，正常波动。你才买了 {n_buys} 次，定投的曲线还远没走完。"
    if prof_pct < 3:
        return f"💡 基本持平（{prof_pct:+.1f}%）。定投前期本来就是这样，不急。"
    if amount <= 0:
        return (f"💰 浮盈 {prof_pct:+.1f}%，而且已经进入停买区。**这正是策略生效的时候**："
                f"不再往里加钱，若达到你设的止盈阶梯，规则会提示分批卖出。交给规则，不凭感觉。")
    if prof_pct < 20:
        return f"🙂 浮盈 {prof_pct:+.1f}%。继续按计划走，别因为赚了点就提前跑。"
    return f"🎯 浮盈 {prof_pct:+.1f}%。**注意：现在才是最容易犯错的时候**——赚了钱就想落袋，往往会卖飞后面的大涨。让规则决定，不要凭感觉。"


def render(item, transitions_map=None):
    """生成一只指数的"说人话"段落"""
    idx = item["index"]
    pct = item["pct"]
    state = item["state"]
    zone_name, zone_desc = zone_of(pct, state["amount"])
    amount = state["amount"]
    n_buys = item["n_buys"]
    prof = item["profit"]
    invested = item["invested"]
    value = item["value"]

    lines = [f"### {idx} · {zone_name}"]
    lines.append(explain_percentile(pct))
    lines.append(zone_desc)
    lines.append(explain_action(amount, state["freq"], zone_name))
    if invested > 0:
        lines.append(
            f"\n累计投入 **{invested:,.0f}** 元｜当前 **{value:,.0f}** 元｜**{prof:+.1f}%**"
        )
        c = comfort(prof, invested, n_buys, amount)
        if c:
            lines.append(c)
    return "\n\n".join(lines)
