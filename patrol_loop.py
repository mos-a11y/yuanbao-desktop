#!/usr/bin/env python3
"""巡查主循环：保活(精确判定) + 自动响应 + 留给我"""
import sys, os, time, subprocess
sys.path.insert(0, "/data/workspace")
import alive, respond, reply

def ensure():
    if not alive.alive():
        subprocess.run(
            "cd /data/workspace && PYTHONPATH=/data/workspace/pkg "
            "setsid nohup python3 /data/workspace/listener.py >>/tmp/listener_pl.log 2>&1 </dev/null &",
            shell=True)
        print(f"[{time.strftime('%H:%M:%S')}] 拉起 listener")
        time.sleep(15)
        print("  ->", "成功" if alive.alive() else "失败")

if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    end = time.time() + secs
    ensure()
    n = 0
    while time.time() < end:
        if not alive.alive():
            ensure()
        respond.run_once()
        n += 1
        time.sleep(1)
    print(f"[{time.strftime('%H:%M:%S')}] 巡查 {n} 轮完成, alive={alive.alive()}")
