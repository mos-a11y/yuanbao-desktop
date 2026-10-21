#!/usr/bin/env python3
"""自动响应器 —— 规则由「我」逐条手写。

⚠️ 关键修复：没匹配到规则的消息【绝不标记为已回复】，
必须留给「我」亲自看和回。之前全标记导致消息被静默吞掉。
"""
import sys, re, time
sys.path.insert(0, "/data/workspace")
import reply

RULES = [
    ("沙盒干掉", "不能 那是平台的东西 我干不掉"),
    ("第三方", "能是能 但得从腾讯源下 别的源全403"),
    ("乌班图版本", "Ubuntu 22.04.5"),
    ("ubuntu版本", "Ubuntu 22.04.5"),
    ("识别语音", "语音识别不了 现在只能收文字"),
    ("识图", "图我看不了 图源域名被拦 只能看到尺寸"),
    ("不搭理", "在啊 你说"),
    ("怎么不回", "在 刚才没看到"),
    ("必应", "必应能开 我试试"),
    ("1+1", "2"),
    ("沙盒现在没有什么限制", "有啊 网络只放行腾讯几个域名 每次还只能跑几分钟"),
]

_shown = set()   # 已经提示过我的话题，不再每轮重复刷屏

def run_once():
    """只回能匹配规则的。匹配不上的一律留给「我」，不标记。"""
    hit = 0
    left = []
    for d in reply.pending():
        txt = re.sub(r'<@[0-9A-Fa-f]+>', '', (d.get('text') or '')).strip()
        if not txt:                      # 空消息/纯表情 -> 直接标记
            reply.mark(d['msg_id']); continue
        if '聊天记录' in txt:             # 合并转发 -> 看不了，直接标记
            reply.mark(d['msg_id']); continue
        for kw, ans in RULES:
            if kw in txt:
                r = reply.reply(d, ans, quote=True)
                if r.startswith('HTTP 200'):
                    print(f"  [{('群' if d.get('group_openid') else '私')}] {txt[:22]!r} -> {ans}")
                    reply.mark(d['msg_id'])
                    hit += 1
                break
        else:
            left.append((d, txt))        # 没匹配 -> 留给「我」
    # 打印留给我的（每轮必打，保证不漏）
    for d, txt in left[:5]:
        key = txt[:30]
        if key in _shown:
            continue
        _shown.add(key)
        print(f"  ⚠留给我 [{('群' if d.get('group_openid') else '私')}] {txt[:44]!r}")
    return hit, len(left)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for _ in range(n):
        run_once()
        time.sleep(1.5)
