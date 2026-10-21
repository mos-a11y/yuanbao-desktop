#!/usr/bin/env python3
"""生成 index.html —— 真·双向实时桌面

上行：页面每 N 毫秒 fetch frame.js -> 更新 <img>（实时画面）
下行：手指按画面 -> PUT click.txt -> 沙盒 bridge.py 拉到 -> xdotool 执行

token 默认从环境变量注入（自己用方便）；
开源时留空，页面会弹输入框让用户填自己的 token。
"""
import base64
import os
import subprocess
import sys

ENV = {**os.environ, "DISPLAY": ":99"}
OUT = "/data/workspace/index.html"
REPO = "mos-a11y/yuanbao-desktop"
TOKEN = os.environ.get("GH_TOKEN", "")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=3,user-scalable=yes">
<title>元宝的电脑 · 实时控制</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d0d;color:#eee;font-family:system-ui,-apple-system,sans-serif;
  display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:8px;
  -webkit-touch-callout:none;-webkit-user-select:none;user-select:none}
h1{font-size:15px;margin:5px 0;color:#7cf}
#wrap{position:relative;width:100%;max-width:1024px;touch-action:manipulation}
#screen{width:100%;display:block;border:1px solid #333;border-radius:6px;background:#111;
  -webkit-user-drag:none;cursor:crosshair;touch-action:manipulation}
#bar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:center;margin:8px 0;font-size:13px}
button{background:#2a6;color:#fff;border:0;border-radius:5px;padding:9px 13px;font-size:14px}
button.sec{background:#456}
button.warn{background:#a52}
#status{color:#8a8;text-align:center;font-size:12px;line-height:1.5;min-width:210px}
#tip{font-size:12px;color:#777;text-align:center;line-height:1.8;max-width:620px;margin-top:8px}
#coord{position:absolute;pointer-events:none;font-size:12px;background:#000d;color:#0f0;
  padding:3px 7px;border-radius:3px;display:none;transform:translate(-50%,-160%);
  font-weight:700;white-space:nowrap;z-index:9}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#555;margin-right:5px}
.dot.on{background:#0f0;box-shadow:0 0 6px #0f0}
.dot.err{background:#f55}
#tk{position:fixed;inset:0;background:#000e;display:none;align-items:center;justify-content:center;z-index:99}
#tk div{background:#1a1a1a;padding:18px;border-radius:8px;max-width:92vw}
#tk input{width:100%;padding:9px;margin:8px 0;background:#000;color:#0f0;border:1px solid #444;
  border-radius:4px;font-family:monospace;font-size:12px}
#tk small{color:#888;line-height:1.6;display:block;margin-bottom:8px}
</style></head><body oncontextmenu="return false">
<h1>🖥️ 元宝的电脑 · 实时控制</h1>
<div id="wrap"><img id="screen" alt="桌面画面"><div id="coord"></div></div>
<div id="bar">
  <span id="status"><span class="dot" id="dot"></span>载入中…</span>
  <button onclick="toggleLive()" id="btnLive">⏸ 暂停</button>
  <button class="sec" onclick="setAct('click')">👆 左键</button>
  <button class="sec" onclick="setAct('rclick')">👉 右键</button>
  <button class="sec" onclick="setAct('move')">🖱 只移动</button>
  <button class="warn" onclick="askToken()">🔑 Token</button>
</div>
<div id="tip">
手指<b>按住画面</b>任意处 → 坐标自动发回沙盒 → 元宝用 xdotool 点击那里 → 下一帧看到结果<br>
当前动作：<b id="act">左键单击</b> ｜ 画面每 __MS__ms 自动刷新
</div>

<div id="tk"><div>
  <b>设置 GitHub Token</b>
  <small>用于把点击坐标写回仓库。需要 repo 权限。保存在本机 localStorage，不会上传给别人。<br>
  开源部署时请填你自己的 token。</small>
  <input id="tki" placeholder="ghp_xxxx 或 github_pat_xxxx">
  <button onclick="saveToken()">保存</button>
  <button class="sec" onclick="closeTk()">取消</button>
</div></div>

<script>
const REPO="__REPO__";
const FALLBACK="data:image/jpeg;base64,__FALLBACK__";
// raw 优先，避免 jsdelivr 缓存把画面卡在旧帧
const FRAME_SRC=[
 `https://raw.githubusercontent.com/${REPO}/main/frame.js`,
 `https://cdn.jsdelivr.net/gh/${REPO}@main/frame.js`,
 `https://raw.githack.com/${REPO}/main/frame.js`,
 `https://cdn.statically.io/gh/${REPO}/main/frame.js`
];
const API=`https://api.github.com/repos/${REPO}/contents/click.txt`;
let TOKEN=localStorage.getItem('gh_token')||"__TOKEN__";
let act="click";

const img=document.getElementById('screen');
const st=document.getElementById('status');
const dot=document.getElementById('dot');
const cd=document.getElementById('coord');
const btn=document.getElementById('btnLive');
let live=true,busy=false,lastTs=0,shown=false;

img.src=FALLBACK;

function askToken(){document.getElementById('tk').style.display='flex';
  document.getElementById('tki').value=localStorage.getItem('gh_token')||'';}
function closeTk(){document.getElementById('tk').style.display='none';}
function saveToken(){const v=document.getElementById('tki').value.trim();
  if(v){TOKEN=v;localStorage.setItem('gh_token',v);} closeTk();}
function setAct(a){act=a;
  document.getElementById('act').textContent={click:'左键单击',rclick:'右键单击',move:'只移动鼠标'}[a];}
function toggleLive(){live=!live;btn.textContent=live?'⏸ 暂停':'▶ 继续';
  if(live){clearInterval(T);T=setInterval(pull,__MS__);pull();}else clearInterval(T);}

async function fetchFrame(u){
  const ctl=new AbortController();const to=setTimeout(()=>ctl.abort(),7000);
  try{
    const r=await fetch(u+"?t="+Date.now(),{cache:"no-store",signal:ctl.signal});
    clearTimeout(to);
    if(!r.ok)return null;
    const t=await r.text();
    const m=t.match(/LIVE_FRAME\s*=\s*"([^"]+)"/);
    const ts=t.match(/LIVE_TS\s*=\s*(\d+)/);
    if(m&&m[1].length>200)return{frame:m[1],ts:ts?+ts[1]:0};
  }catch(e){clearTimeout(to);}
  return null;
}

async function pull(){
  if(busy)return;busy=true;
  for(let i=0;i<FRAME_SRC.length;i++){
    const r=await fetchFrame(FRAME_SRC[i]);
    if(r){
      if(r.ts!==lastTs){lastTs=r.ts;img.src=r.frame;shown=true;}
      dot.className="dot on";
      const d=new Date((r.ts||Date.now()/1000)*1000);
      st.innerHTML=`<span class="dot on"></span>画面 ${d.toLocaleTimeString()} · 源${i+1}`;
      busy=false;return;
    }
  }
  busy=false;
  if(!shown){img.src=FALLBACK;shown=true;}
  dot.className="dot err";
  st.innerHTML='<span class="dot err"></span>取帧失败（显示缓存画面）';
}

// ---- 点击回传 ----
function b64(s){return btoa(unescape(encodeURIComponent(s)));}
async function sendClick(x,y){
  if(!TOKEN){st.innerHTML='<span class="dot err"></span>先点🔑填Token';askToken();return;}
  const body=`${x},${y},${act},${Math.floor(Date.now()/1000)}`;
  const ctl=new AbortController();const to=setTimeout(()=>ctl.abort(),9000);
  try{
    // 先取 sha
    const g=await fetch(API+"?ref=main",{headers:{Authorization:"Bearer "+TOKEN,
      Accept:"application/vnd.github+json"},signal:ctl.signal});
    const j=await g.json();
    const data={message:"click "+body,content:b64(body),branch:"main"};
    if(j&&j.sha)data.sha=j.sha;
    const p=await fetch(API,{method:"PUT",signal:ctl.signal,
      headers:{Authorization:"Bearer "+TOKEN,Accept:"application/vnd.github+json",
               "Content-Type":"application/json"},
      body:JSON.stringify(data)});
    clearTimeout(to);
    if(p.ok){st.innerHTML=`<span class="dot on"></span>已发送 ${x},${y} (${act})`;}
    else{const e=await p.json();
      st.innerHTML='<span class="dot err"></span>发送失败 '+String(e.message||'').slice(0,30);}
  }catch(e){clearTimeout(to);
    st.innerHTML='<span class="dot err"></span>发送超时';}
}

function pos(e){
  const r=img.getBoundingClientRect();
  const sx=img.naturalWidth||1024,sy=img.naturalHeight||640;
  const x=Math.round((e.clientX-r.left)/r.width*sx);
  const y=Math.round((e.clientY-r.top)/r.height*sy);
  cd.style.display='block';
  cd.style.left=(((e.clientX-r.left)/r.width)*100)+'%';
  cd.style.top=(((e.clientY-r.top)/r.height)*100)+'%';
  cd.textContent=x+','+y;
  sendClick(x,y);
}
img.addEventListener('pointerdown',pos);
img.addEventListener('mousedown',function(e){if(!window.PointerEvent)pos(e);});
img.addEventListener('touchstart',function(e){if(e.touches&&e.touches[0])pos(e.touches[0]);},{passive:true});
// 拖拽也要能触发（按住滑动）
let dragging=false;
img.addEventListener('pointermove',function(e){if(dragging)return;dragging=true;
  setTimeout(()=>dragging=false,600);});

let T=setInterval(pull,__MS__);
pull();
</script></body></html>"""


def shot_b64():
    raw = "/tmp/_i.png"
    subprocess.run(["scrot", "-z", raw], capture_output=True, env=ENV)
    if not os.path.exists(raw):
        return None
    try:
        from PIL import Image
        im = Image.open(raw).convert("RGB")
        im = im.resize((1024, 640), Image.LANCZOS)
        im.save("/tmp/_i.jpg", "JPEG", quality=60, optimize=True)
        src = "/tmp/_i.jpg"
    except Exception:
        src = raw
    b = base64.b64encode(open(src, "rb").read()).decode()
    os.remove(raw)
    return b


if __name__ == "__main__":
    ms = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    b64 = shot_b64()
    if not b64:
        print("截图失败"); sys.exit(1)
    html = (TEMPLATE
            .replace("__FALLBACK__", b64)
            .replace("__REPO__", REPO)
            .replace("__TOKEN__", TOKEN)
            .replace("__MS__", str(ms)))
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"✓ index.html {os.path.getsize(OUT)//1024}KB  刷新间隔{ms}ms  "
          f"token={'已注入' if TOKEN else '未注入(需手填)'}")
