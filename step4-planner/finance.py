# -*- coding: utf-8 -*-
"""财务画像 + 现实性校验（第②层）

核心思想：在算收益之前，先算"撑不撑得住"。
四项校验不过关，再高的收益预测都是空中楼阁。
"""


def check(profile):
    """
    profile 字段：
      monthly_income     月收入（税后）
      monthly_expense    月固定支出
      savings            现有储蓄
      emergency_months   希望保留几个月的应急资金（3~6）
      weekly_invest      计划每周投入（中性档）
      income_drop_pct    压力测试：收入下降比例（默认30%）

    返回 dict：
      items: [{name, ok, level, msg}]   level: ok/warn/fail
      monthly_surplus    月结余
      passed             是否全部通过（无 fail）
    """
    inc = float(profile["monthly_income"])
    exp = float(profile["monthly_expense"])
    savings = float(profile["savings"])
    em_months = float(profile.get("emergency_months", 3))
    weekly = float(profile["weekly_invest"])
    drop_pct = float(profile.get("income_drop_pct", 30))

    monthly_invest = weekly * 52 / 12
    surplus = inc - exp
    items = []

    # ① 现金流：定投额不能吃掉全部结余
    if surplus <= 0:
        items.append({"name": "现金流", "level": "fail",
                      "msg": f"每月支出 {exp:,.0f} ≥ 收入 {inc:,.0f}，没有钱可以投。先解决收支平衡。"})
    else:
        ratio = monthly_invest / surplus
        if ratio > 0.8:
            items.append({"name": "现金流", "level": "fail",
                          "msg": f"月投 {monthly_invest:,.0f} 元占月结余 {surplus:,.0f} 的 {ratio*100:.0f}%，太满。"
                                 f"任何意外都会让你断供。建议不超过 50%。"})
        elif ratio > 0.5:
            items.append({"name": "现金流", "level": "warn",
                          "msg": f"月投占月结余 {ratio*100:.0f}%，偏高。留点余地给意外支出。"})
        else:
            items.append({"name": "现金流", "level": "ok",
                          "msg": f"月投 {monthly_invest:,.0f} 元占月结余 {surplus:,.0f} 的 {ratio*100:.0f}%，健康。"})

    # ② 应急资金：投完之后手上还剩几个月生活费
    need_em = exp * em_months
    if savings >= need_em:
        items.append({"name": "应急资金", "level": "ok",
                      "msg": f"现有储蓄 {savings:,.0f} 元，够 {savings/exp:.1f} 个月生活费（建议 ≥{em_months:.0f} 个月）。"})
    else:
        gap = need_em - savings
        items.append({"name": "应急资金", "level": "fail",
                      "msg": f"现有储蓄 {savings:,.0f} 元只够 {savings/exp:.1f} 个月生活费。"
                             f"建议先补到 {need_em:,.0f} 元（还差 {gap:,.0f}），再开始定投。"})

    # ③ 压力测试：收入下降后还撑得住吗
    inc_stress = inc * (1 - drop_pct / 100)
    surplus_stress = inc_stress - exp
    if surplus_stress <= 0:
        items.append({"name": "压力测试", "level": "fail",
                      "msg": f"若收入下降 {drop_pct:.0f}%（降到 {inc_stress:,.0f}），生活就过不下去了。"
                             f"这个计划没有抗风险空间。"})
    else:
        ratio_s = monthly_invest / surplus_stress
        if ratio_s > 1.0:
            items.append({"name": "压力测试", "level": "fail",
                          "msg": f"若收入下降 {drop_pct:.0f}%，月投将超过结余（占用 {ratio_s*100:.0f}%），"
                                 f"必须减投。建议把周投降到 {surplus_stress*12/52*0.7:,.0f} 元以内。"})
        elif ratio_s > 0.7:
            items.append({"name": "压力测试", "level": "warn",
                          "msg": f"若收入下降 {drop_pct:.0f}%，月投将占结余 {ratio_s*100:.0f}%，需要减投应对。"})
        else:
            items.append({"name": "压力测试", "level": "ok",
                          "msg": f"若收入下降 {drop_pct:.0f}%，仍可承受（占用结余 {ratio_s*100:.0f}%）。"})

    # ④ 资金的期限属性：投入的钱应该是 5 年不用的
    if savings > 0 and savings < exp * em_months:
        items.append({"name": "资金属性", "level": "warn",
                      "msg": "注意：定投的钱必须是 5 年内不需要动的钱。若这笔钱近期有用途，请勿投入。"})
    else:
        items.append({"name": "资金属性", "level": "ok",
                      "msg": "前提确认：投入的钱应为 5 年内不需要动用的闲钱。"})

    passed = all(i["level"] != "fail" for i in items)
    return {
        "items": items,
        "monthly_surplus": surplus,
        "monthly_invest": monthly_invest,
        "emergency_need": need_em,
        "passed": passed,
    }


def max_allowed_weekly(profile):
    """按现金流 50% + 压力测试 70% 两条线，算出建议的每周投入上限"""
    inc = float(profile["monthly_income"])
    exp = float(profile["monthly_expense"])
    drop_pct = float(profile.get("income_drop_pct", 30))

    surplus = inc - exp
    surplus_stress = inc * (1 - drop_pct / 100) - exp

    caps = []
    if surplus > 0:
        caps.append(surplus * 0.5)
    if surplus_stress > 0:
        caps.append(surplus_stress * 0.7)
    if not caps:
        return 0.0
    return min(caps) * 12 / 52
