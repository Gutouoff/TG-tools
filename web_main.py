"""TG工具箱 Web 前端入口 (pywebview 壳)。

启动 FastAPI 后端(后台线程),开 WebView2 窗口加载前端。
普通桌面程序形态: 无地址栏、非浏览器。窗口尺寸记忆到 settings.json。

窗口模式失败时(pywebview/pythonnet/.NET 环境问题)自动降级为
浏览器模式: 服务照常运行,用系统默认浏览器打开界面。
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

try:
    import webview          # noqa: E402
    _HAS_WEBVIEW = True
except Exception as _e:
    webview = None
    _HAS_WEBVIEW = False
    _WEBVIEW_ERR = _e

import tg_tool          # noqa: E402
import server           # noqa: E402

SETTINGS = os.path.join(tg_tool.SCRIPT_DIR, 'settings.json')


def _load_geometry():
    try:
        if os.path.isfile(SETTINGS):
            s = json.load(open(SETTINGS, encoding='utf-8'))
            g = s.get('geometry', '')
            if 'x' in g:
                w, h = g.split('x', 1)
                return int(w), int(h)
    except Exception:
        pass
    return 1100, 680


def _save_geometry(w, h):
    try:
        s = {}
        if os.path.isfile(SETTINGS):
            try:
                s = json.load(open(SETTINGS, encoding='utf-8'))
            except Exception:
                s = {}
        s['geometry'] = f'{w}x{h}'
        json.dump(s, open(SETTINGS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass


def _browser_mode(url, err):
    """窗口模式起不来: 弹提示+开系统浏览器,服务保持运行。"""
    import threading
    import time
    import webbrowser
    try:
        import ctypes
        msg = (f'窗口模式启动失败（{type(err).__name__}），已切换为浏览器模式。\n\n'
               f'界面将在默认浏览器中打开，请保持本程序运行。\n'
               f'彻底退出：任务管理器结束 TG工具箱Web.exe。\n\n'
               f'提示：安装 .NET Framework 4.8 运行库可恢复窗口模式；'
               f'若 zip 被系统锁定，请右键 zip → 属性 → 解除锁定后重新解压。')
        ctypes.windll.user32.MessageBoxW(0, msg, 'TG小号工具箱 - 浏览器模式', 0x40)
    except Exception:
        pass
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def main():
    tg_tool.load_whitelist()
    tg_tool.load_proxy_cfg()

    port, token = server.start_server()
    # 用 localhost(不是 127.0.0.1),WebAuthn 的 rp.id 才能匹配(localhost 是特殊例外)
    url = f'http://localhost:{port}/?token={token}'

    if not _HAS_WEBVIEW:
        _browser_mode(url, _WEBVIEW_ERR)
        return

    w, h = _load_geometry()
    try:
        win = webview.create_window(
            'TG小号工具箱',
            url,
            width=w,
            height=h,
            min_size=(860, 560),
            resizable=True,
        )

        def on_closed():
            try:
                _save_geometry(win.width, win.height)
            except Exception:
                pass

        win.events.closed += on_closed
        webview.start()
    except Exception as e:
        # pythonnet/.NET/WebView2 环境问题(测试者机器常见): 降级浏览器模式
        try:
            server  # 保持服务引用
        except Exception:
            pass
        _browser_mode(url, e)


if __name__ == '__main__':
    main()
