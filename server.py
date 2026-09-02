"""TG工具箱 Web 后端 (FastAPI) —— 封装现有引擎,提供 REST + WebSocket。

引擎层(tg_engine / tg_tool / tg_profile)不改,通过 Engine 实例复用。
回调(on_log/on_progress/on_state)在引擎线程执行,经 asyncio.run_coroutine_threadsafe
桥接到 FastAPI 事件循环,再广播给 WebSocket 客户端。
"""
import asyncio
import glob
import json
import os
import socket
import sys
import threading

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import tg_tool
import tg_engine
import tg_profile

if getattr(sys, 'frozen', False):
    BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, 'webapp', 'dist')

# 账号根目录(与旧 tg_ui 的 ROOT 逻辑一致)
if tg_tool.IS_FROZEN:
    SCRIPT_DIR = tg_tool.SCRIPT_DIR
    if os.path.isdir(os.path.join(SCRIPT_DIR, '_internal')):
        ROOT = os.path.dirname(SCRIPT_DIR)   # onedir: exe 在「程序名」文件夹里
    else:
        ROOT = SCRIPT_DIR                    # onefile
else:
    ROOT = os.path.dirname(tg_tool.SCRIPT_DIR)

app = FastAPI(title='TG工具箱', docs_url=None, redoc_url=None)

# ---------- 引擎单例 + 回调桥接 ----------
_loop = None
_engine = None


def _emit(data: dict):
    if _loop:
        try:
            asyncio.run_coroutine_threadsafe(_ws_broadcast(data), _loop)
        except Exception:
            pass


def init_engine():
    global _engine
    if _engine is None:
        _engine = tg_engine.Engine(
            on_log=lambda msg: _emit({'type': 'log', 'line': msg}),
            on_progress=lambda done, total, label: _emit(
                {'type': 'progress', 'done': done, 'total': total, 'label': label}),
            on_state=lambda st, data: _emit(
                {'type': 'state', 'status': st, 'data': _jsonable(data)}),
        )
        _engine.start()
    return _engine


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, 'to_dict'):
        try:
            return _jsonable(obj.to_dict())
        except Exception:
            pass
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# ---------- WebSocket ----------
_ws_clients: set = set()


async def _ws_broadcast(data: dict):
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


@app.websocket('/ws')
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)


# ---------- 基础 ----------
@app.get('/api/ping')
async def ping():
    return {'status': 'ok', 'app': 'TG工具箱', 'root': ROOT}


# ---------- 账号列表 ----------
def _scan_accounts():
    raw = tg_engine.scan_accounts(ROOT)
    prof = tg_profile.load_profiles()
    out = []
    for name, path, st in raw:
        a = {'name': name, 'path': path, 'state': st,
             'phone': '', 'username': '', 'uid': '', 'display': '', 'avatar': ''}
        try:
            js = glob.glob(os.path.join(path, '*.json'))
            if js:
                cfg = json.load(open(js[0], encoding='utf-8'))
                a['phone'] = str(cfg.get('phone') or '')
                u = cfg.get('username') or ''
                a['username'] = str(u)
                uid = cfg.get('user_id') or cfg.get('uid') or ''
                a['uid'] = str(uid) if uid else ''
        except Exception:
            pass
        p = prof.get(name, {})
        for k in ('username', 'phone', 'uid', 'dc'):
            if p.get(k) and not a.get(k):
                a[k] = str(p[k])
        if p.get('avatar'):
            a['avatar'] = p['avatar']
        if p.get('first') or p.get('last'):
            a['display'] = (str(p.get('first') or '') + ' ' +
                            str(p.get('last') or '')).strip()
        out.append(a)
    return out


@app.get('/api/accounts')
async def accounts():
    return await asyncio.to_thread(_scan_accounts)


# ---------- 连接 ----------
@app.post('/api/connect')
async def connect(body: dict):
    eng = init_engine()
    path = body.get('path', '')
    if not path:
        return {'ok': False, 'msg': '缺少账号路径'}
    fut = eng.connect(path)
    return {'ok': True, 'msg': '连接请求已提交'}


@app.post('/api/disconnect')
async def disconnect():
    eng = init_engine()
    eng.disconnect()
    return {'ok': True}


# ---------- 任务 ----------
@app.post('/api/tasks/delete-contacts')
async def delete_contacts():
    eng = init_engine()
    eng.delete_contacts()
    return {'ok': True}


@app.post('/api/tasks/delete-dialogs')
async def delete_dialogs(body: dict):
    eng = init_engine()
    choice = body.get('choice', 'users')
    eng.delete_dialogs(choice)
    return {'ok': True}


@app.post('/api/tasks/scan-dialogs')
async def scan_dialogs():
    eng = init_engine()
    eng.scan_dialogs()
    return {'ok': True}


@app.post('/api/tasks/stop')
async def stop():
    eng = init_engine()
    eng.stop_task()
    return {'ok': True}


# ---------- 速度档 ----------
@app.get('/api/speed')
async def get_speed():
    return {'speed': 3}


@app.put('/api/speed')
async def set_speed(body: dict):
    eng = init_engine()
    idx = int(body.get('speed', 3))
    eng.set_speed(idx)
    return {'ok': True, 'speed': idx}


# ---------- 白名单 ----------
@app.get('/api/whitelist')
async def whitelist():
    return {
        'users': sorted(int(u) for u in tg_tool.USER_WHITELIST),
        'groups': sorted(int(g) for g in tg_tool.GROUP_WHITELIST),
    }


@app.post('/api/whitelist/user')
async def add_user(body: dict):
    uid = int(body.get('id', 0))
    if uid:
        tg_tool.USER_WHITELIST.add(uid)
        tg_tool.save_whitelist()
    return {'ok': True, 'users': sorted(int(u) for u in tg_tool.USER_WHITELIST)}


@app.delete('/api/whitelist/user')
async def del_user(body: dict):
    uid = int(body.get('id', 0))
    tg_tool.USER_WHITELIST.discard(uid)
    tg_tool.save_whitelist()
    return {'ok': True, 'users': sorted(int(u) for u in tg_tool.USER_WHITELIST)}


@app.post('/api/whitelist/group')
async def add_group(body: dict):
    gid = int(body.get('id', 0))
    if gid:
        tg_tool.GROUP_WHITELIST.add(gid)
        tg_tool.save_whitelist()
    return {'ok': True, 'groups': sorted(int(g) for g in tg_tool.GROUP_WHITELIST)}


@app.delete('/api/whitelist/group')
async def del_group(body: dict):
    gid = int(body.get('id', 0))
    tg_tool.GROUP_WHITELIST.discard(gid)
    tg_tool.save_whitelist()
    return {'ok': True, 'groups': sorted(int(g) for g in tg_tool.GROUP_WHITELIST)}


# ---------- 更新本体 ----------
@app.post('/api/update-telegram')
async def update_telegram():
    eng = init_engine()
    eng.update_telegram()
    return {'ok': True}


# ---------- 安全: 2FA / passkey / 邮箱 / 设备 / 资料 ----------
async def _call(fn, *args, timeout=120):
    """调用引擎方法(on_done 回调风格),等待结果返回 (ok, data)。"""
    loop = asyncio.get_event_loop()
    fut = asyncio.Future()

    def _resolve(ok, data):
        if not fut.done():
            fut.set_result((ok, data))

    def _done(ok, data):
        try:
            asyncio.run_coroutine_threadsafe(_resolve_async(fut, ok, data), loop)
        except Exception:
            pass

    async def _resolve_async(f, ok, data):
        if not f.done():
            f.set_result((ok, data))

    fn(*args, on_done=_done)
    return await asyncio.wait_for(fut, timeout)


@app.get('/api/passkeys')
async def passkeys():
    eng = init_engine()
    ok, data = await _call(eng.get_passkeys)
    return {'ok': ok, 'passkeys': _jsonable(data) if ok else []}


@app.post('/api/passkeys/delete')
async def delete_passkey(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.delete_passkey, body.get('id', ''))
    return {'ok': ok, 'msg': data}


@app.post('/api/passkeys/init')
async def init_passkey():
    eng = init_engine()
    ok, data = await _call(eng.init_passkey_registration)
    return {'ok': ok, 'qr': data if ok else ''}


@app.get('/api/2fa')
async def get_2fa():
    eng = init_engine()
    ok, data = await _call(eng.get_password_info)
    if ok:
        return {'ok': True, 'has_2fa': bool(getattr(data, 'has_password', False))}
    return {'ok': False, 'msg': data}


@app.post('/api/2fa/set')
async def set_2fa(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.set_2fa, body.get('current', ''), body.get('new', ''))
    return {'ok': ok, 'msg': data}


@app.post('/api/email/send')
async def send_email(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.send_verify_email_code, body.get('email', ''))
    return {'ok': ok, 'msg': '验证码已发送' if ok else data}


@app.post('/api/email/verify')
async def verify_email(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.verify_email, body.get('code', ''))
    return {'ok': ok, 'msg': data}


@app.get('/api/devices')
async def devices():
    eng = init_engine()
    ok, data = await _call(eng.get_authorizations)
    return {'ok': ok, 'devices': _jsonable(data) if ok else []}


@app.post('/api/devices/delete')
async def delete_device(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.reset_authorization, body.get('hash', 0))
    return {'ok': ok, 'msg': data}


@app.get('/api/profile')
async def get_profile():
    eng = init_engine()
    ok, data = await _call(eng.get_full_info)
    return {'ok': ok, 'profile': _jsonable(data) if ok else {}}


@app.post('/api/profile/update')
async def update_profile(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.update_profile,
                           body.get('first_name'), body.get('last_name'), body.get('about'))
    return {'ok': ok, 'msg': data}


@app.post('/api/profile/username')
async def update_username(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.update_username, body.get('username', ''))
    return {'ok': ok, 'msg': data}


@app.post('/api/profile/birthday')
async def update_birthday(body: dict):
    eng = init_engine()
    ok, data = await _call(eng.update_birthday,
                           int(body.get('day', 0)), int(body.get('month', 0)), body.get('year'))
    return {'ok': ok, 'msg': data}


@app.post('/api/avatar')
async def upload_avatar(body: dict):
    import base64
    b64 = body.get('data', '')
    if not b64:
        return {'ok': False, 'msg': '缺少图片数据'}
    try:
        data = base64.b64decode(b64)
    except Exception:
        return {'ok': False, 'msg': '图片数据无效'}
    eng = init_engine()
    ok, msg = await _call(eng.upload_avatar, data)
    return {'ok': ok, 'msg': msg}


# ---------- 账号分组 ----------
GROUPS_FILE = os.path.join(tg_tool.SCRIPT_DIR, 'groups.json')


def _load_groups():
    try:
        if os.path.isfile(GROUPS_FILE):
            d = json.load(open(GROUPS_FILE, encoding='utf-8'))
            if isinstance(d, dict):
                return d
    except Exception:
        pass
    return {}


def _save_groups(groups):
    try:
        json.dump(groups, open(GROUPS_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass


@app.get('/api/groups')
async def groups():
    return _load_groups()


@app.post('/api/groups')
async def create_group(body: dict):
    name = (body.get('name') or '').strip()
    groups = _load_groups()
    if not name or name in groups:
        return {'ok': False, 'msg': '分组名无效或已存在'}
    groups[name] = []
    _save_groups(groups)
    return {'ok': True, 'groups': groups}


@app.delete('/api/groups/{name}')
async def delete_group(name: str):
    groups = _load_groups()
    groups.pop(name, None)
    _save_groups(groups)
    return {'ok': True, 'groups': groups}


@app.post('/api/groups/move')
async def move_account(body: dict):
    name = body.get('name', '')
    group = body.get('group', '')
    groups = _load_groups()
    for g in groups:
        if name in groups[g]:
            groups[g].remove(name)
    if group and group != 'ungrouped':
        groups.setdefault(group, []).append(name)
    _save_groups(groups)
    return {'ok': True, 'groups': groups}


# ---------- tdata 转换 ----------
@app.post('/api/convert-tdata')
async def convert_tdata(body: dict):
    eng = init_engine()
    path = body.get('path', '')
    if not path:
        return {'ok': False, 'msg': '缺少账号路径'}
    fut = eng.convert_tdata(path)
    try:
        ok = await asyncio.wait_for(asyncio.wrap_future(fut), 300)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': bool(ok), 'msg': '转换完成' if ok else '转换失败'}


# ---------- 拖放导入账号 ----------
def _account_kind(d):
    if os.path.isdir(os.path.join(d, 'tdata')):
        return 'tdata'
    sess = glob.glob(os.path.join(d, '*.session'))
    js = [f for f in glob.glob(os.path.join(d, '*.json')) if tg_tool._is_account_json(f)]
    if sess and js:
        return 'session'
    return None


def _find_account(d):
    r = _account_kind(d)
    if r:
        return d, r
    for sub in sorted(os.listdir(d)):
        subd = os.path.join(d, sub)
        if os.path.isdir(subd):
            r = _account_kind(subd)
            if r:
                return subd, r
    return None, None


def _unique_target(root, name):
    clean = name.strip() or '账号'
    for ch in '\\/:*?"<>|':
        clean = clean.replace(ch, '_')
    cand = os.path.join(root, clean)
    if not os.path.exists(cand):
        return cand
    i = 2
    while os.path.exists(f'{cand}_{i}'):
        i += 1
    return f'{cand}_{i}'


@app.post('/api/import')
async def import_archive(body: dict):
    import base64
    import io
    import zipfile
    import tempfile
    import shutil
    b64 = body.get('data', '')
    name = body.get('name', '账号')
    if not b64:
        return {'ok': False, 'msg': '缺少数据'}
    try:
        zip_bytes = base64.b64decode(b64)
    except Exception:
        return {'ok': False, 'msg': '数据无效'}
    tmp = tempfile.mkdtemp(prefix='tgimport_')
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp)
        src, kind = _find_account(tmp)
        if src is None:
            return {'ok': False, 'msg': '压缩包里没找到 tdata 或 session+json 账号结构'}
        target = _unique_target(ROOT, name)
        os.makedirs(target, exist_ok=True)
        for entry in os.listdir(src):
            s = os.path.join(src, entry)
            d = os.path.join(target, entry)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        if kind == 'tdata':
            eng = init_engine()
            fut = eng.convert_tdata(target)
            await asyncio.wait_for(asyncio.wrap_future(fut), 300)
        return {'ok': True, 'msg': f'已导入 {os.path.basename(target)}'}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- 静态前端 ----------
if os.path.isdir(DIST):
    app.mount('/', StaticFiles(directory=DIST, html=True), name='static')


def _pick_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server(port: int = 0):
    port = port or _pick_port()
    config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning')
    srv = uvicorn.Server(config)

    def _run():
        asyncio.run(srv.serve())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return port


if __name__ == '__main__':
    p = _pick_port()
    print(f'后端启动于 http://127.0.0.1:{p}')
    uvicorn.run(app, host='127.0.0.1', port=p, log_level='info')
