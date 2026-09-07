"""TG工具箱 Web 后端 (FastAPI) —— 封装现有引擎,提供 REST + WebSocket。

引擎层(tg_engine / tg_tool / tg_profile)不改,通过 Engine 实例复用。
回调(on_log/on_progress/on_state)在引擎线程执行,经 asyncio.run_coroutine_threadsafe
桥接到 FastAPI 事件循环,再广播给 WebSocket 客户端。
"""
import asyncio
import glob
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import tg_tool
import tg_engine
import tg_profile
import cable

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

@asynccontextmanager
async def lifespan(app):
    global _loop
    _loop = asyncio.get_event_loop()
    yield


app = FastAPI(title='TG工具箱', docs_url=None, redoc_url=None, lifespan=lifespan)

# 本地 API 鉴权 token
TOKEN = secrets.token_urlsafe(32)


class _AuthMiddleware:
    """纯 ASGI 中间件(不走 BaseHTTPMiddleware): token 鉴权 + 异常兜底。
    BaseHTTPMiddleware 会把路由内真实异常吞成 "No response returned.",
    纯 ASGI 下异常原样穿透到本层,可带回真实原因。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        path = scope['path']
        headers = {k.decode('latin-1').lower(): v.decode('latin-1')
                   for k, v in scope.get('headers', [])}
        # DNS rebinding 防护: 只信任本机来源(浏览器直连/webview 壳),
        # 恶意网站把域名解析到 127.0.0.1 时 Host 会是攻击者域名
        if path.startswith('/api') or path == '/':
            host = headers.get('host', '')
            host_name = host.split(':')[0].strip().lower()
            if host_name not in ('localhost', '127.0.0.1'):
                resp = json.dumps({'detail': 'forbidden host'}).encode()
                await send({'type': 'http.response.start', 'status': 403,
                            'headers': [(b'content-type', b'application/json'),
                                        (b'content-length', str(len(resp)).encode())]})
                await send({'type': 'http.response.body', 'body': resp})
                return
        if path.startswith('/api') and scope['method'] != 'OPTIONS':
            token = headers.get('x-tg-token', '')
            # <img> 标签无法带 header,仅头像图片端点放行 query token
            if not token and path == '/api/avatar-image':
                qs = (scope.get('query_string') or b'').decode('latin-1')
                for kv in qs.split('&'):
                    if kv.startswith('token='):
                        token = kv[len('token='):]
                        break
            if token != TOKEN:
                resp = json.dumps({'detail': 'unauthorized'}).encode()
                await send({'type': 'http.response.start', 'status': 401,
                            'headers': [(b'content-type', b'application/json'),
                                        (b'content-length', str(len(resp)).encode())]})
                await send({'type': 'http.response.body', 'body': resp})
                return
        # 异常兜底: 真实异常原样穿透到这层,转成 JSON(响应未开始时)
        started = False

        async def send_wrapper(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            if not started:
                resp = json.dumps({'ok': False,
                                   'msg': f'服务器内部错误: {type(e).__name__}: {str(e)[:200]}'}).encode()
                await send({'type': 'http.response.start', 'status': 500,
                            'headers': [(b'content-type', b'application/json'),
                                        (b'content-length', str(len(resp)).encode())]})
                await send({'type': 'http.response.body', 'body': resp})
            if not isinstance(e, Exception):
                raise   # SystemExit 等继续上抛交回运行时
        except BaseException as e:
            if not started:
                resp = json.dumps({'ok': False,
                                   'msg': f'服务器异常中止: {type(e).__name__}: {str(e)[:200]}'}).encode()
                await send({'type': 'http.response.start', 'status': 500,
                            'headers': [(b'content-type', b'application/json'),
                                        (b'content-length', str(len(resp)).encode())]})
                await send({'type': 'http.response.body', 'body': resp})
            raise


app.add_middleware(_AuthMiddleware)

# ---------- 引擎单例 + 回调桥接 ----------
_loop = None
_engine = None


def _emit(data: dict):
    # 日志行统一打码手机号(引擎日志不走 tg_tool.log,补一层)
    if data.get('type') == 'log' and data.get('line'):
        data = {**data, 'line': tg_tool._mask_phone_text(data['line'])}
    # debug 诊断事件(蓝牙原始广播/厂商数据/EID 诊断)只在 debug 等级下发
    if data.get('type') == 'state':
        st = str(data.get('status') or '')
        if st.startswith(('passkey_adv:', 'passkey_mfg:', 'passkey_diag:')):
            try:
                if _load_settings().get('log_level') != 'debug':
                    return
            except Exception:
                pass
    if _loop:
        try:
            asyncio.run_coroutine_threadsafe(_ws_broadcast(data), _loop)
        except Exception:
            pass


def init_engine():
    global _engine
    # tg_tool.log 的行(资料刷新失败原因等)也广播到 Web 日志页
    if tg_tool.UI_LOG_HOOK is None:
        tg_tool.UI_LOG_HOOK = lambda msg: _emit({'type': 'log', 'line': msg})
    if _engine is None:
        _engine = tg_engine.Engine(
            on_log=lambda msg: _emit({'type': 'log', 'line': msg}),
            on_progress=lambda done, total, label: _emit(
                {'type': 'progress', 'done': done, 'total': total, 'label': label}),
            on_state=lambda st, data: _emit(
                {'type': 'state', 'status': st, 'data': _jsonable(data)}),
            on_message=lambda data: _emit(
                {'type': 'state', 'status': 'recv_message', 'data': _jsonable(data)}),
        )
        _engine.start()
    return _engine


def _ensure_in_root(p):
    """校验路径必须落在 ROOT 内,越界抛 400。返回 realpath。"""
    from fastapi import HTTPException
    if not p:
        raise HTTPException(status_code=400, detail='缺少路径')
    real = os.path.realpath(p)
    root_real = os.path.realpath(ROOT)
    try:
        if os.path.commonpath([real, root_real]) != root_real:
            raise HTTPException(status_code=400, detail='路径越界')
    except ValueError:
        raise HTTPException(status_code=400, detail='路径越界')
    return real


def _clean_name(name):
    """清洗名称: 只保留中文/字母/数字/下划线/短横线,禁止路径分隔符与命令字符。"""
    clean = re.sub(r'[^\w\u4e00-\u9fff-]', '_', name or '')
    clean = clean.replace('..', '_')
    clean = clean.strip('_') or '账号'
    return clean


def _as_int(v, default=0):
    """请求字段安全转 int,非法输入回退默认值(避免 500)。"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


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
    if ws.query_params.get('token', '') != TOKEN:
        await ws.close(code=4001)
        return
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
    return {'status': 'ok', 'app': 'TG工具箱', 'version': tg_tool.APP_VERSION}


# ---------- 账号列表 ----------
def _country_of(phone):
    """区号最长前缀匹配 -> (两字母码, 中文名)。"""
    best = None
    for code, (cc, name) in tg_profile.PHONE_CODE_MAP.items():
        if phone.startswith(code) and (best is None or len(code) > len(best[0])):
            best = (code, cc, name)
    if best:
        return best[1], best[2]
    return '', ''


def _scan_accounts():
    raw = tg_engine.scan_accounts(ROOT)
    prof = tg_profile.load_profiles()
    poll = _load_poll_results()
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
        cc, cname = _country_of(a['phone'])
        a['country'] = cname
        pr = poll.get(name)
        if pr:
            a['poll_alive'] = pr.get('alive')   # True/False/None(None=未判定,前端显示?不显示死)
            a['poll_time'] = str(pr.get('time', ''))
            a['poll_msg'] = str(pr.get('msg', ''))
        out.append(a)
    return out


@app.get('/api/accounts')
async def accounts():
    return await asyncio.to_thread(_scan_accounts)


# ---------- 连接 ----------
@app.post('/api/connect')
async def connect(body: dict):
    eng = init_engine()
    path = _ensure_in_root(body.get('path', ''))
    fut = eng.connect(path)
    try:
        # tdata-only 账号会先自动转换(opentele 含网络操作,耗时较长)
        info = await asyncio.wait_for(asyncio.wrap_future(fut), 180)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    # 登录后获取 username
    try:
        ok, me = await _call(eng.get_me, timeout=20)
        info['username'] = (me or {}).get('username', '') if ok else ''
    except Exception:
        info['username'] = ''
    # 连接成功即自动开启消息接收(规则沿用设置;用户可在界面随时关闭,重连恢复开启)
    try:
        s = _load_settings()
        eng.set_recv(True, {k: s.get(k) for k in
                            ('recv_exclude_channels', 'recv_exclude_groups', 'recv_exclude_bots')})
        if not s.get('recv_on'):
            s['recv_on'] = True
            _save_settings(s)
    except Exception:
        pass
    # 连接成功后自动拉取会话列表(前端进"消息接收"页零等待)
    dialogs = []
    try:
        _d = await asyncio.wait_for(asyncio.wrap_future(eng.list_dialogs(info['name'])), 60)
        dialogs = _d or []
    except Exception:
        pass
    # 同步返回池中所有在线账号(前端按 name 匹配打在线徽标)
    online = []
    try:
        _ok, onl = await _call(eng.online_accounts, timeout=10)
        if _ok and onl:
            online = onl
    except Exception:
        pass
    return {'ok': True, 'info': _jsonable(info), 'online': _jsonable(online),
            'dialogs': _jsonable(dialogs)}


# ---------- 聊天: 消息接收 / 加群频道 ----------
@app.get('/api/recv')
async def get_recv():
    s = _load_settings()
    return {'ok': True,
            'on': bool(s.get('recv_on')),
            'rules': {k: bool(s.get(k)) for k in
                      ('recv_exclude_channels', 'recv_exclude_groups', 'recv_exclude_bots')}}


@app.post('/api/recv')
async def set_recv(body: dict):
    eng = init_engine()
    on = bool(body.get('on'))
    rules = body.get('rules') or {}
    s = _load_settings()
    s['recv_on'] = on
    for k in ('recv_exclude_channels', 'recv_exclude_groups', 'recv_exclude_bots'):
        if k in rules:
            s[k] = bool(rules[k])
    _save_settings(s)
    eng.set_recv(on, rules)
    return {'ok': True, 'on': on,
            'rules': {k: bool(s.get(k)) for k in
                      ('recv_exclude_channels', 'recv_exclude_groups', 'recv_exclude_bots')}}


@app.post('/api/join-channels')
async def join_channels(body: dict):
    eng = init_engine()
    links = body.get('links') or []
    if isinstance(links, str):
        links = links.splitlines()
    links = [str(l).strip() for l in links if str(l).strip()]
    if not links:
        return {'ok': False, 'msg': '链接列表为空'}
    fut = eng.join_chats(links)
    try:
        results = await asyncio.wait_for(asyncio.wrap_future(fut), 300)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'results': _jsonable(results or [])}


@app.get('/api/dialogs')
async def get_dialogs(account: str = ''):
    """抓取在线账号的会话列表。"""
    if not account:
        return {'ok': False, 'msg': '缺少 account'}
    eng = init_engine()
    fut = eng.list_dialogs(account)
    try:
        dialogs = await asyncio.wait_for(asyncio.wrap_future(fut), 90)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'dialogs': _jsonable(dialogs or [])}


@app.post('/api/history')
async def history(body: dict):
    """拉取会话历史消息;offset_id 传最早一条 id 向更早翻页。"""
    account = str(body.get('account') or '')
    dialog_id = body.get('dialog_id')
    if not account or dialog_id is None:
        return {'ok': False, 'msg': '参数缺失'}
    eng = init_engine()
    limit = min(int(body.get('limit') or 20), 100)
    offset_id = int(body.get('offset_id') or 0)
    fut = eng.fetch_history(account, dialog_id, limit, offset_id)
    try:
        msgs = await asyncio.wait_for(asyncio.wrap_future(fut), 90)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'msgs': _jsonable(msgs or [])}


@app.post('/api/chat/send')
async def chat_send(body: dict):
    """在指定会话发送文本消息(目前仅适配文本)。"""
    account = str(body.get('account') or '')
    dialog_id = body.get('dialog_id')
    text = str(body.get('text') or '').strip()
    if not account or dialog_id is None or not text:
        return {'ok': False, 'msg': '参数缺失'}
    eng = init_engine()
    fut = eng.send_message(account, int(dialog_id), text)
    try:
        msg = await asyncio.wait_for(asyncio.wrap_future(fut), 30)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'msg': _jsonable(msg)}


@app.get('/api/me')
async def me():
    eng = init_engine()
    ok, data = await _call(eng.get_me)
    return {'ok': ok, 'me': _jsonable(data) if ok else {}}


@app.post('/api/fetch-avatars')
async def fetch_avatars():
    """一键获取所有账号头像/资料(复用 tg_profile 后台刷新,增量落盘)。"""
    def on_update(name, info):
        if name is None:
            _emit({'type': 'avatars_done'})
        else:
            _emit({'type': 'progress', 'label': f'拉取 {name}', 'done': 0, 'total': 0})
    try:
        tg_profile.start_refresh(ROOT, on_update)
        return {'ok': True, 'msg': '已开始后台获取头像'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


def _guess_image_media(path):
    """按文件头字节判断真实图片类型(兼容历史头像 JPEG 字节存成 .png 的情况)。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(16)
    except Exception:
        return None
    if head[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if head[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    return None


@app.post('/api/refresh-avatar')
async def refresh_avatar(body: dict):
    """刷新单个账号头像/资料(同步等待)。在线账号用池内 client,离线才临时开 client。"""
    name = str(body.get('name', ''))
    if not name:
        return {'ok': False, 'msg': '缺少账号名'}
    if name in ('.', '..') or '/' in name or '\\' in name:
        return {'ok': False, 'msg': '非法账号名'}
    eng = init_engine()
    # 在线账号: 复用池内 client(二次连接会撞 .session 的 SQLite 锁)
    fut = eng.refresh_profile(name)
    try:
        info = await asyncio.wait_for(asyncio.wrap_future(fut), 60)
    except RuntimeError:
        info = None  # 不在线 → 走临时 client
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    if info is None:
        def _run():
            return tg_profile.refresh_one(ROOT, name)
        info = await asyncio.to_thread(_run)
        if info is None:
            # refresh_one 已把原因打进日志(无json/无session/登录失效/连接失败)
            return {'ok': False, 'msg': '刷新失败(原因见日志)', 'info': {}}
    # 刷新成功 = 账号必然活着: 若轮询曾标记死号,改回存活让标识消失
    try:
        import time as _t
        p = os.path.join(tg_tool.SCRIPT_DIR, 'poll_results.json')
        res = json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else {}
        if res.get(name, {}).get('alive') is not True:
            res[name] = {'alive': True, 'msg': '存活(手动刷新账号信息)',
                         'time': _t.strftime('%Y-%m-%d %H:%M')}
            json.dump(res, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception:
        pass
    return {'ok': True, 'info': _jsonable(info)}


@app.get('/api/export-accounts')
async def export_accounts():
    """导出账号信息到固定表格 账号总表.xlsx(ROOT 下,每次覆盖更新)并用系统程序直接打开。"""
    import subprocess
    import sys
    from datetime import datetime
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return {'ok': False, 'msg': '服务器缺少 openpyxl 依赖,无法导出'}

    rows = _scan_accounts()
    eng = init_engine()
    sec = {}
    try:
        ok, data = await _call(eng.online_accounts, timeout=10)
        online = [o.get('name') if isinstance(o, dict) else o for o in (_jsonable(data) or [])]
    except Exception:
        online = []
    if online:
        try:
            ok, data = await _call(lambda: eng.security_info(online), timeout=60)
            if ok and data:
                sec = data
        except Exception:
            pass

    def _fmt_phone(raw: str) -> str:
        """手机号 -> Excel 公式 ="+"&"62"&" "&"8112115091"。"""
        digits = str(raw or '').strip()
        if not digits:
            return ''
        if not digits.startswith('+'):
            digits = '+' + digits
        body = digits[1:].replace(' ', '').replace('-', '')
        cc = body[:2] if len(body) > 2 else body
        rest = body[2:] if len(body) > 2 else ''
        return f'="+"&"{cc}"&" "&"{rest}"'

    wb = Workbook()
    ws = wb.active
    ws.title = '账号信息'
    headers = ['用户名', 'ID', 'username', '手机号码', '邮箱', '通行密钥', '2FA', '注册时间', '国家', '状态', '导出时间']
    header_fill = PatternFill('solid', fgColor='009688')
    header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin = Border(*(Side(style='thin', color='DCE9E5'),) * 4)
    body_font = Font(name='微软雅黑', size=10)
    ws.append(headers)
    for c in ws[1]:
        c.fill = header_fill
        c.font = header_font
        c.alignment = center
        c.border = thin
    export_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    for a in rows:
        name = a.get('name', '')
        info = sec.get(name) or {}
        poll = a.get('poll_alive')
        status = '死号' if poll is False else ''
        if not status and a.get('state') == 'empty':
            status = '无登录态'
        pk_n = info.get('passkeys')
        ws.append([
            a.get('display') or a.get('name', ''),
            a.get('uid', ''),
            a.get('username', ''),
            _fmt_phone(a.get('phone', '')),
            info.get('email') or '',
            str(pk_n) if pk_n is not None else '',
            info.get('twofa') or '',
            '',
            a.get('country', ''),
            status,
            export_time,
        ])
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = body_font
            c.border = thin
            c.alignment = Alignment(vertical='center')
    for i, w in enumerate([18, 14, 18, 22, 28, 10, 18, 12, 10, 10, 16], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    # 固定路径覆盖写入,每次导出都在同一表格上更新
    # 优先部署目录(D:\Desktop\TG小号,exe 的 ROOT),源码调试时回退 ROOT
    base = ROOT if ROOT != os.path.dirname(SCRIPT_DIR) else ROOT
    table_root = r'D:\Desktop\TG小号' if os.path.isdir(r'D:\Desktop\TG小号') else ROOT
    out_path = os.path.join(table_root, '账号总表.xlsx')
    try:
        wb.save(out_path)
    except PermissionError:
        return {'ok': False, 'msg': '表格正被 Excel 打开占用,请关闭表格后重试'}
    except Exception as e:
        return {'ok': False, 'msg': f'写入失败: {e}'}

    # 用系统默认程序(Excel)直接打开表格
    try:
        os.startfile(out_path)          # Windows: 调系统关联程序打开
    except Exception:
        # 无关联程序时的兜底: 资源管理器定位文件。
        # 千万不能用 sys.executable 打开——打包环境里那是本程序 exe,
        # 会把 xlsx 当参数再启动一个工具箱实例
        try:
            subprocess.Popen(['explorer', '/select,', out_path])
        except Exception:
            pass
    return {'ok': True, 'path': out_path, 'count': len(rows), 'time': export_time}




@app.get('/api/avatar-image')
async def avatar_image(name: str):
    """返回账号头像图片(供前端 <img> 加载,失败 404 回退色块)。"""
    from fastapi.responses import FileResponse, JSONResponse
    prof = tg_profile.load_profiles()
    p = prof.get(name, {}).get('avatar', '')
    if p:
        real = os.path.realpath(p)
        # 允许的头像目录: exe 的 avatars + 旧工具箱的 avatars(历史缓存)
        allowed = [os.path.realpath(tg_profile.AVATAR_DIR),
                   os.path.realpath(os.path.join(ROOT, '工具箱', 'avatars'))]
        try:
            ok = os.path.isfile(real) and any(
                os.path.commonpath([real, d]) == d for d in allowed)
            if ok:
                media = _guess_image_media(real)
                resp = FileResponse(real, media_type=media) if media else FileResponse(real)
                # 头像文件会被原地覆盖更新,禁止 WebView2 缓存旧图
                resp.headers['Cache-Control'] = 'no-cache'
                return resp
        except ValueError:
            pass
    return JSONResponse(status_code=404, content={'detail': 'no avatar'})


@app.post('/api/disconnect')
async def disconnect(body: dict = None):
    eng = init_engine()
    name = (body or {}).get('name') if isinstance(body, dict) else None
    fut = eng.disconnect(name)
    try:
        await asyncio.wait_for(asyncio.wrap_future(fut), 30)
    except Exception:
        pass
    return {'ok': True}


@app.post('/api/switch')
async def switch(body: dict):
    """秒切到池中已在线的账号(不重连)。"""
    eng = init_engine()
    name = body.get('name', '')
    if not name:
        return {'ok': False, 'msg': '缺少账号名'}
    fut = eng.switch(name)
    try:
        info = await asyncio.wait_for(asyncio.wrap_future(fut), 15)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    if not info:
        return {'ok': False, 'msg': '该账号不在线,请先连接'}
    # 秒切后保持消息接收开启(幂等,已注册的 client 不会重复)
    try:
        s = _load_settings()
        eng.set_recv(True, {k: s.get(k) for k in
                            ('recv_exclude_channels', 'recv_exclude_groups', 'recv_exclude_bots')})
    except Exception:
        pass
    return {'ok': True, 'info': _jsonable(info)}


@app.get('/api/online')
async def online():
    """当前在线账号列表(连接池)。"""
    eng = init_engine()
    ok, data = await _call(eng.online_accounts, timeout=10)
    return {'ok': ok, 'online': _jsonable(data) if ok and data else []}


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
    idx = _as_int(body.get('speed', 3), 3)
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
    uid = _as_int(body.get('id', 0))
    if uid:
        tg_tool.USER_WHITELIST.add(uid)
        tg_tool.save_whitelist()
    return {'ok': True, 'users': sorted(int(u) for u in tg_tool.USER_WHITELIST)}


@app.delete('/api/whitelist/user')
async def del_user(body: dict):
    uid = _as_int(body.get('id', 0))
    tg_tool.USER_WHITELIST.discard(uid)
    tg_tool.save_whitelist()
    return {'ok': True, 'users': sorted(int(u) for u in tg_tool.USER_WHITELIST)}


@app.post('/api/whitelist/group')
async def add_group(body: dict):
    gid = _as_int(body.get('id', 0))
    if gid:
        tg_tool.GROUP_WHITELIST.add(gid)
        tg_tool.save_whitelist()
    return {'ok': True, 'groups': sorted(int(g) for g in tg_tool.GROUP_WHITELIST)}


@app.delete('/api/whitelist/group')
async def del_group(body: dict):
    gid = _as_int(body.get('id', 0))
    tg_tool.GROUP_WHITELIST.discard(gid)
    tg_tool.save_whitelist()
    return {'ok': True, 'groups': sorted(int(g) for g in tg_tool.GROUP_WHITELIST)}


# ---------- 更新本体 ----------
@app.post('/api/update-telegram')
async def update_telegram():
    eng = init_engine()
    eng.update_telegram(ROOT)   # 显式传账号根目录(打包环境 WORKDIR=exe 目录)
    return {'ok': True}


@app.post('/api/poll-accounts')
async def poll_accounts(body: dict = None):
    """账号轮询: 逐号登录一次保活+测活(后台任务,进度走 WebSocket)。
    body.group 可限定范围: 分组名 / 'ungrouped' / 缺省=全部。"""
    eng = init_engine()
    group = (body or {}).get('group') if isinstance(body, dict) else None
    try:
        eng.poll_accounts(ROOT, group)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'msg': '已开始'}


@app.post('/api/convert-to-tdata')
async def convert_to_tdata(body: dict):
    """session+json → Telegram Desktop tdata(在线账号复用池内 client)。"""
    path = _ensure_in_root(body.get('path', ''))
    overwrite = bool(body.get('overwrite'))
    twofa_password = str(body.get('twofa_password') or '')
    eng = init_engine()
    fut = eng.convert_to_tdata(path, overwrite=overwrite, twofa_password=twofa_password)
    try:
        target = await asyncio.wait_for(asyncio.wrap_future(fut), 120)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'path': target, 'msg': os.path.basename(path)}


@app.post('/api/refresh-session')
async def refresh_session(body: dict):
    """tdata → session+json 覆盖刷新(在线账号只刷 json 元数据)。"""
    path = _ensure_in_root(body.get('path', ''))
    eng = init_engine()
    fut = eng.refresh_session_from_tdata(path)
    try:
        await asyncio.wait_for(asyncio.wrap_future(fut), 180)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'msg': '已刷新'}


@app.post('/api/refresh-ss-batch')
async def refresh_ss_batch():
    """批量刷新: 所有有 tdata 且测活失败的离线账号重建 session+json(后台任务)。"""
    eng = init_engine()
    try:
        eng.refresh_sessions_batch(ROOT)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'msg': '已开始'}


@app.post('/api/start-chat')
async def start_chat(body: dict):
    """按用户名解析会话对象,供前端直接发起聊天。"""
    account = str(body.get('account') or '')
    username = str(body.get('username') or '').strip()
    if not account or not username:
        return {'ok': False, 'msg': '参数缺失'}
    eng = init_engine()
    fut = eng.start_chat(account, username)
    try:
        dialog = await asyncio.wait_for(asyncio.wrap_future(fut), 45)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'dialog': _jsonable(dialog)}


def _load_poll_results():
    try:
        p = os.path.join(tg_tool.SCRIPT_DIR, 'poll_results.json')
        if os.path.isfile(p):
            return json.load(open(p, encoding='utf-8'))
    except Exception:
        pass
    return {}


def _scrub_account_meta(name, new_name=None):
    """账号删/改名后同步清理元数据缓存(分组/资料/头像/轮询结果)。"""
    try:
        if os.path.isfile(GROUPS_FILE):
            g = json.load(open(GROUPS_FILE, encoding='utf-8'))
            changed = False
            for k, lst in g.items():
                if isinstance(lst, list) and name in lst:
                    if new_name:
                        g[k] = [new_name if x == name else x for x in lst]
                    else:
                        g[k] = [x for x in lst if x != name]
                    changed = True
            if changed:
                json.dump(g, open(GROUPS_FILE, 'w', encoding='utf-8'),
                          ensure_ascii=False)
    except Exception:
        pass
    try:
        prof = tg_profile.load_profiles()
        if name in prof:
            if new_name:
                prof[new_name] = prof.pop(name)
            else:
                prof.pop(name)
            tg_profile.save_profiles(prof)
        av = tg_profile.avatar_path(name)
        if os.path.isfile(av):
            if new_name:
                os.replace(av, tg_profile.avatar_path(new_name))
            else:
                os.remove(av)
    except Exception:
        pass
    try:
        p = os.path.join(tg_tool.SCRIPT_DIR, 'poll_results.json')
        if os.path.isfile(p):
            res = json.load(open(p, encoding='utf-8'))
            if name in res:
                if new_name:
                    res[new_name] = res.pop(name)
                else:
                    res.pop(name)
                json.dump(res, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception:
        pass


@app.post('/api/launch-client')
async def launch_client(body: dict):
    """启动账号目录内的 Telegram 便携版客户端(找到 Telegram.exe 即启动)。"""
    import subprocess
    path = _ensure_in_root(body.get('path', ''))
    if not os.path.isdir(path):
        return {'ok': False, 'msg': '账号目录不存在'}
    exe = None
    for root, dirs, files in os.walk(path):
        if 'Telegram.exe' in files:
            exe = os.path.join(root, 'Telegram.exe')
            break
        for n in tg_tool.EXE_NAMES:
            if n in files:
                exe = os.path.join(root, n)
                break
        if exe:
            break
    if not exe:
        return {'ok': False, 'msg': '该账号目录下未找到 Telegram.exe,可先用「更新本体」安装便携版'}
    try:
        subprocess.Popen(
            [exe], cwd=os.path.dirname(exe),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True)
    except Exception as e:
        return {'ok': False, 'msg': f'启动失败: {e}'}
    return {'ok': True, 'msg': os.path.relpath(exe, path)}


@app.post('/api/open-folder')
async def open_folder(body: dict):
    """在资源管理器中打开账号文件夹并定位。"""
    import subprocess
    path = _ensure_in_root(body.get('path', ''))
    if not os.path.isdir(path):
        return {'ok': False, 'msg': '账号目录不存在'}
    try:
        # 直接打开账号文件夹本身(即 tdata/session 所在的那一级)
        subprocess.Popen(['explorer', os.path.normpath(path)])
    except Exception as e:
        return {'ok': False, 'msg': f'打开失败: {e}'}
    return {'ok': True}


@app.post('/api/rename-account')
async def rename_account(body: dict):
    """重命名账号文件夹(在线账号会先自动断开:session 文件占用会锁住改名)。"""
    import re
    path = _ensure_in_root(body.get('path', ''))
    new_name = str(body.get('new_name', '') or '').strip()
    old_name = os.path.basename(os.path.normpath(path))
    if not os.path.isdir(path):
        return {'ok': False, 'msg': '账号目录不存在'}
    if not new_name:
        return {'ok': False, 'msg': '请输入新名称'}
    if new_name != old_name:
        if not re.fullmatch(r'[^\\/:*?"<>|]{1,60}', new_name):
            return {'ok': False, 'msg': '名称含非法字符(\\ / : * ? " < > |)或过长'}
        if new_name in tg_engine.EXCLUDE_DIRS:
            return {'ok': False, 'msg': '该名称是保留目录名'}
        if os.path.exists(os.path.join(os.path.dirname(path), new_name)):
            return {'ok': False, 'msg': '同名文件夹已存在'}
    if new_name == old_name:
        return {'ok': True, 'new_path': path, 'msg': '名称未变化'}
    eng = init_engine()
    # 在线账号先断开(SQLite session 文件被占用会让 os.rename 报错)
    try:
        fut = eng.disconnect(old_name)
        await asyncio.wait_for(asyncio.wrap_future(fut), 30)
    except Exception:
        pass
    try:
        os.rename(path, os.path.join(os.path.dirname(path), new_name))
    except OSError as e:
        return {'ok': False, 'msg': f'重命名失败: {e}(若刚用过「启动客户端」,请先关闭该客户端)'}
    # 分组/资料缓存/头像文件同步改名(失败不阻塞,缓存下次刷新会自愈)
    try:
        if os.path.isfile(GROUPS_FILE):
            g = json.load(open(GROUPS_FILE, encoding='utf-8'))
            changed = False
            for k, lst in g.items():
                if isinstance(lst, list) and old_name in lst:
                    g[k] = [new_name if x == old else x for x in lst]
                    changed = True
            if changed:
                json.dump(g, open(GROUPS_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception:
        pass
    try:
        prof = tg_profile.load_profiles()
        if old_name in prof:
            prof[new_name] = prof.pop(old_name)
            tg_profile.save_profiles(prof)
        old_av = tg_profile.avatar_path(old_name)
        if os.path.isfile(old_av):
            os.replace(old_av, tg_profile.avatar_path(new_name))
    except Exception:
        pass
    new_path = os.path.join(os.path.dirname(path), new_name)
    _emit({'type': 'log', 'line': f'[账号] 文件夹已重命名: {old_name} → {new_name}'})
    return {'ok': True, 'new_path': new_path, 'msg': new_name}


@app.post('/api/delete-account')
async def delete_account(body: dict):
    """永久删除账号文件夹及其全部内容(二级确认由前端保证)。"""
    import shutil
    path = _ensure_in_root(body.get('path', ''))
    real = os.path.realpath(path)
    root_real = os.path.realpath(ROOT)
    name = os.path.basename(real)
    if real == root_real:
        return {'ok': False, 'msg': '不能删除账号根目录'}
    if os.path.dirname(real) != root_real:
        return {'ok': False, 'msg': '只允许删除账号根目录下的一级文件夹'}
    if name in tg_engine.EXCLUDE_DIRS:
        return {'ok': False, 'msg': '该目录不是账号文件夹,拒绝删除'}
    if '工具箱' in name or name.startswith('TG') or name in ('qifu', 'modules'):
        return {'ok': False, 'msg': '该目录疑似程序目录,拒绝删除'}
    if not os.path.isdir(real):
        return {'ok': False, 'msg': '账号目录不存在'}
    has_data = (os.path.isdir(os.path.join(real, 'tdata'))
                or glob.glob(os.path.join(real, '*.session'))
                or tg_tool._account_jsons(real))
    if not has_data:
        return {'ok': False, 'msg': '该目录不含账号数据(tdata/session/json),拒绝删除'}
    # 统计规模(供日志)
    total_size, total_files = 0, 0
    for r_, _d, f_ in os.walk(real):
        for fn in f_:
            try:
                total_size += os.path.getsize(os.path.join(r_, fn))
                total_files += 1
            except OSError:
                pass
    # 在线账号先断开(session 占用会让 rmtree 失败)
    eng = init_engine()
    try:
        fut = eng.disconnect(name)
        await asyncio.wait_for(asyncio.wrap_future(fut), 30)
    except Exception:
        pass
    try:
        shutil.rmtree(real)
    except OSError as e:
        return {'ok': False, 'msg': f'删除失败: {e}(若该号的客户端/资源管理器开着,请先关闭)'}
    _scrub_account_meta(name)
    size_mb = total_size / 1048576
    _emit({'type': 'log',
           'line': f'[账号] 已删除文件夹: {real} (共 {total_files} 个文件, {size_mb:.1f} MB)'})
    return {'ok': True, 'msg': name, 'deleted_path': real,
            'files': total_files, 'size_mb': round(size_mb, 1)}


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


# ---------- Telegram 官方 caBLE passkey QR 格式(对照 tdesktop webauthn/cable_core.cpp) ----------
CABLE_TUNNEL_DOMAINS = ["cable.ua5v.com", "cable.auth.com"]


def _bytes_to_digits(data: bytes) -> str:
    """BytesToDigits: 每 7 字节按小端转固定宽度十进制数(前导零),对应官方实现。"""
    widths = [0, 3, 5, 8, 10, 13, 15, 17]
    out = []
    i = 0
    n = len(data)
    while i < n:
        take = min(7, n - i)
        value = 0
        for j in range(take):
            value |= data[i + j] << (8 * j)
        out.append(str(value).zfill(widths[take]))
        i += take
    return ''.join(out)


def _make_cable_qr_uri():
    """生成 caBLE makeCredential QR: FIDO:/ + digits(CBOR(cable 参数))。"""
    import secrets as _sec
    import time
    import cbor2
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    priv = ec.generate_private_key(ec.SECP256R1())
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint)
    secret = _sec.token_bytes(16)
    cbor_map = {
        0: pub_bytes,              # identity 公钥(压缩 X9.62, 33 字节)
        1: secret,                 # 16 字节随机 secret
        2: len(CABLE_TUNNEL_DOMAINS),  # tunnel 域名数量 = 2
        3: int(time.time()),       # 时间戳
        4: False,                  # 保留布尔
        5: b'mc',                  # makeCredential
    }
    cbor_bytes = cbor2.dumps(cbor_map)
    return 'FIDO:/' + _bytes_to_digits(cbor_bytes)


def qr_matrix_to_png(matrix):
    """qrcode 布尔矩阵 -> 8 位灰度 PNG bytes(纯 zlib/struct, 不依赖 Pillow)。"""
    import struct
    import zlib

    def chunk(tag, payload):
        body = tag + payload
        return (struct.pack('>I', len(payload)) + body
                + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF))

    h = len(matrix)
    w = len(matrix[0]) if h else 0
    raw = b''.join(b'\x00' + bytes(0 if c else 255 for c in row) for row in matrix)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))

@app.post('/api/passkeys/init')
async def init_passkey():
    import asyncio
    import time as _time
    eng = init_engine()
    ok, data = await _call(eng.init_passkey_registration)
    if not ok:
        return {'ok': False, 'msg': str(data)}
    try:
        opts = cable.parse_public_key_options(data)
        request = {
            'clientDataHash': opts['clientDataHash'],
            'rpId': opts['rpId'],
            'rpName': opts['rpName'],
            'userId': opts['userId'],
            'userName': opts['userName'],
            'userDisplayName': opts['userDisplayName'],
            'algorithms': opts['algorithms'],
        }
        qr_key = cable.QRKey()
        qr_text = cable.encode_qr_contents(qr_key, True, int(_time.time()))
        client_data_json = opts['clientDataJson']

        async def _run():
            try:
                def _on_state(s):
                    # 心跳状态(wait:已等待秒数)转成进度条,其余原样透传
                    if s.startswith('wait:'):
                        try:
                            elapsed = int(s[5:])
                        except ValueError:
                            return
                        _emit({'type': 'progress', 'done': elapsed,
                               'total': 300, 'label': '通行密钥: 等待手机扫码(5分钟内有效)'})
                        return
                    _emit({'type': 'state', 'status': f'passkey_{s}'})

                result = await cable.register_via_cable(
                    request, qr_key=qr_key, timeout_s=300,
                    on_state=_on_state)
                cred_id = cable.b64url(result['credentialId'])
                attestation = cable.make_attestation_none(result['authData'])
                ok2, r2 = await _call(eng.register_passkey,
                                      cred_id, cred_id, client_data_json, attestation)
                _emit({'type': 'state', 'status': 'passkey_done',
                       'data': {'ok': ok2, 'msg': '注册成功' if ok2 else str(r2)}})
            except Exception as e:
                _emit({'type': 'state', 'status': 'passkey_error', 'data': str(e)})

        asyncio.create_task(_run())
        # 生成二维码图片(纯 zlib PNG 编码,避免为二维码引入整套 Pillow 约 13MB)
        import base64
        import qrcode as _qrcode
        qr = _qrcode.QRCode(border=2)
        qr.add_data(qr_text)
        qr.make(fit=True)
        img_b64 = base64.b64encode(qr_matrix_to_png(qr.get_matrix())).decode('ascii')
        return {'ok': True, 'qr': qr_text, 'img': img_b64}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


@app.post('/api/passkeys/register')
async def register_passkey(body: dict):
    import base64
    eng = init_engine()
    cred_id = body.get('id', '')
    raw_id = body.get('raw_id', '')
    client_data = body.get('client_data', '')
    attestation_b64 = body.get('attestation', '')
    try:
        attestation_data = base64.b64decode(attestation_b64)
    except Exception:
        return {'ok': False, 'msg': 'attestation 数据无效'}
    ok, data = await _call(eng.register_passkey, cred_id, raw_id, client_data, attestation_data)
    return {'ok': ok, 'msg': '注册成功' if ok else str(data)}


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
    ok, data = await _call(eng.verify_email, body.get('code', ''), body.get('email', ''))
    return {'ok': ok, 'msg': data}


@app.post('/api/email/get')
async def get_email(body: dict):
    """读取账号本地记录的已绑定邮箱(绑定成功时持久化在账号 json 的 login_email)。"""
    path = _ensure_in_root(body.get('path', ''))
    email = ''
    try:
        js = glob.glob(os.path.join(path, '*.json'))
        js = [f for f in js if tg_tool._is_account_json(f)]
        if js:
            email = str(json.load(open(js[0], encoding='utf-8')).get('login_email') or '')
    except Exception:
        pass
    return {'ok': True, 'email': email}


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
    year = body.get('year')
    year = _as_int(year) if year not in (None, '', 0) else None
    ok, data = await _call(eng.update_birthday,
                           _as_int(body.get('day', 0)), _as_int(body.get('month', 0)), year)
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


@app.post('/api/groups/rename')
async def rename_group(body: dict):
    old = (body.get('old') or '').strip()
    new = (body.get('new') or '').strip()
    groups = _load_groups()
    if not new or old not in groups:
        return {'ok': False, 'msg': '原分组不存在或新名称无效'}
    if new != old and new in groups:
        return {'ok': False, 'msg': '新分组名已存在'}
    # 重命名键并保持原顺序(成员不变)
    groups = {(new if k == old else k): v for k, v in groups.items()}
    _save_groups(groups)
    return {'ok': True, 'groups': groups}


@app.post('/api/groups/reorder')
async def reorder_groups(body: dict):
    """按给定顺序重排分组(dict 键序即持久化顺序)。"""
    order = body.get('order') or []
    groups = _load_groups()
    new = {k: groups[k] for k in order if k in groups}
    for k in groups:
        if k not in new:
            new[k] = groups[k]
    _save_groups(new)
    return {'ok': True, 'groups': new}


@app.post('/api/groups/move')
async def move_account(body: dict):
    """toggle 分组: 单账号可多分组。group='ungrouped' 表示移出所有组。"""
    name = body.get('name', '')
    group = body.get('group', '')
    groups = _load_groups()
    if group == 'ungrouped':
        for g in groups:
            if name in groups[g]:
                groups[g].remove(name)
    elif group:
        if name in groups.get(group, []):
            groups[group].remove(name)
        else:
            groups.setdefault(group, []).append(name)
    _save_groups(groups)
    return {'ok': True, 'groups': groups}


# ---------- tdata 转换 ----------
@app.post('/api/convert-to-tdata')
async def convert_to_tdata(body: dict):
    """将 session+json 转换为账号目录内的 Telegram Desktop tdata。"""
    path = _ensure_in_root(body.get('path', ''))
    eng = init_engine()
    fut = eng.convert_to_tdata(path)
    try:
        target = await asyncio.wait_for(asyncio.wrap_future(fut), 180)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    return {'ok': True, 'path': target}


@app.post('/api/convert-tdata')
async def convert_tdata(body: dict):
    eng = init_engine()
    path = _ensure_in_root(body.get('path', ''))
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
    if sess:
        # 仅 session: json 在首次连接时自愈补建(make_json_from_session)
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
    name = _clean_name(body.get('name', '账号'))
    if not b64:
        return {'ok': False, 'msg': '缺少数据'}
    try:
        zip_bytes = base64.b64decode(b64)
    except Exception:
        return {'ok': False, 'msg': '数据无效'}
    if len(zip_bytes) > 1024 * 1024 * 1024:
        return {'ok': False, 'msg': '压缩包过大'}
    tmp = tempfile.mkdtemp(prefix='tgimport_')
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            infos = zf.infolist()
            if len(infos) > 10000:
                return {'ok': False, 'msg': '压缩包条目过多'}
            total = sum(i.file_size for i in infos)
            if total > 1024 * 1024 * 1024:
                return {'ok': False, 'msg': '解压总大小超限'}
            tmp_real = os.path.realpath(tmp)
            for info in infos:
                target = os.path.realpath(os.path.join(tmp, info.filename))
                try:
                    if os.path.commonpath([target, tmp_real]) != tmp_real:
                        return {'ok': False, 'msg': '压缩包路径越界'}
                except ValueError:
                    return {'ok': False, 'msg': '压缩包路径越界'}
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
        # 自动放置客户端: 账号根目录有 Telegram.exe 就复制一份进新账号文件夹,
        # 让「启动客户端」开箱即用
        exe_src = os.path.join(ROOT, 'Telegram.exe')
        exe_dst = os.path.join(target, 'Telegram.exe')
        msg = f'已导入 {os.path.basename(target)}'
        if kind == 'session':
            msg += '(仅 session,凭据 json 将在首次连接时自动补建)'
        if os.path.isfile(exe_src) and not os.path.isfile(exe_dst):
            try:
                shutil.copy2(exe_src, exe_dst)
                msg += ',已自动放置 Telegram.exe'
            except OSError:
                pass
        return {'ok': True, 'msg': msg}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- 设置 ----------
SETTINGS_FILE = os.path.join(tg_tool.SCRIPT_DIR, 'settings.json')

DEFAULT_SETTINGS = {
    'pack_naming': '{name}_账号包',
    'pack_password': '',
    'theme_seed': '#009688',
    'theme_bg': '#F7FAF9',
    'theme_dark': '#FFFFFF',
    'theme_topbar': '#00796B',
    'theme_mode': 'light',
    'proxy_mode': 'none',
    'proxy_scheme': 'socks5',
    'proxy_host': '',
    'proxy_port': '',
    'card_open': {},
    'card_order': '基本信息,聊天,安全,删除,转换,其他设置',  # 中栏功能区顺序(逗号分隔)
    'recv_on': False,               # 消息接收开关(连接后自动恢复)
    'recv_exclude_channels': True,  # 默认排除所有频道
    'recv_exclude_groups': False,
    'recv_exclude_bots': False,
    'join_links': [],               # 要加入的群/频道 [{name:备注,link,type:'group'|'channel'}]
    'log_level': 'info',            # info=常规 / debug=含蓝牙原始广播等诊断日志
    'rename_quick': ['display', 'username', 'phone', 'uid'],  # 重命名弹窗快捷项
    'rename_prefix': '',            # 重命名快捷项自定义前缀
    'email_presets': [],            # 预选邮箱列表(绑定登录邮箱时一键填入)
    'cur_group': 'all',             # 记忆上次所在分组
}


def _load_settings():
    try:
        if os.path.isfile(SETTINGS_FILE):
            s = json.load(open(SETTINGS_FILE, encoding='utf-8'))
            if isinstance(s, dict):
                merged = dict(DEFAULT_SETTINGS)
                merged.update({k: v for k, v in s.items() if k in DEFAULT_SETTINGS})
                # 兼容旧的 proxy dict 字段
                p = s.get('proxy')
                if isinstance(p, dict):
                    merged['proxy_mode'] = p.get('mode', 'none')
                    merged['proxy_scheme'] = p.get('scheme', 'socks5')
                    merged['proxy_host'] = str(p.get('host', '') or '')
                    merged['proxy_port'] = str(p.get('port', '') or '')
                # card_order 自动补新增卡片(老 settings 缺「转换」会让新功能卡不显示)
                order = merged.get('card_order')
                if isinstance(order, str):
                    default_order = DEFAULT_SETTINGS['card_order'].split(',')
                    have = [x.strip() for x in order.split(',') if x.strip()]
                    for c in default_order:
                        if c not in have:
                            have.append(c)
                    merged['card_order'] = ','.join(have)
                # 兼容旧 join_links 字符串(每行一个) → 结构化条目
                jl = merged.get('join_links')
                if isinstance(jl, str):
                    merged['join_links'] = [
                        {'name': '', 'link': ln.strip(), 'type': 'group'}
                        for ln in jl.splitlines() if ln.strip()]
                elif not isinstance(jl, list):
                    merged['join_links'] = []
                else:
                    merged['join_links'] = [
                        {'name': str(e.get('name', '') or ''),
                         'link': str(e.get('link', '') or ''),
                         'type': 'channel' if e.get('type') == 'channel' else 'group'}
                        for e in jl if isinstance(e, dict)]
                return merged
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(s):
    try:
        raw = {}
        if os.path.isfile(SETTINGS_FILE):
            try:
                raw = json.load(open(SETTINGS_FILE, encoding='utf-8'))
            except Exception:
                raw = {}
        for k in DEFAULT_SETTINGS:
            raw[k] = s.get(k, DEFAULT_SETTINGS[k])
        # 同步 proxy dict 字段(tg_tool.load_proxy_cfg 读取)
        port = s.get('proxy_port')
        raw['proxy'] = {
            'mode': s.get('proxy_mode', 'none'),
            'scheme': s.get('proxy_scheme', 'socks5'),
            'host': s.get('proxy_host', ''),
            'port': int(port) if str(port).isdigit() else 0,
        }
        json.dump(raw, open(SETTINGS_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass


@app.get('/api/settings')
async def get_settings():
    return _load_settings()


@app.post('/api/settings')
async def set_settings(body: dict):
    s = _load_settings()
    for k in DEFAULT_SETTINGS:
        if k in body:
            s[k] = body[k]
    _save_settings(s)
    # 代理配置变更后重新加载(供后续连接使用)
    try:
        tg_tool.load_proxy_cfg()
    except Exception:
        pass
    return s


# ---------- 打包账号(仅 tdata + session + json + 2fa.txt,zip + 剪贴板) ----------
def _copy_file_to_clipboard(path):
    """复制文件到剪贴板(CF_HDROP),纯 ctypes 无 shell 注入。"""
    import ctypes
    from ctypes import wintypes
    try:
        CF_HDROP = 15
        GMEM_MOVEABLE = 0x0002
        GMEM_ZEROINIT = 0x0040

        class DROPFILES(ctypes.Structure):
            _fields_ = [('pFiles', wintypes.DWORD),
                        ('pt', wintypes.POINT),
                        ('fNC', wintypes.BOOL),
                        ('fWide', wintypes.BOOL)]

        df = DROPFILES()
        df.pFiles = ctypes.sizeof(DROPFILES)
        df.fWide = True
        head = ctypes.string_at(ctypes.addressof(df), ctypes.sizeof(DROPFILES))
        payload = head + path.encode('utf-16-le') + b'\x00\x00'

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(payload))
        ptr = kernel32.GlobalLock(hmem)
        ctypes.memmove(ptr, payload, len(payload))
        kernel32.GlobalUnlock(hmem)
        user32.OpenClipboard(None)
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_HDROP, hmem)
        user32.CloseClipboard()
        return True
    except Exception:
        return False


def _collect_account_files(src, dst):
    """把账号目录里需要打包的文件收集到 dst。"""
    for entry in os.listdir(src):
        full = os.path.join(src, entry)
        low = entry.lower()
        if low == 'tdata':
            shutil.copytree(full, os.path.join(dst, entry), dirs_exist_ok=True)
        elif entry.endswith('.session') or entry.endswith('.session-journal'):
            shutil.copy2(full, os.path.join(dst, entry))
        elif entry.endswith('.json') and tg_tool._is_account_json(full):
            shutil.copy2(full, os.path.join(dst, entry))
        elif low == '2fa.txt':
            shutil.copy2(full, os.path.join(dst, entry))


@app.post('/api/pack')
async def pack_account(body: dict):
    import datetime
    import zipfile
    path = _ensure_in_root(body.get('path', ''))
    name = _clean_name(body.get('name', ''))
    if not os.path.isdir(path):
        return {'ok': False, 'msg': '账号路径无效'}
    s = _load_settings()
    password = str(s.get('pack_password') or '')
    naming = s.get('pack_naming', '{name}_账号包')
    try:
        base = naming.format(name=name, date=datetime.date.today().strftime('%Y%m%d'))
    except Exception:
        base = f'{name}_账号包'
    base = _clean_name(base)
    zip_path = os.path.join(ROOT, f'{base}.zip')

    if password:
        # 有密码: 7z AES-256 加密
        seven = shutil.which('7z') or shutil.which('7za')
        if not seven:
            return {'ok': False, 'msg': '未找到 7-Zip，无法生成加密账号包'}
        staging = os.path.join(ROOT, f'.{base}_pack_staging')
        try:
            if os.path.exists(staging):
                shutil.rmtree(staging, ignore_errors=True)
            os.makedirs(staging)
            _collect_account_files(path, staging)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            proc = subprocess.run(
                [seven, 'a', '-tzip', '-mem=AES256', f'-p{password}', '-y', zip_path, '.'],
                cwd=staging, capture_output=True, timeout=120,
            )
            if proc.returncode != 0 or not os.path.isfile(zip_path):
                raise RuntimeError((proc.stderr or proc.stdout).decode(errors='replace')[-200:])
        except Exception as e:
            try:
                if os.path.isfile(zip_path):
                    os.remove(zip_path)
            except OSError:
                pass
            return {'ok': False, 'msg': f'加密打包失败: {str(e)[:200]}'}
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        clip = _copy_file_to_clipboard(zip_path)
        return {'ok': True, 'msg': f'已加密打包{"并复制到剪贴板" if clip else ""}：{os.path.basename(zip_path)}'}

    # 无密码: zipfile 明文
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for entry in os.listdir(path):
                full = os.path.join(path, entry)
                low = entry.lower()
                if low == 'tdata':
                    for r2, dirs, files in os.walk(full):
                        for f in files:
                            fp = os.path.join(r2, f)
                            zf.write(fp, os.path.relpath(fp, path))
                elif entry.endswith('.session') or entry.endswith('.session-journal'):
                    zf.write(full, entry)
                elif entry.endswith('.json') and tg_tool._is_account_json(full):
                    zf.write(full, entry)
                elif low == '2fa.txt':
                    zf.write(full, entry)
    except Exception as e:
        return {'ok': False, 'msg': f'打包失败: {str(e)[:200]}'}
    clip = _copy_file_to_clipboard(zip_path)
    return {'ok': True, 'msg': f'已打包{"并复制到剪贴板" if clip else ""}：{os.path.basename(zip_path)}'}


# ---------- 静态前端 ----------
_index_cache = None          # index.html 缓存(避免每次请求读盘)


@app.get('/')
async def index(token: str = ''):
    from fastapi.responses import HTMLResponse
    # 首页含 token 注入,必须带 query token 才返回(壳和浏览器模式都带 ?token=);
    # 否则本机任意进程扫端口即可白拿 token 调用全部 API
    if token != TOKEN:
        return HTMLResponse('未授权', status_code=401)
    global _index_cache
    if _index_cache is None:
        index_path = os.path.join(DIST, 'index.html')
        if not os.path.isfile(index_path):
            return HTMLResponse('未找到前端资源', status_code=404)
        _index_cache = open(index_path, encoding='utf-8').read()
    inject = f'<script>window.__TG_TOKEN__={json.dumps(TOKEN)}</script>'
    html = _index_cache.replace('</head>', inject + '</head>')
    return HTMLResponse(html, headers={'Cache-Control': 'no-cache, no-store, must-revalidate'})


class _NoCacheStatic(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp


if os.path.isdir(DIST):
    app.mount('/assets', _NoCacheStatic(directory=os.path.join(DIST, 'assets')), name='assets')


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
    return port, TOKEN


if __name__ == '__main__':
    p = _pick_port()
    print(f'后端启动于 http://127.0.0.1:{p}/?token={TOKEN}')
    uvicorn.run(app, host='127.0.0.1', port=p, log_level='warning')
