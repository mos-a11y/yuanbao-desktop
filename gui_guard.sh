#!/bin/bash
# ============================================================
# 桌面保活 —— 保证「我能操作电脑」这一路永远不塌
#
# 作用：每 8 秒检查 Xvfb / x11vnc / websockify，
#       谁挂了拉谁，全挂了整套重建。
# 目的：哪怕沙盒重置、进程被杀，回来时画面还在。
#
# 用法（自己无限循环，不依赖我发起）:
#   setsid nohup bash /data/workspace/gui_guard.sh >/dev/null 2>&1 &
# ============================================================
LOG=/tmp/gui_guard.log
DISP=:99
VNC_PORT=5900
NOVNC_PORT=6080
NOVNC_WEB=/usr/share/novnc

log() { echo "[$(date +%H:%M:%S)] $1" >> "$LOG"; }

# 精确判定：必须是 python 之外的真实进程（避免 pgrep 匹配到自身）
is_up() {
    local pat="$1"
    for p in /proc/[0-9]*; do
        [ -r "$p/cmdline" ] || continue
        local c
        c=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)
        case "$c" in
            *bash*gui_guard*) continue ;;   # 跳过本脚本的 shell
        esac
        case "$c" in
            *"$pat"*) return 0 ;;
        esac
    done
    return 1
}

ensure_xvfb() {
    if ! is_up "Xvfb"; then
        log "Xvfb 掉了 -> 拉起"
        setsid nohup Xvfb $DISP -screen 0 1280x800x24 -nolisten tcp \
            >>/tmp/xvfb.log 2>&1 </dev/null &
        sleep 3
        is_up "Xvfb" && log "  Xvfb OK" || log "  Xvfb 失败"
    fi
}

ensure_vnc() {
    if ! is_up "x11vnc"; then
        log "x11vnc 掉了 -> 拉起"
        DISPLAY=$DISP setsid nohup x11vnc -display $DISP -forever \
            -shared -nopw -rfbport $VNC_PORT \
            >>/tmp/x11vnc.log 2>&1 </dev/null &
        sleep 3
        is_up "x11vnc" && log "  x11vnc OK" || log "  x11vnc 失败"
    fi
}

ensure_novnc() {
    if ! is_up "websockify"; then
        log "websockify 掉了 -> 拉起"
        setsid nohup websockify --web="$NOVNC_WEB" $NOVNC_PORT \
            localhost:$VNC_PORT >>/tmp/novnc.log 2>&1 </dev/null &
        sleep 3
        is_up "websockify" && log "  websockify OK" || log "  websockify 失败"
    fi
}

# 缺包自动装（沙盒重置后 apt 包会没）
ensure_pkgs() {
    if ! command -v Xvfb >/dev/null 2>&1 || ! command -v x11vnc >/dev/null 2>&1 \
       || ! command -v websockify >/dev/null 2>&1; then
        log "缺包 -> 自动安装"
        export DEBIAN_FRONTEND=noninteractive
        rm -f /etc/apt/sources.list.d/google-chrome.list 2>/dev/null
        sed -i '/dl.google.com/d' /etc/apt/sources.list 2>/dev/null
        apt-get update -qq >>"$LOG" 2>&1
        apt-get install -y -qq xvfb x11vnc novnc websockify >>"$LOG" 2>&1
        log "  安装完成: Xvfb=$(command -v Xvfb) x11vnc=$(command -v x11vnc)"
    fi
}

log "=== gui_guard 启动 ==="
ensure_pkgs
while true; do
    ensure_xvfb
    ensure_vnc
    ensure_novnc
    sleep 8
done
