#!/usr/bin/env python3
"""生成 live.html —— 内嵌兜底帧 + 轮询拉最新帧

吸取的教训：
1. 之前纯依赖外部 frame.js，CDN 一 502 就「连图片都没有」→ 必须内嵌一帧兜底
2. 坐标模式要用户先点按钮，长按没反应 → 默认开启，直接按就有
3. script 标签加载失败无提示 → 改 fetch，状态码可见

用法:
    python3 make_live.py            # 截当前画面内嵌 + 生成
"""
import base64
import os
import subprocess
import sys
import time

ENV = {**os.environ, "DISPLAY": ":99"}
OUT = "/data/workspace/live.html"
REPO = "mos-a11y/yuanbao-desktop"

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=3,user-scalable=yes">
<title>元宝的电脑 · 实时</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d0d;color:#eee;font-family:system-ui,-apple-system,sans-serif;
     display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:8px;
     -webkit-touch-callout:none;-webkit-user-select:none;user-select:none}
h1{font-size:15px;margin:5px 0;color:#7cf}
#wrap{position:relative;width:100%;max-width:1024px}
#screen{width:100%;display:block;border:1px solid #333;border-radius:6px;background:#111;
  -webkit-user-drag:none;touch-action:manipulation;cursor:crosshair}
#bar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;justify-content:center;
     margin:8px 0;font-size:13px}
button{background:#2a6;color:#fff;border:0;border-radius:5px;padding:9px 14px;font-size:14px}
button.sec{background:#456}
#status{color:#8a8;min-width:200px;text-align:center;font-size:12px;line-height:1.5}
#tip{font-size:12px;color:#777;text-align:center;line-height:1.7;max-width:620px;margin-top:8px}
#coord{position:absolute;pointer-events:none;font-size:12px;background:#000d;color:#0f0;
       padding:3px 7px;border-radius:3px;display:none;transform:translate(-50%,-150%);
       font-weight:700;white-space:nowrap;z-index:9}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#555;margin-right:5px}
.dot.on{background:#0f0;box-shadow:0 0 6px #0f0}
.dot.err{background:#f55}
</style></head><body oncontextmenu="return false">
<h1>🖥️ 元宝的电脑 · 实时</h1>
<div id="wrap"><img id="screen" alt="桌面画面"><div id="coord"></div></div>
<div id="bar">
  <span id="status"><span class="dot" id="dot"></span>载入中…</span>
  <button onclick="toggleLive()" id="btnLive">⏸ 暂停</button>
  <button class="sec" onclick="pull()">🔄 刷新</button>
</div>
<div id="tip">
坐标模式<b>已默认开启</b>：手指按住画面任意处 → 显示 x,y → 把坐标发给元宝，它就能点那里<br>
每 2 秒自动拉最新画面，右下角显示更新时间
</div>
<script>
// 兜底帧：外部拉取失败时至少能看到画面
const FALLBACK="data:image/jpeg;base64,__FALLBACK__";
const SRC=[
 "https://cdn.jsdelivr.net/gh/__REPO__@main/frame.js",
 "https://raw.githubusercontent.com/__REPO__/main/frame.js",
 "https://ghfast.top/https://raw.githubusercontent.com/__REPO__/main/frame.js",
 "https://cdn.jsdelivr.net/gh/__REPO__@main/frame.js?v=2"
];
const img=document.getElementById('screen');
const st=document.getElementById('status');
const dot=document.getElementById('dot');
const cd=document.getElementById('coord');
const btn=document.getElementById('btnLive');
let live=true,busy=false,lastTs=0,shown=false;

img.src=FALLBACK;   // 立刻显示兜底帧，绝不空白

async function fetchOne(u){
  const ctl=new AbortController();
  const to=setTimeout(()=>ctl.abort(),7000);
  try{
    const r=await fetch(u+"?t="+Date.now(),{cache:"no-store",signal:ctl.signal});
    clearTimeout(to);
    if(!r.ok) return null;
    const t=await r.text();
    const m=t.match(/LIVE_FRAME\\s*=\\s*"([^"]+)"/);
    const ts=t.match(/LIVE_TS\\s*=\\s*(\\d+)/);
    if(m&&m[1].length>200) return {frame:m[1],ts:ts?+ts[1]:0};
  }catch(e){ clearTimeout(to); }
  return null;
}

async function pull(){
  if(busy) return; busy=true;
  for(let i=0;i<SRC.length;i++){
    const r=await fetchOne(SRC[i]);
    if(r){
      if(r.ts!==lastTs){ lastTs=r.ts; img.src=r.frame; shown=true; }
      dot.className="dot on";
      const d=new Date((r.ts||Date.now()/1000)*1000);
      st.innerHTML='<span class="dot on"></span>更新 '+d.toLocaleTimeString()+' · 源'+(i+1);
      busy=false; return;
    }
  }
  busy=false;
  if(!shown){ img.src=FALLBACK; shown=true; }
  dot.className="dot err";
  st.innerHTML='<span class="dot err"></span>取帧失败(显示的是缓存画面)';
}

function toggleLive(){
  live=!live;
  btn.textContent= live?'⏸ 暂停':'▶ 继续';
  if(live){ clearInterval(T); T=setInterval(pull,2000); pull(); }
  else clearInterval(T);
}

function pos(e){
  const r=img.getBoundingClientRect();
  const sx=img.naturalWidth||1024, sy=img.naturalHeight||640;
  const x=Math.round((e.clientX-r.left)/r.width*sx);
  const y=Math.round((e.clientY-r.top)/r.height*sy);
  cd.style.display='block';
  cd.style.left=(((e.clientX-r.left)/r.width)*100)+'%';
  cd.style.top=(((e.clientY-r.top)/r.height)*100)+'%';
  cd.textContent=x+','+y;
  st.textContent='坐标 '+x+','+y+' → 发给元宝';
}
// pointerdown：手指一按就触发（长按也行）
img.addEventListener('pointerdown',pos);
// 兜底：老浏览器没有 pointer 事件
img.addEventListener('mousedown',function(e){ if(!window.PointerEvent) pos(e); });
img.addEventListener('touchstart',function(e){
  if(e.touches&&e.touches[0]) pos(e.touches[0]);
},{passive:true});

let T=setInterval(pull,2000);
pull();
</script></body></html>"""


def shot_b64():
    raw = "/tmp/_live.png"
    subprocess.run(["scrot", "-z", raw], capture_output=True, env=ENV)
    if not os.path.exists(raw):
        return None
    try:
        from PIL import Image
        im = Image.open(raw).convert("RGB")
        im = im.resize((1024, 640), Image.LANCZOS)
        im.save("/tmp/_live.jpg", "JPEG", quality=60, optimize=True)
        src = "/tmp/_live.jpg"
    except Exception:
        src = raw
    b = base64.b64encode(open(src, "rb").read()).decode()
    os.remove(raw)
    return b


if __name__ == "__main__":
    b64 = shot_b64()
    if not b64:
        print("截图失败"); sys.exit(1)
    html = TEMPLATE.replace("__FALLBACK__", b64).replace("__REPO__", REPO)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"✓ live.html {os.path.getsize(OUT)//1024}KB (内嵌兜底帧 {len(b64)//1024}KB)")
