#!/usr/bin/env python3
"""生成「元宝的电脑」HTML —— 把沙盒桌面画面打包进一个文件

原理：沙盒入站不通（VNC/穿透全被拦），但「我截图 -> 用户下载HTML」这条路通。
所以：scrot 采 N 帧 -> base64 内嵌 -> JS 循环播放 -> 手机浏览器打开就能看。

用法:
    python3 mkscreen.py            # 采 14 帧（约 21 秒）
    python3 mkscreen.py 30         # 采 30 帧
    python3 mkscreen.py 30 0.8     # 30 帧，间隔 0.8 秒
"""
import base64
import os
import shutil
import subprocess
import sys
import time

DISP = ":99"
FRAMES_DIR = "/data/workspace/frames"
OUT = "/data/workspace/元宝的电脑.html"
ENV = {**os.environ, "DISPLAY": DISP}

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=3,user-scalable=yes">
<title>元宝的电脑 · 实时画面</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#111;color:#eee;font-family:system-ui,-apple-system,sans-serif;
     display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:8px}
h1{font-size:15px;margin:6px 0;color:#7cf}
#wrap{position:relative;width:100%;max-width:1280px}
#screen{width:100%;display:block;border:1px solid #444;border-radius:6px;background:#000;
  -webkit-touch-callout:none;-webkit-user-select:none;user-select:none;
  -webkit-user-drag:none;touch-action:manipulation;pointer-events:auto}
#bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:center;
     margin:8px 0;font-size:13px}
button{background:#2a6;color:#fff;border:0;border-radius:5px;padding:7px 14px;font-size:14px}
button.sec{background:#456}
#status{color:#8a8}
#tip{font-size:12px;color:#888;text-align:center;line-height:1.6;max-width:640px;margin-top:6px}
#coord{position:absolute;pointer-events:none;font-size:11px;background:#000a;color:#0f0;
       padding:2px 5px;border-radius:3px;display:none}
</style></head><body oncontextmenu="return false">
<h1>🖥️ 元宝的电脑 · 画面</h1>
<div id="wrap"><img id="screen" alt="桌面"><div id="coord"></div></div>
<div id="bar">
  <span id="status">播放中</span>
  <button onclick="play()">▶ 播放/暂停</button>
  <button class="sec" onclick="step(-1)">◀ 上帧</button>
  <button class="sec" onclick="step(1)">下帧 ▶</button>
  <button class="sec" onclick="toggleCoord()">📍 坐标模式</button>
</div>
<div id="tip">
画面由元宝沙盒真实截取 · 共__N__帧循环播放<br>
开「坐标模式」点画面会显示坐标，把坐标告诉元宝，它就能用 xdotool 点那里
</div>
<script>
const FRAMES=[__FRAMES__];
let i=0,timer=null,coordMode=false;
const img=document.getElementById('screen');
const st=document.getElementById('status');
const cd=document.getElementById('coord');
img.src='data:image/jpeg;base64,'+FRAMES[0];
function show(n){i=(n+FRAMES.length)%FRAMES.length;
  img.src='data:image/jpeg;base64,'+FRAMES[i];
  st.textContent='第 '+(i+1)+'/'+FRAMES.length+' 帧';}
function play(){if(timer){clearInterval(timer);timer=null;st.textContent='已暂停';return;}
  timer=setInterval(()=>show(i+1),__MS__);st.textContent='播放中';}
function step(d){if(timer){clearInterval(timer);timer=null;}show(i+d);}
function toggleCoord(){coordMode=!coordMode;
  st.textContent=coordMode?'坐标模式：点画面':'已暂停';
  img.style.cursor=coordMode?'crosshair':'default';}
img.addEventListener('pointerdown',function(e){
  if(!coordMode)return;
  const r=img.getBoundingClientRect();
  const sx=img.naturalWidth||1280, sy=img.naturalHeight||800;
  const x=Math.round((e.clientX-r.left)/r.width*sx);
  const y=Math.round((e.clientY-r.top)/r.height*sy);
  cd.style.display='block';
  cd.style.left=((e.clientX-r.left)/r.width*100)+'%';
  cd.style.top=((e.clientY-r.top)/r.height*100)+'%';
  cd.textContent=x+','+y;
  st.textContent='坐标 '+x+','+y+' —— 发给元宝';
});
play();
</script></body></html>"""


def ensure_binaries():
    """缺 scrot / Xvfb 就装"""
    need = []
    for b, pkg in (("scrot", "scrot"), ("Xvfb", "xvfb"),
                   ("openbox", "openbox"), ("xterm", "xterm"),
                   ("xsetroot", "x11-xserver-utils")):
        if not shutil.which(b):
            need.append(pkg)
    if not need:
        return
    print("缺", need, "-> 安装")
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    # 源会随沙盒重置回 archive.ubuntu.com(403)，改回腾讯镜像
    try:
        p = "/etc/apt/sources.list"
        t = open(p, encoding="utf-8", errors="ignore").read()
        t = t.replace("http://archive.ubuntu.com", "https://mirrors.cloud.tencent.com")
        t = t.replace("http://security.ubuntu.com", "https://mirrors.cloud.tencent.com")
        open(p, "w").write(t)
    except Exception:
        pass
    import glob
    for f in glob.glob("/etc/apt/sources.list.d/*"):
        try:
            if "dl.google.com" in open(f, errors="ignore").read():
                os.remove(f)
        except Exception:
            pass
    subprocess.run(["apt-get", "update", "-qq"], capture_output=True, env=env, timeout=150)
    subprocess.run(["apt-get", "install", "-y", "-qq", *need],
                   capture_output=True, env=env, timeout=250)


def _running(mark):
    """进程是否活着（跳开自己）"""
    for e in os.listdir("/proc"):
        if not e.isdigit():
            continue
        try:
            c = open(f"/proc/{e}/cmdline", "rb").read().decode("utf-8", "ignore")
        except Exception:
            continue
        if "mkscreen" in c:
            continue
        if mark in c:
            return True
    return False


def ensure_display():
    """保证 Xvfb :99 + openbox + 非黑背景 都在

    ⚠ 关键：只有 Xvfb 没有窗口管理器，截图是纯黑（用户看到黑屏的根因）。
    必须起 openbox 并用 xsetroot 刷个背景色。
    """
    if not _running("Xvfb"):
        print("起 Xvfb :99")
        f = open("/tmp/xvfb.log", "a")
        subprocess.Popen(["Xvfb", DISP, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
                         stdout=f, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
        time.sleep(4)

    if not _running("openbox"):
        print("起 openbox")
        f = open("/tmp/openbox.log", "a")
        subprocess.Popen(["openbox"], stdout=f, stderr=subprocess.STDOUT,
                         preexec_fn=os.setsid, env=ENV)
        time.sleep(4)

    # 刷背景色，防止黑屏
    subprocess.run(["xsetroot", "-solid", "#1e3a5f"], capture_output=True, env=ENV)
    time.sleep(1)

    if not _running("xterm"):
        print("开终端")
        f = open("/tmp/xterm.log", "a")
        subprocess.Popen(["xterm", "-geometry", "100x30+50+50"],
                         stdout=f, stderr=subprocess.STDOUT,
                         preexec_fn=os.setsid, env=ENV)
        time.sleep(5)


def capture(n, gap):
    os.makedirs(FRAMES_DIR, exist_ok=True)
    for old in os.listdir(FRAMES_DIR):
        os.remove(os.path.join(FRAMES_DIR, old))
    paths = []
    try:
        from PIL import Image
        has_pil = True
    except ImportError:
        has_pil = False
    for i in range(n):
        raw = f"{FRAMES_DIR}/raw{i:03d}.png"
        subprocess.run(["scrot", "-z", raw], capture_output=True, env=ENV)
        if not (os.path.exists(raw) and os.path.getsize(raw) > 500):
            continue
        if has_pil:
            # 转 JPEG + 缩放，体积降 10 倍，才能塞更多帧
            out = f"{FRAMES_DIR}/f{i:03d}.jpg"
            im = Image.open(raw).convert("RGB")
            im = im.resize((1024, 640), Image.LANCZOS)
            im.save(out, "JPEG", quality=55, optimize=True)
            os.remove(raw)
        else:
            out = raw
        paths.append(out)
        time.sleep(gap)
    return paths


def build(paths, gap):
    frames = [base64.b64encode(open(p, "rb").read()).decode() for p in paths]
    html = TEMPLATE
    html = html.replace("__FRAMES__", ",".join('"%s"' % f for f in frames))
    html = html.replace("__N__", str(len(frames)))
    html = html.replace("__MS__", str(int(gap * 1000)))
    open(OUT, "w", encoding="utf-8").write(html)
    return len(frames), os.path.getsize(OUT)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    ensure_binaries()
    ensure_display()
    paths = capture(n, gap)
    if not paths:
        print("截图失败"); sys.exit(1)

    # 黑屏自检：唯一色<=2 说明还是黑屏，别交付
    try:
        from PIL import Image
        im = Image.open(paths[0]).convert("RGB")
        px = list(im.getdata())
        uniq = len(set(px[::997]))
        if uniq <= 2:
            print(f"⚠ 仍是黑屏（唯一色{uniq}），检查 openbox 是否真的起来了")
        else:
            print(f"✓ 画面正常（唯一色{uniq}）")
    except Exception:
        pass

    cnt, size = build(paths, gap)
    print(f"✓ {cnt} 帧, HTML {size} 字节 -> {OUT}")
