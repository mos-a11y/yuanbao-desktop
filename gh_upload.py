#!/usr/bin/env python3
"""批量上传文件到 yuanbao-desktop 仓库（走 Contents API）

git over https 被沙盒网关 403，所以只能用 API 一个个 PUT。
用法:
    python3 gh_upload.py 文件1 文件2 ...
    python3 gh_upload.py --all      # 上传预设的项目文件
"""
import base64
import json
import os
import subprocess
import sys
import time

TOKEN = os.environ.get("GH_TOKEN", "")
OWNER, REPO, BRANCH = "mos-a11y", "yuanbao-desktop", "main"

# --all 时上传的清单（沙盒路径 -> 仓库内路径）
PRESET = [
    ("/data/workspace/live.html",        "live.html"),
    ("/data/workspace/mkscreen.py",      "mkscreen.py"),
    ("/data/workspace/live_push.py",     "live_push.py"),
    ("/data/workspace/gui_guard.py",     "gui_guard.py"),
    ("/data/workspace/gui_guard.sh",     "gui_guard.sh"),
    ("/data/workspace/alive.py",         "alive.py"),
    ("/data/workspace/reply.py",         "reply.py"),
    ("/data/workspace/respond.py",       "respond.py"),
    ("/data/workspace/patrol_loop.py",   "patrol_loop.py"),
    ("/data/workspace/PERSONA.md",       "docs/PERSONA.md"),
    ("/data/workspace/REPLY_RULE.md",    "docs/REPLY_RULE.md"),
    ("/data/workspace/云桌面进展.md",     "docs/云桌面进展.md"),
]


def api(method, url, data=None):
    cmd = ["curl", "-s", "--max-time", "40", "-X", method,
           "-H", f"Authorization: Bearer {TOKEN}",
           "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28"]
    if data is not None:
        cmd += ["-d", json.dumps(data)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_raw": r.stdout[:200]}


def sha_of(path):
    r = subprocess.run(["curl", "-s", "--max-time", "25",
                        "-H", f"Authorization: Bearer {TOKEN}",
                        "-H", "Accept: application/vnd.github+json",
                        f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout).get("sha")
    except Exception:
        return None


def put(local, remote):
    if not os.path.exists(local):
        print(f"  跳过(不存在) {remote}")
        return False
    raw = open(local, "rb").read()
    if len(raw) > 20 * 1024 * 1024:
        print(f"  跳过(>20MB) {remote}")
        return False
    enc = base64.b64encode(raw).decode()
    data = {"message": f"update {remote}", "content": enc, "branch": BRANCH}
    s = sha_of(remote)
    if s:
        data["sha"] = s
    r = api("PUT", f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{remote}", data)
    ok = "content" in r or "commit" in r
    print(f"  {'✓' if ok else '✗'} {remote} ({len(raw)//1024}KB)"
          + ("" if ok else " " + str(r.get("message", ""))[:60]))
    return ok


if __name__ == "__main__":
    if not TOKEN:
        print("需要 GH_TOKEN 环境变量")
        sys.exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        items = [(a, b) for a, b in PRESET if os.path.exists(a)]
    else:
        items = [(a, os.path.basename(a)) for a in sys.argv[1:]]
    if not items:
        print("没有可上传的文件")
        sys.exit(1)
    print(f"上传 {len(items)} 个文件 -> {OWNER}/{REPO}")
    ok = 0
    for a, b in items:
        if put(a, b):
            ok += 1
        time.sleep(0.6)
    print(f"完成 {ok}/{len(items)}")
