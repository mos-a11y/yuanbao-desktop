#!/usr/bin/env python3
"""桌面保活（python版）—— 比 bash 版可靠

之前 bash 版用 `setsid nohup ... &` 起进程，在这沙盒里起不来（日志全是"失败"）。
改成 python 直接 Popen + os.setsid，实测能起。

保活链路: Xvfb :99  ->  x11vnc 5900  ->  websockify 6080
谁挂了拉谁，包没了自动装。
"""
import os
import subprocess
import time

LOG = "/tmp/gui_guard.log"
DISP = ":99"
VNC_PORT = 5900
NOVNC_PORT = 6080
NOVNC_WEB = "/usr/share/novnc"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


def alive(mark: str) -> bool:
    """精确判定进程是否活着（跳过本脚本自己）"""
    me = os.getpid()
    for e in os.listdir("/proc"):
        if not e.isdigit():
            continue
        pid = int(e)
        if pid == me:
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().split(b"\x00")
            cmd = [c.decode("utf-8", "ignore") for c in cmd if c]
        except Exception:
            continue
        if not cmd:
            continue
        # 跳过 bash 包装（避免误判）
        if "gui_guard" in " ".join(cmd):
            continue
        # websockify 是 python 脚本：cmd[0]=python3, cmd[1]=/usr/bin/websockify
        # 所以必须检查全部参数，不能只看 cmd[0]
        exe = os.path.basename(cmd[0])
        if "python" in exe:
            # python 脚本：看第一个脚本参数
            if len(cmd) > 1 and mark in os.path.basename(cmd[1]):
                return True
        elif exe.startswith(mark):
            return True
    return False


def start(argv, logfile, env=None):
    try:
        f = open(logfile, "a")
        subprocess.Popen(argv, stdout=f, stderr=subprocess.STDOUT,
                         preexec_fn=os.setsid, env=env or os.environ)
    except Exception as e:
        log(f"  启动失败 {argv[0]}: {str(e)[:60]}")


def ensure_pkgs():
    need = []
    for b in ("Xvfb", "x11vnc", "websockify"):
        if not subprocess.run(["which", b], capture_output=True).returncode == 0:
            need.append(b)
    if not need:
        return
    log(f"缺包 {need} -> 安装")
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    subprocess.run(["bash", "-c",
                    "rm -f /etc/apt/sources.list.d/google-chrome.list; "
                    "sed -i '/dl.google.com/d' /etc/apt/sources.list"],
                   capture_output=True)
    subprocess.run(["apt-get", "update", "-qq"], capture_output=True, env=env)
    subprocess.run(["apt-get", "install", "-y", "-qq", "xvfb", "x11vnc",
                    "novnc", "websockify"], capture_output=True, env=env)
    log("  安装完成")


def ensure_all():
    if not alive("Xvfb"):
        log("Xvfb 掉了 -> 拉起")
        start(["Xvfb", DISP, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
              "/tmp/xvfb.log")
        time.sleep(3)
    if not alive("x11vnc"):
        log("x11vnc 掉了 -> 拉起")
        start(["x11vnc", "-display", DISP, "-forever", "-shared", "-nopw",
               "-rfbport", str(VNC_PORT)], "/tmp/x11vnc.log",
              env={**os.environ, "DISPLAY": DISP})
        time.sleep(3)
    if not alive("websockify"):
        log("websockify 掉了 -> 拉起")
        start(["websockify", f"--web={NOVNC_WEB}", str(NOVNC_PORT),
               f"localhost:{VNC_PORT}"], "/tmp/novnc.log")
        time.sleep(3)


if __name__ == "__main__":
    log("=== gui_guard.py 启动 ===")
    ensure_pkgs()
    secs = int(os.sys.argv[1]) if len(os.sys.argv) > 1 else None
    end = time.time() + secs if secs else None
    ensure_all()
    while True:
        if end and time.time() > end:
            break
        ensure_all()
        time.sleep(8)
    log("保活循环结束")
