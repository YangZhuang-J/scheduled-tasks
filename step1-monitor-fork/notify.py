# -*- coding: utf-8 -*-
"""PushPlus 微信推送封装"""
import requests


def push(token, title, content, template="markdown"):
    """推送到个人微信（PushPlus）。成功返回 (True, resp)，失败返回 (False, resp)"""
    try:
        r = requests.post(
            "https://www.pushplus.plus/send",
            json={"token": token, "title": title, "content": content, "template": template},
            timeout=15,
        )
        j = r.json()
        return j.get("code") == 200, j
    except Exception as e:
        return False, {"error": str(e)}
