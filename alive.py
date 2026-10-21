#!/usr/bin/env python3
"""精确判断 listener 是否真的活着。

之前用 pgrep -f "python3 listener.py" 判断，会匹配到执行这条命令的
bash 进程自身（命令行里含这串字），永远返回真 —— 导致监听早死了
我还以为活着，保活逻辑根本没触发。这是"没连上还在巡查"的根因。

正确做法：遍历 /proc，找 cmdline 恰好是 python3 + listener.py 的进程，
且可执行文件路径里含 python（排除 bash）。
"""
import os

MARK = "listener.py"


def pids() -> list[int]:
    """返回真正跑着 listener.py 的 python 进程 pid"""
    out = []
    me = os.getpid()
    for e in os.listdir("/proc"):
        if not e.isdigit():
            continue
        pid = int(e)
        if pid == me:
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                parts = f.read().split(b"\x00")
            parts = [p.decode("utf-8", "ignore") for p in parts if p]
        except Exception:
            continue
        if len(parts) < 2:
            continue
        exe, arg = parts[0], parts[1]
        # 可执行文件必须是 python，不能是 bash
        if "python" not in os.path.basename(exe).lower():
            continue
        # 参数里必须有 listener.py（用 basename 比较，避免路径差异）
        if not any(os.path.basename(a) == MARK for a in parts[1:]):
            continue
        out.append(pid)
    return out


def alive() -> bool:
    return len(pids()) > 0


if __name__ == "__main__":
    ps = pids()
    print("ALIVE" if ps else "DEAD", ps)
