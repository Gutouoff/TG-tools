"""TG工具箱 Web 前端入口 (pywebview 壳)。

启动 FastAPI 后端(后台线程),开 WebView2 窗口加载前端。
普通桌面程序形态: 无地址栏、非浏览器。窗口尺寸记忆到 settings.json。
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import webview          # noqa: E402
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


def main():
    tg_tool.load_whitelist()
    tg_tool.load_proxy_cfg()

    port, token = server.start_server()
    url = f'http://127.0.0.1:{port}/?token={token}'

    w, h = _load_geometry()
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


if __name__ == '__main__':
    main()
