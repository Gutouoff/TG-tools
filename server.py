"""TG工具箱 Web 后端 (FastAPI) —— 封装现有引擎,提供 REST + WebSocket。

骨架阶段: 先跑通 ping / 静态前端 / WebSocket 握手,再逐步补 API。
引擎层(tg_engine / tg_tool / tg_profile)一行不改,通过 asyncio.to_thread 调用。
"""
import asyncio
import os
import socket
import threading

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import tg_tool

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, 'webapp', 'dist')

app = FastAPI(title='TG工具箱', docs_url=None, redoc_url=None)


@app.get('/api/ping')
async def ping():
    """握手探活。"""
    return {'status': 'ok', 'app': 'TG工具箱', 'script_dir': tg_tool.SCRIPT_DIR}


# ---------- WebSocket(进度/状态/日志,后续聚合) ----------
_ws_clients: set = set()


@app.websocket('/ws')
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)


async def ws_broadcast(data: dict):
    """向所有 WebSocket 客户端广播(骨架阶段简单实现,后续加聚合)。"""
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


# ---------- 静态前端(生产: dist 产物) ----------
if os.path.isdir(DIST):
    app.mount('/', StaticFiles(directory=DIST, html=True), name='static')


def _pick_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server(port: int = 0):
    """后台线程启动 uvicorn,返回实际端口(供 pywebview 加载)。"""
    port = port or _pick_port()
    config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning')
    srv = uvicorn.Server(config)

    def _run():
        asyncio.run(srv.serve())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # 等端口就绪
    return port


if __name__ == '__main__':
    p = _pick_port()
    print(f'后端启动于 http://127.0.0.1:{p}')
    uvicorn.run(app, host='127.0.0.1', port=p, log_level='info')
