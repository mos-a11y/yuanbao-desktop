#!/usr/bin/env python3
"""元宝的电脑 · 双向桥（推画面 + 收坐标）

上行：沙盒截图 -> 仓库 frame.js      -> 用户浏览器拉（实时画面）
下行：用户点画面 -> 仓库 click.txt    -> 我轮询拉到 -> xdotool 执行

GitHub 当总线：沙盒入站被封死，但两边都能读写 GitHub。

用法:
    python3 bridge.py            # 一直跑（推帧 + 收坐标）
    python3 bridge.py 120        # 跑 120 秒
    python3 bridge.py 120 2      # 120 秒，每 2 秒一帧
"""
import base64
import json
import os
import subprocess
import sys
import time

TOKEN = os.environ.get("GH_TOKEN", "")
OWNER, REPO, BRANCH = "mos-a11y", "yuanbao-desktop", "main"
API = f"https://api.github.com/repos/{OWNER}/{REPO}/contents"
ENV = {**os.environ, "DISPLAY": ":99"}

# 桌面逻辑尺寸（截图会缩放到 1024x640 给用户看，坐标要按比例还原）
SHOW_W, SHOW_H = 1024, 640
REAL_W, REAL_H = 1280, 800

_last_click = ""


def api(method, url, data=None):
    cmd = ["curl", "-s", "--max-time", "40", "-X", method,
           "-H", f"Authorization: Bearer {TOKEN}",
           "-H", "Accept: application/vnd.github+json"]
    if data is not None:
        cmd += ["-d", json.dumps(data)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_raw": r.stdout[:150]}


def sha_of(path):
    r = subprocess.run(["curl", "-s", "--max-time", "25",
                        "-H", f"Authorization: Bearer {TOKEN}",
                        "-H", "Accept: application/vnd.github+json",
                        f"{API}/{path}?ref={BRANCH}"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout).get("sha")
    except Exception:
        return None


def put(path, content_bytes, msg):
    data = {"message": msg, "content": base64.b64encode(content_bytes).decode(),
            "branch": BRANCH}
    s = sha_of(path)
    if s:
        data["sha"] = s
    r = api("PUT", f"{API}/{path}", data)
    return "content" in r or "commit" in r, str(r.get("message", ""))[:60]


def get_text(path):
    r = subprocess.run(["curl", "-s", "--max-time", "20",
                        "-H", f"Authorization: Bearer {TOKEN}",
                        "-H", "Accept: application/vnd.github+json",
                        f"{API}/{path}?ref={BRANCH}"], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        if "content" in d:
            return base64.b64decode(d["content"]).decode("utf-8", "ignore")
    except Exception:
        pass
    return None


# ---------- 上行：推画面 ----------
def ensure_desktop():
    for b in ("Xvfb", "scrot", "openbox", "xdotool"):
        if subprocess.run(["which", b], capture_output=True).returncode != 0:
            print(f"缺 {b}，先跑 mkscreen.py 装环境")
            return False
    def up(m):
        for e in os.listdir("/proc"):
            if not e.isdigit():
                continue
            try:
                c = open(f"/proc/{e}/cmdline", "rb").read().decode("utf-8", "ignore")
            except Exception:
                continue
            if "bridge.py" in c:
                continue
            if m in c:
                return True
        return False
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


def push_frame():
    raw = "/tmp/_b.png"
    subprocess.run(["scrot", "-z", raw], capture_output=True, env=ENV)
    if not os.path.exists(raw):
        return False
    try:
        from PIL import Image
        im = Image.open(raw).convert("RGB")
        im = im.resize((SHOW_W, SHOW_H), Image.LANCZOS)
        im.save("/tmp/_b.jpg", "JPEG", quality=60, optimize=True)
        src = "/tmp/_b.jpg"
    except Exception:
        src = raw
    b64 = base64.b64encode(open(src, "rb").read()).decode()
    os.remove(raw)
    body = (f'window.LIVE_FRAME="data:image/jpeg;base64,{b64}";\n'
            f'window.LIVE_TS={int(time.time())};\n')
    global _frame_sha
    data = {"message": f"frame {time.strftime('%H:%M:%S')}",
            "content": base64.b64encode(body.encode()).decode(), "branch": BRANCH}
    if _frame_sha:
        data["sha"] = _frame_sha
    r = api("PUT", f"{API}/frame.js", data)
    if "content" in r:
        _frame_sha = r["content"].get("sha")
        return True
    if "message" in r and "does not match" in str(r["message"]):
        _frame_sha = sha_of("frame.js")   # sha 变了，刷新后下一帧自然成功
    return False


# ---------- 下行：收坐标并执行 ----------
def pull_click():
    """返回 (x, y, action) 或 None"""
    txt = get_text("click.txt")
    if not txt:
        return None
    txt = txt.strip()
    global _last_click
    if not txt or txt == _last_click:
        return None
    _last_click = txt
    # 格式: "x,y,action,ts"  例: "512,320,click,1712345678"
    parts = [p.strip() for p in txt.split(",")]
    try:
        x = int(parts[0]); y = int(parts[1])
    except Exception:
        return None
    action = parts[2] if len(parts) > 2 else "click"
    # 显示尺寸 -> 真实尺寸
    rx = int(x * REAL_W / SHOW_W)
    ry = int(y * REAL_H / SHOW_H)
    return rx, ry, action


def do_action(rx, ry, action):
    if action == "click":
        subprocess.run(["xdotool", "mousemove", str(rx), str(ry)], env=ENV)
        subprocess.run(["xdotool", "click", "1"], env=ENV)
    elif action == "rclick":
        subprocess.run(["xdotool", "mousemove", str(rx), str(ry)], env=ENV)
        subprocess.run(["xdotool", "click", "3"], env=ENV)
    elif action == "move":
        subprocess.run(["xdotool", "mousemove", str(rx), str(ry)], env=ENV)
    elif action == "key":
        # key 时 x 当作 keysym 用不了，这里支持 type
        pass
    print(f"  ⚡ 执行 {action} @ ({rx},{ry})   用户坐标({int(rx*SHOW_W/REAL_W)},{int(ry*SHOW_H/REAL_H)})")


if __name__ == "__main__":
    _frame_sha = sha_of("frame.js")
    if not TOKEN:
        print("需要 GH_TOKEN")
        sys.exit(1)
    if not ensure_desktop():
        sys.exit(1)
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    print(f"桥接启动: 推帧间隔 {gap}s" + (f"，运行 {secs}s" if secs else "，持续运行"))
    end = time.time() + secs if secs else None
    nf = nc = 0
    while True:
        try:
            if push_frame():
                nf += 1
                print(f"[{time.strftime('%H:%M:%S')}] 帧{nf}", end="")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] 帧失败", end="")
            c = pull_click()
            if c:
                do_action(*c)
                nc += 1
            print(f" | 已执行点击 {nc}")
        except Exception as e:
            print("异常:", str(e)[:70])
        if end and time.time() > end:
            break
        time.sleep(gap)
    print(f"结束: 推了 {nf} 帧, 执行 {nc} 次点击")
