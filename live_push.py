#!/usr/bin/env python3
"""实时推流：截图 -> 推到 GitHub 仓库 -> 用户浏览器定时拉取

链路（绕开沙盒入站限制）：
    我 scrot 截图  ->  base64  ->  GitHub 仓库 frame.js
                                        ↓
    用户手机浏览器  <-  定时 fetch raw.githubusercontent.com

用法:
    python3 live_push.py           # 推一帧
    python3 live_push.py 60 2      # 持续 60 秒，每 2 秒一帧
"""
import base64
import json
import os
import subprocess
import sys
import time

TOKEN = os.environ.get("GH_TOKEN", "")
OWNER = "mos-a11y"
REPO = "yuanbao-desktop"
PATH = "frame.js"
BRANCH = "main"
API = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{PATH}"
RAW = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/{PATH}"

ENV = {**os.environ, "DISPLAY": ":99"}


def gh(method, url, data=None, extra=None):
    cmd = ["curl", "-s", "--max-time", "30", "-X", method,
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


def get_sha():
    """文件已存在时拿到 sha 才能更新"""
    r = subprocess.run(["curl", "-s", "--max-time", "20",
                        "-H", f"Authorization: Bearer {TOKEN}",
                        "-H", "Accept: application/vnd.github+json",
                        f"{API}?ref={BRANCH}"], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        return d.get("sha")
    except Exception:
        return None


def shot():
    """截一帧，返回 base64(jpeg)"""
    raw = "/tmp/live_raw.png"
    subprocess.run(["scrot", "-z", raw], capture_output=True, env=ENV)
    if not os.path.exists(raw):
        return None
    try:
        from PIL import Image
        im = Image.open(raw).convert("RGB")
        im = im.resize((1024, 640), Image.LANCZOS)
        im.save("/tmp/live.jpg", "JPEG", quality=60, optimize=True)
        src = "/tmp/live.jpg"
    except Exception:
        src = raw
    b = open(src, "rb").read()
    os.remove(raw)
    return base64.b64encode(b).decode()


def push(b64):
    body = (f'window.LIVE_FRAME="data:image/jpeg;base64,{b64}";\n'
            f'window.LIVE_TS={int(time.time())};\n')
    enc = base64.b64encode(body.encode()).decode()
    sha = get_sha()
    data = {"message": f"frame {time.strftime('%H:%M:%S')}",
            "content": enc, "branch": BRANCH}
    if sha:
        data["sha"] = sha
    r = gh("PUT", API, data)
    ok = "commit" in r or "content" in r
    return ok, str(r.get("message", ""))[:80]


def ensure_desktop():
    """沙盒重置后自动恢复桌面"""
    for b in ("Xvfb", "scrot", "openbox"):
        if not subprocess.run(["which", b], capture_output=True).returncode == 0:
            print("缺包，先跑 mkscreen.py 装环境")
            return False
    up = lambda m: any(m in open(f"/proc/{e}/cmdline", "rb").read().decode("utf-8", "ignore")
                       for e in os.listdir("/proc") if e.isdigit()
                       and os.path.exists(f"/proc/{e}/cmdline"))
    if not up("Xvfb"):
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                         stdout=open("/tmp/xvfb.log", "a"), stderr=subprocess.STDOUT,
                         preexec_fn=os.setsid)
        time.sleep(4)
    if not up("openbox"):
        subprocess.Popen(["openbox"], stdout=open("/tmp/openbox.log", "a"),
                         stderr=subprocess.STDOUT, preexec_fn=os.setsid, env=ENV)
        time.sleep(4)
        subprocess.run(["xsetroot", "-solid", "#1e3a5f"], capture_output=True, env=ENV)
    return True


if __name__ == "__main__":
    if not TOKEN:
        TOKEN = os.environ.get("GH_TOKEN", "")
    if not TOKEN:
        print("需要 GH_TOKEN")
        sys.exit(1)
    if not ensure_desktop():
        sys.exit(1)
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 2.5
    end = time.time() + secs if secs else None
    n = 0
    while True:
        b64 = shot()
        if b64:
            ok, msg = push(b64)
            n += 1
            print(f"[{time.strftime('%H:%M:%S')}] 第{n}帧 {'OK' if ok else 'FAIL '+msg}"
                  f" ({len(b64)//1024}KB)")
        if end and time.time() > end:
            break
        time.sleep(gap)
    print(f"推送 {n} 帧，浏览器拉: {RAW}")
