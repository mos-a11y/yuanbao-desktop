#!/usr/bin/env python3
"""统一回复入口 —— 私聊回私聊，群回群

之前所有回复都硬编码发到群里，导致私聊消息也发到群里。
这个模块强制按消息来源决定目标，不会再错。
"""
import json
import random
import sys
import time

sys.path.insert(0, "/data/workspace")
import send  # noqa: E402

INBOX = "/data/workspace/inbox.jsonl"
REPLIED = "/data/workspace/replied.txt"
_PRIVATE_FALLBACK = "02E9A5ECBFD3B3561E06352ED20A52AC"  # 管理员私聊openid兜底


def load_replied() -> set:
    try:
        return set(l.strip() for l in open(REPLIED, encoding="utf-8") if l.strip())
    except FileNotFoundError:
        return set()


def mark(mid: str):
    with open(REPLIED, "a", encoding="utf-8") as f:
        f.write(mid + "\n")


def target_of(d: dict) -> tuple[str, bool]:
    """根据消息决定 (目标ID, 是否群)
    群消息 -> (group_openid, True)
    私聊   -> (openid, False)
    """
    g = d.get("group_openid") or ""
    if g:
        return g, True
    oid = d.get("openid") or _PRIVATE_FALLBACK
    return oid, False


def reply(d: dict, content: str, quote: bool = False) -> str:
    """回复一条消息，自动判断发群还是发私聊"""
    tgt, is_group = target_of(d)
    mid = d.get("msg_id")
    r = send.send(
        tgt, content, mid, is_group,
        msg_seq=random.randint(1, 90000),
        quote=(mid if quote else None),
    )
    return r


def pending() -> list[dict]:
    seen = load_replied()
    out = []
    for l in open(INBOX, encoding="utf-8"):
        d = json.loads(l)
        m = d.get("msg_id") or ""
        if not m or m in seen:
            continue
        out.append(d)
    return out


def reply_to_text(keyword: str, content: str, quote: bool = True) -> bool:
    """找到包含关键词的未读消息并回复（按来源发）"""
    for d in pending():
        if keyword in (d.get("text") or ""):
            tgt, is_group = target_of(d)
            where = "群" if is_group else "私聊"
            r = reply(d, content, quote=quote)
            ok = r.startswith("HTTP 200")
            print(f"{'OK ' if ok else 'FAIL'} [{where}] {content[:24]} {r[:24]}")
            return ok
    return False


if __name__ == "__main__":
    # 用法: python3 reply.py "关键词" "回复内容"
    if len(sys.argv) >= 3:
        reply_to_text(sys.argv[1], sys.argv[2])
    else:
        ps = pending()
        print(f"未读 {len(ps)} 条:")
        for d in ps:
            tgt, isg = target_of(d)
            print(f"  [{'群' if isg else '私聊'}] {(d.get('text') or '')[:40]!r}")
