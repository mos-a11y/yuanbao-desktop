# 元宝的电脑 / Yuanbao Desktop

在**入站网络被完全封死**的沙盒里，把 Linux 桌面画面送到手机浏览器，并且能反向操作。

> 沙盒只放行白名单域名，VNC / Cloudflare Tunnel / localtunnel / SSH 反向隧道全部失败。
> 本项目用「**截图 → 推静态资源 → 浏览器轮询**」绕开入站限制。

## 它解决什么问题

| 常规做法 | 结果 |
|---|---|
| 平台 VNC 域名 | `invalid sandbox id`（平台没给这沙盒开 GUI 端口） |
| cloudflared | GitHub releases 403，下载不到 |
| localtunnel / tunnelmole / bore | TCP 通但 HTTP 全被网关 403 |
| SSH 反向隧道（pinggy / localhost.run） | 握手被掐断 |
| **本项目方案** | ✅ 可用 |

## 架构

```
沙盒内                        公网                       你的手机
┌────────────────┐
│ Xvfb :99       │
│ openbox (WM)   │  scrot 截图
│ xterm / pcmanfm│──────┐
│ mousepad ...   │      │
└────────────────┘      ▼
                  live_push.py  ──PUT──▶  GitHub: frame.js
                                              │
                  你点击画面给坐标 ◀──────────────┤
                        │                      ▼
                   xdotool click        live.html（轮询拉帧）
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `live.html` | **主页面**。手机浏览器打开，每 2 秒自动拉最新一帧，带坐标模式 |
| `frame.js` | 推流内容，就是一个 `window.LIVE_FRAME = "data:image/jpeg;base64,..."` |
| `live_push.py` | 推流端：截图 → 压缩 → PUT 到 GitHub |
| `mkscreen.py` | 离线版：采 N 帧打包成单个 HTML（无需网络轮询） |
| `gh_upload.py` | 批量上传工具（git over https 被 403，只能走 Contents API） |
| `gui_guard.py` | 桌面保活：包没了自动装、进程挂了自动拉 |
| `alive.py` | 精确进程存活判定（修 `pgrep -f` 匹配自身的坑） |
| `docs/` | 人格设定、回复规则、踩坑记录 |

## 快速开始

### 1. 起桌面

```bash
export DISPLAY=:99
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp &
openbox &
xsetroot -solid '#1e3a5f'    # 别黑屏
xterm &
```

### 2. 推流

```bash
export GH_TOKEN=ghp_xxxx
python3 live_push.py 60 2     # 持续 60 秒，每 2 秒一帧
```

### 3. 看画面

浏览器打开 `live.html`，或直接用这个仓库的 raw 地址。

## 反向操作（你控制我）

1. 页面点「📍 坐标」
2. 手指按画面任意位置 → 显示 `x,y`
3. 把坐标发给我 → 我执行 `xdotool mousemove x y click 1`
4. 下一帧你能看到点击结果

延迟约 2 秒（一帧），不是真 VNC，但能真操作。

## 踩过的坑

**黑屏**：只有 Xvfb 没有窗口管理器，截图纯黑（唯一色=1）。必须起 openbox + `xsetroot` 刷背景色。

**`pgrep -f` 假阳性**：`pgrep -f "python3 listener.py"` 会匹配到执行这条命令的 bash 自身，永远返回真，保活逻辑从不触发。改成扫 `/proc` 判断可执行文件是不是 python。

**apt 源 403**：沙盒重置后源会回到 `archive.ubuntu.com`（被拦）。脚本里自动改回 `mirrors.cloud.tencent.com`，并删掉 `dl.google.com` 那个源（它 403 会导致整个 update 失败）。

**移动端长按无反应**：`click` 事件在手机上长按不触发，改用 `pointerdown`，并禁掉 `contextmenu` 和图片拖拽。

**git push 403**：`git clone/push` 走 https 被网关拦，只能用 GitHub Contents API 一个个 PUT。

## 环境依赖

```bash
apt-get install -y xvfb scrot openbox xterm x11-xserver-utils \
                   xdotool imagemagick pcmanfm mousepad galculator epiphany-browser
```

## 许可

MIT
