"""TG工具箱 Web 前端入口 (pywebview 壳)。

启动 FastAPI 后端(后台线程),开 WebView2 窗口加载前端。
普通桌面程序形态: 无地址栏、非浏览器。
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import webview          # noqa: E402
import tg_tool          # noqa: E402
import server           # noqa: E402


def main():
    tg_tool.load_whitelist()
    tg_tool.load_proxy_cfg()

    port = server.start_server()
    url = f'http://127.0.0.1:{port}/'
    print(f'[web] 后端: {url}')

    webview.create_window(
        'TG小号工具箱',
        url,
        width=1100,
        height=680,
        min_size=(860, 560),
        resizable=True,
    )
    webview.start()


if __name__ == '__main__':
    main()
