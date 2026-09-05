"""TG工具箱 GUI 引擎层 (核心部分)
====================================================
职责: 在后台线程里跑 telethon 事件循环,把 CLI 已验证的
删除联系人/删对话逻辑以"可取消、带进度回调"的形式暴露给 GUI。

线程模型:
  GUI(Tk mainloop,主线程)
    └─ worker 线程: 每个线程一个独立的 asyncio 循环
       - Engine.start(): 启动线程+循环,常驻直到 Engine.stop()
       - 账号连接/断开/任务全部通过 loop.call_soon_threadsafe 提交

停止控制(防风控安全):
  - stop() 设置 self._cancel = True,任务在"每个动作之间"检查
  - 正在执行的 API 请求不中断(避免半途废 session),
    当前动作完成后停止 —— 与 CLI 的 Ctrl+C 等价但更温和
"""
import asyncio
import json
import os
import random
import threading
import time

import tg_tool
from tg_tool import (
    T, LOG_DIR, BACKUP_DIR, SCRIPT_DIR,
    _account_jsons, _is_tdata_only, _convert_tdata,
    find_cfg, make_client,
)

# GUI 自己的排除列表(与 CLI 的工具目录/非账号文件夹对齐)
EXCLUDE_DIRS = {'工具箱', 'logs', 'backups', 'modules', 'tupdates', '空白Telegram',
                '__pycache__', '_internal'}

def _ensure_telethon():
    """惰性导入 telethon(首次任务时加载,省 GUI 启动约 2s)。"""
    if 'DeleteContactsRequest' in globals():
        return
    from telethon import functions
    from telethon.errors import FloodWaitError
    from telethon.tl.functions.contacts import DeleteContactsRequest, BlockRequest
    from telethon.tl.functions.channels import LeaveChannelRequest
    from telethon.tl.functions.messages import DeleteChatUserRequest
    globals()['functions'] = functions
    globals()['FloodWaitError'] = FloodWaitError
    globals()['DeleteContactsRequest'] = DeleteContactsRequest
    globals()['BlockRequest'] = BlockRequest
    globals()['LeaveChannelRequest'] = LeaveChannelRequest
    globals()['DeleteChatUserRequest'] = DeleteChatUserRequest


# ============ 账号发现(不转换 tdata —— 转换是写操作,GUI 里单独触发) ============

def scan_accounts(root):
    """扫描 root 下的账号。返回 [(名字, 路径, 状态), ...] 状态:
    'ok'=json+session | 'tdata'=仅tdata可转换 | 'session'=有session无json | 'empty'=无法操作
    """
    out = []
    try:
        subs = sorted(os.listdir(root))
    except Exception:
        return out
    for sub in subs:
        d = os.path.join(root, sub)
        if not os.path.isdir(d) or sub in EXCLUDE_DIRS:
            continue
        if _account_jsons(d):
            import glob as _g
            has_sess = bool(_g.glob(os.path.join(d, '*.session')))
            cfg = json.load(open(_account_jsons(d)[0], encoding='utf-8'))
            if cfg.get('session_str') or has_sess:
                out.append((sub, d, 'ok'))
            else:
                out.append((sub, d, 'empty'))
        elif _is_tdata_only(d):
            out.append((sub, d, 'tdata'))
        else:
            import glob as _g
            if _g.glob(os.path.join(d, '*.session')):
                out.append((sub, d, 'session'))
            # 其余(纯 Telegram.exe/tupdates 等杂物文件夹)不算账号
    return out


def account_info(account_dir):
    """读 json 摘要。返回 dict(name, phone, uid, json_path)。"""
    js = _account_jsons(account_dir)
    if not js:
        return {}
    try:
        cfg = json.load(open(js[0], encoding='utf-8'))
    except Exception:
        cfg = {}
    return {
        'name': os.path.basename(account_dir),
        'phone': cfg.get('phone') or '',
        'uid': cfg.get('user_id') or '',
        'json_path': js[0],
    }


# ============ 引擎 ============

class Engine:
    """一个 GUI 会话对应一个 Engine。持有当前账号的 client。

    用法(GUI 侧):
      eng = Engine(on_log, on_progress, on_state)
      eng.start()
      eng.connect(account_dir)     -> 等回调 on_state('connected', info)
      eng.delete_contacts()        -> 回调进度,直到 on_state('done', ...)
      eng.stop_task()              -> 温和取消当前任务
      eng.shutdown()               -> 断开+结束线程
    回调全部在 GUI 线程执行(经 root.after 调度,见 ui 层)。
    """

    def __init__(self, on_log=None, on_progress=None, on_state=None, on_message=None, gui_schedule=None):
        self.on_log = on_log or (lambda msg: None)
        self.on_progress = on_progress or (lambda done, total, label: None)
        self.on_state = on_state or (lambda st, data: None)
        self.on_message = on_message or (lambda data: None)   # 新消息接收(聊天功能)
        self._gui_schedule = gui_schedule or (lambda fn: fn())   # 默认同步调
        self._loop = None
        self._thread = None
        self._client = None
        self._me = None
        self._account_dir = None
        # 连接池: 账号名 -> {'client','me','info'};支持多账号同时在线,秒切
        self._pool = {}
        self._recv_on = False       # 消息接收开关
        self._recv_rules = {'exclude_channels': True, 'exclude_groups': False,
                            'exclude_bots': False}
        # 已注册消息监听的 client 集合(引擎侧管理;
        # Telethon client 是 __slots__ 类,不能往实例上挂标记属性)
        self._recv_bound = set()
        self._cancel = threading.Event()
        self._task_running = False
        self._lock = threading.RLock()

    # ---------- 线程/循环 ----------

    def start(self):
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        # 等事件循环就绪(最多 5s),否则 connect 会拿到 None loop
        deadline = time.time() + 5
        while self._loop is None and time.time() < deadline:
            time.sleep(0.02)

    def _thread_main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def shutdown(self):
        """断开所有在线账号并结束线程。"""
        if self._loop is None:
            return
        async def _fin():
            for entry in list(self._pool.values()):
                try:
                    await entry['client'].disconnect()
                except Exception:
                    pass
            self._pool.clear()
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            self._me = None
        try:
            fut = asyncio.run_coroutine_threadsafe(_fin(), self._loop)
            fut.result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)

    def _submit(self, coro, timeout=None):
        """把协程提交到引擎线程;返回 concurrent.futures.Future。"""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # ---------- 工具 ----------

    def _log(self, msg):
        self._gui_schedule(lambda: self.on_log(msg))

    def _prog(self, done, total, label=''):
        self._gui_schedule(lambda: self.on_progress(done, total, label))

    def _state(self, st, data=None):
        self._gui_schedule(lambda: self.on_state(st, data))

    def _check_cancel(self):
        return self._cancel.is_set()

    async def _sleep(self, seconds):
        """可取消的 sleep: 分片睡,便于及时响应停止。"""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._check_cancel():
                return
            await asyncio.sleep(min(0.5, max(0.0, end - time.monotonic())))

    # ---------- 连接/断开 ----------

    def connect(self, account_dir):
        """连接账号(线程安全)。"""
        self._cancel.clear()
        fut = self._submit(self._do_connect(account_dir))
        return fut

    async def _do_connect(self, account_dir):
        with self._lock:
            name = os.path.basename(account_dir)
            # 已在线: 秒切到该账号,不重连
            if name in self._pool:
                entry = self._pool[name]
                self._client = entry['client']
                self._me = entry['me']
                self._account_dir = account_dir
                self._state('connected', entry['info'])
                return entry['info']
            self._account_dir = account_dir
            self._log(T('t050a', os.path.basename(account_dir)))
            # tdata-only 账号: 自动转换成 session 再连(登录态优先级
            # .session > json.session_str > tdata 转换,与 make_client 一致)
            if _is_tdata_only(account_dir):
                self._log(T('t159', name))
                loop = asyncio.get_event_loop()
                ok = await loop.run_in_executor(None, tg_tool._convert_tdata, account_dir)
                if not ok:
                    self._state('connect_fail', None)
                    return None
            try:
                cfg_path, cfg = find_cfg(account_dir)
                client = make_client(cfg_path, cfg)
            except SystemExit:
                # die() 会 raise SystemExit —— 引擎里转成失败状态
                self._state('connect_fail', None)
                return None
            except Exception as e:
                self._log(f'[!] {type(e).__name__}: {e}')
                self._state('connect_fail', None)
                return None
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    self._log(T('t048'))
                    await client.disconnect()
                    self._state('connect_fail', None)
                    return None
                me = await client.get_me()
            except Exception as e:
                self._log(f'[!] {type(e).__name__}: {e}')
                self._state('connect_fail', None)
                return None
            expect = cfg.get('user_id')
            if expect and str(me.id) != str(expect):
                self._log(T('t049', expect, me.id))
                await client.disconnect()
                self._state('connect_fail', None)
                return None
            self._client = client
            self._me = me
            info = {
                'name': os.path.basename(account_dir),
                'phone': cfg.get('phone') or me.phone or '',
                'uid': str(me.id),
                'first': me.first_name or '',
                'last': me.last_name or '',
            }
            self._pool[name] = {'client': client, 'me': me, 'info': info, 'dir': account_dir}
            self._log(T('t050', info['phone'], info['first'], info['last']).rstrip())
            self._state('connected', info)
            return info

    # ---------- 速度档 ----------

    def set_speed(self, idx):
        """idx: 1-5,同 CLI pick_speed 的档位。"""
        presets = tg_tool.SPEED_PRESETS
        if not (1 <= idx <= len(presets)):
            idx = 3
        name, rng, k = presets[idx - 1]
        with self._lock:
            tg_tool.DIALOG_DELAY = rng
            tg_tool.CONTACT_BATCH_DELAY = (round(5 * k, 1), round(10 * k, 1))
            tg_tool.CONTACT_ROUND_DELAY = (round(20 * k, 1), round(40 * k, 1))
        self._log(T('t053', name, rng[0], rng[1],
                    tg_tool.CONTACT_BATCH_DELAY[0], tg_tool.CONTACT_BATCH_DELAY[1],
                    tg_tool.CONTACT_ROUND_DELAY[0], tg_tool.CONTACT_ROUND_DELAY[1]))
        return name

    # ---------- 任务: 删联系人 ----------

    def delete_contacts(self, confirm_backup=True):
        return self._submit(self._do_delete_contacts())

    async def _do_delete_contacts(self):
        _ensure_telethon()
        if not self._client:
            self._state('done', '未连接账号')
            return
        self._cancel.clear()
        self._task_running = True
        self._state('task_start', '删除联系人')
        try:
            client, me = self._client, self._me
            res = await client(functions.contacts.GetContactsRequest(hash=0))
            all_users = [u for u in res.users if u.id != me.id]
            users = [u for u in all_users
                     if u.id not in tg_tool.USER_WHITELIST and not tg_tool.is_official(u)]
            wl = [u for u in all_users if u.id in tg_tool.USER_WHITELIST]
            official = [u for u in all_users if tg_tool.is_official(u)]
            self._log(T('t066', len(all_users), len(wl), len(users)))
            if official:
                self._log(T('t152', len(official)))
            for u in wl:
                self._log(T('t067', u.first_name or '', u.last_name or '', u.id).rstrip())
            if not users:
                self._log(T('t068'))
                self._state('done', '没有可删除的联系人')
                return

            # 备份(GUI 无确认弹窗逻辑,永远备份)
            ts = time.strftime('%Y%m%d-%H%M%S')
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                bfile = os.path.join(BACKUP_DIR, f'contacts-backup-{ts}.json')
            except Exception:
                bfile = os.path.join(SCRIPT_DIR, f'contacts-backup-{ts}.json')
            json.dump([{'id': u.id, 'first_name': u.first_name, 'last_name': u.last_name or '',
                        'username': u.username or '', 'phone': u.phone or ''} for u in users],
                      open(bfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            self._log(T('t071', len(users), os.path.basename(bfile)))

            total = 0
            for rnd in range(3):
                res = await client(functions.contacts.GetContactsRequest(hash=0))
                ids = [u.id for u in res.users
                       if u.id != me.id and u.id not in tg_tool.USER_WHITELIST]
                if not ids:
                    break
                self._log(T('t072', rnd + 1, len(ids)))
                batches = (len(ids) + tg_tool.CONTACT_BATCH - 1) // tg_tool.CONTACT_BATCH
                for bi in range(0, len(ids), tg_tool.CONTACT_BATCH):
                    if self._check_cancel():
                        self._log('[!] 任务已停止')
                        self._state('done', f'已停止(删除 {total} 个)')
                        return
                    batch = ids[bi:bi + tg_tool.CONTACT_BATCH]
                    ok = False
                    for attempt in range(3):
                        try:
                            await client(DeleteContactsRequest(id=batch))
                            total += len(batch)
                            ok = True
                            break
                        except FloodWaitError as e:
                            w = min(e.seconds, 600)
                            self._log(T('t073', w))
                            await self._sleep(w + 1)
                            if self._check_cancel():
                                break
                        except Exception as e:
                            if attempt == 2:
                                self._log(T('t074', e))
                            await self._sleep(3)
                    if ok:
                        bnum = bi // tg_tool.CONTACT_BATCH + 1
                        self._prog(total, len(ids), T('t075a'))
                        self._log(T('t075', tg_tool.pbar(bnum, batches), total, len(ids)))
                    if bi + tg_tool.CONTACT_BATCH < len(ids) and not self._check_cancel():
                        w = random.uniform(*tg_tool.CONTACT_BATCH_DELAY)
                        self._log(T('t076', w))
                        await self._sleep(w)
                if rnd < 2 and not self._check_cancel():
                    r = await client(functions.contacts.GetContactsRequest(hash=0))
                    remain = [u.id for u in r.users
                              if u.id != me.id and u.id not in tg_tool.USER_WHITELIST
                              and not tg_tool.is_official(u)]
                    if remain:
                        w = random.uniform(*tg_tool.CONTACT_ROUND_DELAY)
                        self._log(T('t077', w))
                        await self._sleep(w)
                    else:
                        break

            res2 = await client(functions.contacts.GetContactsRequest(hash=0))
            left = [u for u in res2.users
                    if u.id != me.id and u.id not in tg_tool.USER_WHITELIST
                    and not tg_tool.is_official(u)]
            kept = [u for u in res2.users if u.id in tg_tool.USER_WHITELIST]
            self._log(T('t078', total, len(left), len(kept)))
            self._state('done', f'共删除 {total} 个,残留 {len(left)} 个')
        except Exception as e:
            self._log(f'[!] 任务出错: {type(e).__name__}: {e}')
            self._state('done', f'出错: {e}')
        finally:
            self._task_running = False

    # ---------- 任务: 删对话 ----------

    def delete_dialogs(self, choice):
        """choice: 'privates' / 'groups' / 'all'"""
        return self._submit(self._do_delete_dialogs(choice))

    async def _do_delete_dialogs(self, choice):
        _ensure_telethon()
        if not self._client:
            self._state('done', '未连接账号')
            return
        self._cancel.clear()
        self._task_running = True
        label = {'users': '删除私聊', 'bots': '拉黑机器人', 'groups': '退出群组/频道',
                 'privates': '删除全部私聊', 'all': '全部执行'}.get(choice, choice)
        self._state('task_start', label)
        try:
            client, me = self._client, self._me
            self._log(T('t079'))
            dialogs = await client.get_dialogs(limit=None)
            try:
                archived = await client.get_dialogs(limit=None, archived=True)
                dialogs += archived
                if archived:
                    self._log(T('t080', len(archived)))
            except Exception as e:
                self._log(T('t081', e))
            self._log(T('t082', len(dialogs)))

            users, bots, deleted, groups, keep_users, keep_groups = [], [], [], [], [], []
            official_kept = 0
            for d in dialogs:
                e = d.entity
                eid = getattr(e, 'id', None)
                if eid == me.id:
                    keep_users.append(d)
                elif eid in tg_tool.USER_WHITELIST:
                    keep_users.append(d)
                elif d.is_user:
                    if tg_tool.is_official(e):
                        keep_users.append(d)   # 官方/认证账号,永不删
                        official_kept += 1
                    elif getattr(e, 'bot', False):
                        bots.append(d)
                    elif getattr(e, 'deleted', False) or getattr(e, 'first_name', None) == 'Deleted Account':
                        deleted.append(d)
                    else:
                        users.append(d)
                elif d.is_group or d.is_channel:
                    if eid in tg_tool.GROUP_WHITELIST:
                        keep_groups.append(d)
                    elif tg_tool.is_official(e):
                        keep_groups.append(d)  # 官方/认证频道,永不退
                        official_kept += 1
                    else:
                        groups.append(d)

            if official_kept:
                self._log(T('t152', official_kept))
            self._log(T('t083', len(dialogs), len(users), len(deleted), len(bots),
                        len(groups), len(keep_users) + len(keep_groups)))

            all_privates = users + deleted + bots

            async def del_user(client, d):
                await client.delete_dialog(d.entity, revoke=True)

            async def block_bot(client, d):
                await client.delete_dialog(d.entity, revoke=True)
                await client(BlockRequest(id=d.entity))

            if choice == 'users':
                await self._backup_dialogs(users + deleted, 'privates')
                await self._run_dialog_action(client, deleted, T('t107'), del_user)
                await self._run_dialog_action(client, users, T('t109'), del_user)
            elif choice == 'bots':
                await self._backup_dialogs(bots, 'bots')
                await self._run_dialog_action(client, bots, T('t108'), block_bot)
            elif choice in ('privates', 'all'):
                await self._backup_dialogs(all_privates, 'privates')
                await self._run_dialog_action(client, deleted, T('t107'), del_user)
                await self._run_dialog_action(client, bots, T('t108'), block_bot)
                await self._run_dialog_action(client, users, T('t109'), del_user)
            if self._check_cancel():
                self._state('done', '已停止')
                return
            if choice in ('groups', 'all'):
                await self._do_groups(client, groups)
            self._log(T('t110'))
            self._state('done', '对话清理完成')
        except Exception as e:
            self._log(f'[!] 任务出错: {type(e).__name__}: {e}')
            self._state('done', f'出错: {e}')
        finally:
            self._task_running = False

    async def _backup_dialogs(self, items, tag):
        ts = time.strftime('%Y%m%d-%H%M%S')
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            fname = os.path.join(BACKUP_DIR, f'dialogs-backup-{tag}-{ts}.json')
        except Exception:
            fname = os.path.join(SCRIPT_DIR, f'dialogs-backup-{tag}-{ts}.json')
        rows = [{'id': getattr(d.entity, 'id', None), 'name': tg_tool._dlbl(d)} for d in items]
        json.dump(rows, open(fname, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        self._log(T('t084', len(rows), os.path.basename(fname)))

    async def _run_dialog_action(self, client, items, desc, fn):
        _ensure_telethon()
        if not items:
            self._log(T('t085', desc))
            return
        total = len(items)
        done = 0
        for i, d in enumerate(items, 1):
            if self._check_cancel():
                self._log('[!] 任务已停止')
                return
            try:
                await fn(client, d)
                done += 1
                self._prog(done, total, desc)
                self._log(f'  {desc} {tg_tool.pbar(i, total)}  {tg_tool._dlbl(d)}')
            except FloodWaitError as e:
                w = min(e.seconds, 300)
                self._log(T('t086', w))
                await self._sleep(w + 1)
            except Exception as e:
                self._log(T('t087', desc, i, total, tg_tool._dlbl(d), e))
            await self._sleep(random.uniform(*tg_tool.DIALOG_DELAY))
        self._log(T('t088', desc, done, total))

    async def _do_groups(self, client, groups):
        _ensure_telethon()
        await self._backup_dialogs(groups, 'groups')
        total = len(groups)
        done = 0
        for i, d in enumerate(groups, 1):
            if self._check_cancel():
                self._log('[!] 任务已停止')
                return
            try:
                if d.is_channel:
                    await client(LeaveChannelRequest(channel=d.entity))
                else:
                    await client(DeleteChatUserRequest(chat_id=d.entity.id, user_id='me'))
                done += 1
                self._prog(done, total, T('t091a', ''))
                self._log(T('t101', tg_tool.pbar(i, total), tg_tool._dlbl(d)))
            except FloodWaitError as e:
                w = min(e.seconds, 300)
                self._log(T('t102', w))
                await self._sleep(w + 1)
            except Exception as e:
                self._log(T('t103', _dlbl_safe(d), e))
                try:
                    await client.delete_dialog(d.entity, revoke=True)
                    done += 1
                    self._log(T('t104', tg_tool.pbar(i, total), _dlbl_safe(d)))
                except Exception as e2:
                    self._log(T('t105', _dlbl_safe(d), e2))
            await self._sleep(random.uniform(*tg_tool.DIALOG_DELAY))
        self._log(T('t106', done, total))

    # ---------- 扫描(只读不删) / 辅助 ----------

    def scan_dialogs(self):
        """只扫描分类,不删。结果经 on_state('scan', data) 回调。"""
        return self._submit(self._do_scan_dialogs())

    async def _do_scan_dialogs(self):
        if not self._client:
            self._state('done', '未连接账号')
            return None
        try:
            client, me = self._client, self._me
            dialogs = await client.get_dialogs(limit=None)
            try:
                archived = await client.get_dialogs(limit=None, archived=True)
                dialogs += archived
            except Exception:
                pass
            users, bots, deleted, groups, keep_users, keep_groups = [], [], [], [], [], []
            for d in dialogs:
                e = d.entity
                eid = getattr(e, 'id', None)
                if eid == me.id or eid in tg_tool.USER_WHITELIST:
                    keep_users.append(d)
                elif d.is_user:
                    if tg_tool.is_official(e):
                        keep_users.append(d)   # 官方/认证账号,永不删
                    elif getattr(e, 'bot', False):
                        bots.append(d)
                    elif getattr(e, 'deleted', False) or getattr(e, 'first_name', None) == 'Deleted Account':
                        deleted.append(d)
                    else:
                        users.append(d)
                elif d.is_group or d.is_channel:
                    if eid in tg_tool.GROUP_WHITELIST:
                        keep_groups.append(d)
                    elif tg_tool.is_official(e):
                        keep_groups.append(d)  # 官方/认证频道,永不退
                    else:
                        groups.append(d)
            data = {
                'total': len(dialogs),
                'privates': len(users) + len(deleted) + len(bots),
                'groups': len(groups),
                'users': len(users), 'deleted': len(deleted), 'bots': len(bots),
                'keep_users': len(keep_users),
                'keep_groups': len(keep_groups),
                'keep': [tg_tool._dlbl(d) for d in keep_users + keep_groups],
            }
            self._log(T('t083', len(dialogs), len(users), len(deleted), len(bots),
                        len(groups), len(keep_users) + len(keep_groups)))
            self._state('scan', data)
            return data
        except Exception as e:
            self._log(f'[!] 扫描出错: {type(e).__name__}: {e}')
            self._state('done', f'扫描出错: {e}')
            return None

    def count_contacts(self, on_done=None):
        """统计联系人。成功经 on_done(True, data) 回调;失败 on_done(False, msg)。"""
        return self._submit(self._do_count_contacts(on_done))

    async def _do_count_contacts(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            client, me = self._client, self._me
            res = await client(functions.contacts.GetContactsRequest(hash=0))
            all_users = [u for u in res.users if u.id != me.id]
            deletable = [u for u in all_users
                         if u.id not in tg_tool.USER_WHITELIST and not tg_tool.is_official(u)]
            data = {'total': len(all_users), 'deletable': len(deletable),
                    'whitelist': len(all_users) - len(deletable)}
            self._log(T('t066', len(all_users), data['whitelist'], len(deletable)))
            self._state('contacts_scan', data)
            if on_done:
                self._gui_schedule(lambda d=data: on_done(True, d))
            return data
        except Exception as e:
            self._log(f'[!] 扫描出错: {type(e).__name__}: {e}')
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            else:
                self._state('done', f'扫描出错: {e}')
            return None

    def resolve_entity(self, s, on_done=None):
        """白名单添加用: 解析 ID/@用户名 -> 实体(需已连接)。
        成功经 on_done(True, entity) 回调;失败 on_done(False, msg)。"""
        return self._submit(self._do_resolve_entity(s, on_done))

    async def _do_resolve_entity(self, s, on_done=None):
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        s = (s or '').strip().lstrip('+')
        ent = None
        try:
            if s.isdigit():
                ent = await self._client.get_entity(int(s))
            elif s.startswith('@'):
                ent = await self._client.get_entity(s)
        except Exception:
            ent = None
        if on_done:
            if ent is not None:
                self._gui_schedule(lambda e=ent: on_done(True, e))
            else:
                self._gui_schedule(lambda: on_done(False, '未找到该用户/群组'))
        return ent

    def disconnect(self, name=None):
        """断开连接。name=None 断当前账号;name 指定池中账号则只断那个。"""
        return self._submit(self._do_disconnect(name))

    async def _do_disconnect(self, name=None):
        with self._lock:
            if name:
                entry = self._pool.pop(name, None)
                if entry:
                    try:
                        await entry['client'].disconnect()
                    except Exception:
                        pass
                    if self._client is entry['client']:
                        self._client = None
                        self._me = None
                        self._account_dir = None
                        # 池里还有其他在线账号: 自动切过去,保持有当前账号
                        for v in self._pool.values():
                            self._client = v['client']
                            self._me = v['me']
                            self._account_dir = v.get('dir')
                            self._log(T('t050b', v['info']['name']))
                            self._state('switched', v['info'])
                            break
                        if not self._pool:
                            self._state('disconnected', name)
                else:
                    self._log(f'[!] {name} 不在线')
                return None
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                # 从池中移除当前账号
                for k, v in list(self._pool.items()):
                    if v['client'] is self._client:
                        del self._pool[k]
                self._client = None
            self._me = None
            # 池里还有其他在线账号: 自动切过去,保持有当前账号
            for v in self._pool.values():
                self._client = v['client']
                self._me = v['me']
                self._account_dir = v.get('dir')
                self._log(T('t050b', v['info']['name']))
                self._state('switched', v['info'])
                break
            if not self._pool:
                self._state('disconnected', None)
        return None

    def switch(self, name):
        """切换当前账号到池中已在线的 name(秒切)。返回 info 或 None。"""
        return self._submit(self._do_switch(name))

    async def _do_switch(self, name):
        with self._lock:
            entry = self._pool.get(name)
            if not entry:
                self._log(f'[!] {name} 不在线')
                return None
            self._client = entry['client']
            self._me = entry['me']
            self._account_dir = entry.get('dir')
            self._log(T('t050b', name))
            self._state('switched', entry['info'])
            return entry['info']

    def online_accounts(self):
        """返回当前在线账号的 info 列表。"""
        return self._submit(self._do_online_accounts())

    async def _do_online_accounts(self):
        return [v['info'] for v in self._pool.values()]

    # ---------- 聊天: 消息接收 / 加群频道 ----------

    def set_recv(self, on, rules=None):
        """开/关消息接收;rules 覆盖过滤规则。对池内所有在线 client 生效。"""
        self._recv_on = bool(on)
        if rules is not None:
            self._recv_rules.update({k: bool(v) for k, v in rules.items()
                                     if k in ('exclude_channels', 'exclude_groups', 'exclude_bots')})
        return self._submit(self._do_set_recv())

    async def _do_set_recv(self):
        _ensure_telethon()
        from telethon import events
        bound = 0
        # 清理已下线 client 的标记
        self._recv_bound &= {entry['client'] for entry in self._pool.values()}
        for entry in self._pool.values():
            client = entry['client']
            is_bound = client in self._recv_bound
            try:
                if self._recv_on and not is_bound:
                    client.add_event_handler(self._on_new_message, events.NewMessage())
                    self._recv_bound.add(client)
                    bound += 1
                elif not self._recv_on and is_bound:
                    client.remove_event_handler(self._on_new_message, events.NewMessage())
                    self._recv_bound.discard(client)
            except Exception as e:
                self._log(f'[!] 消息接收注册失败: {type(e).__name__}: {e}')
        self._log(T('t153', '开启' if self._recv_on else '关闭',
                    len(self._pool), self._recv_rules_summary()))
        return bound

    def _recv_rules_summary(self):
        r = self._recv_rules
        parts = []
        if r.get('exclude_channels'):
            parts.append('排除频道')
        if r.get('exclude_groups'):
            parts.append('排除群组')
        if r.get('exclude_bots'):
            parts.append('排除机器人')
        return '、'.join(parts) if parts else '无排除'

    def _account_of(self, client):
        """反查消息所属的在线账号名。"""
        for entry in self._pool.values():
            if entry['client'] is client:
                return entry['info'].get('name', '?')
        return '?'

    async def _on_new_message(self, event):
        """NewMessage 处理: 过滤后经 on_message 上抛(仅收到的=未读新消息)。"""
        if not self._recv_on:
            return
        try:
            msg = event.message
            if msg.out:                      # 自己发出的,不算收到
                return
            chat = await event.get_chat()
            rules = self._recv_rules
            is_broadcast = bool(getattr(chat, 'broadcast', False))
            if rules.get('exclude_channels') and is_broadcast:
                return
            if rules.get('exclude_groups') and event.is_group:
                return
            data = {
                'account': self._account_of(event.client),
                'chat_id': getattr(chat, 'id', None),
                'chat': (getattr(chat, 'title', None) or getattr(chat, 'username', None)
                         or getattr(chat, 'first_name', None) or '未知对话'),
                'chat_type': ('channel' if is_broadcast
                              else 'group' if event.is_group else 'private'),
                'sender': '',
                'sender_id': None,
                'sender_username': None,
                'sender_phone': None,
                'text': ((msg.message or '').strip()
                         or ('(媒体消息)' if msg.media else '')),
                'date': msg.date.strftime('%H:%M:%S') if msg.date else '',
            }

            def _fill_sender(sd, fallback=''):
                data['sender'] = ((getattr(sd, 'first_name', '') or '') + ' '
                                  + (getattr(sd, 'last_name', '') or '')).strip() or fallback
                data['sender_id'] = getattr(sd, 'id', None)
                data['sender_username'] = getattr(sd, 'username', None) or None
                data['sender_phone'] = getattr(sd, 'phone', None) or None

            if rules.get('exclude_bots') and data['chat_type'] != 'channel':
                sender = await event.get_sender()
                if getattr(sender, 'bot', False):
                    return
                _fill_sender(sender, data['chat'])
            elif data['chat_type'] == 'channel':
                # 频道消息的 sender 即频道本身(无 first_name)
                data['sender'] = data['chat']
                data['sender_id'] = getattr(chat, 'id', None)
                data['sender_username'] = getattr(chat, 'username', None) or None
            else:
                sender = await event.get_sender()
                _fill_sender(sender, data['chat'])
            self._gui_schedule(lambda d=data: self.on_message(d))
        except Exception as e:
            # 不再静默: 收不到消息时这里是最重要的诊断点
            self._log(f'[!] 消息处理异常: {type(e).__name__}: {e}')

    def join_chats(self, links):
        """加入群组/频道(当前账号)。links: t.me/xxx、@xxx、t.me/+邀请。"""
        return self._submit(self._do_join_chats(links))

    def list_dialogs(self, account, limit=100):
        """抓取在线账号的 Telegram 会话列表(置顶+最近在前)。"""
        return self._submit(self._do_list_dialogs(account, limit))

    async def _do_list_dialogs(self, account, limit):
        entry = self._pool.get(account)
        if not entry:
            raise RuntimeError(f'账号 {account} 不在线')
        client = entry['client']
        out = []
        async for d in client.iter_dialogs(limit=limit):
            last = d.message
            out.append({
                'id': d.id,
                'name': d.name or '未知会话',
                'type': ('channel' if (d.is_channel and not d.is_group)
                         else 'group' if d.is_group else 'private'),
                'unread': int(d.unread_count or 0),
                'pinned': bool(d.pinned),
                'last_text': ((last.message or '').strip() or ('(媒体消息)' if last and last.media else ''))[:80] if last else '',
                'last_date': last.date.strftime('%H:%M') if last and last.date else '',
            })
        return out

    def fetch_history(self, account, dialog_id, limit=20, offset_id=0):
        """拉取会话历史消息(新->旧);offset_id 传最早一条 id 可向更早翻页。"""
        return self._submit(self._do_fetch_history(account, int(dialog_id), int(limit), int(offset_id)))

    async def _do_fetch_history(self, account, dialog_id, limit, offset_id):
        entry = self._pool.get(account)
        if not entry:
            raise RuntimeError(f'账号 {account} 不在线')
        client = entry['client']
        msgs = []
        sender_cache = {}    # sender_id -> (sender, name);同一发送者多条消息只解析一次
        async for m in client.iter_messages(dialog_id, limit=limit, offset_id=offset_id):
            sid = m.sender_id
            if sid in sender_cache:
                sender, name = sender_cache[sid]
            else:
                sender = None
                name = ''
                try:
                    sender = await m.get_sender()
                    name = (((getattr(sender, 'first_name', '') or '') + ' '
                             + (getattr(sender, 'last_name', '') or '')).strip()
                            or getattr(sender, 'title', None)
                            or getattr(sender, 'username', None) or '')
                except Exception:
                    # 单条发送者解析失败(匿名管理员/已注销/服务消息)不能炸整批历史
                    name = ''
                sender_cache[sid] = (sender, name)
            msgs.append({
                'id': m.id,
                'out': bool(m.out),          # True=小号自己发出
                'sender': name,
                'sender_id': getattr(sender, 'id', None) if sender else None,
                'sender_username': (getattr(sender, 'username', None) or None) if sender else None,
                'text': (m.message or '').strip() or ('(媒体消息)' if m.media else '(服务消息)'),
                'date': m.date.strftime('%m-%d %H:%M') if m.date else '',
            })
        return msgs

    def refresh_profile(self, account):
        """用池中在线 client 刷新账号资料+头像(避免二次连接撞 session 锁)。"""
        return self._submit(self._do_refresh_profile(account))

    async def _do_refresh_profile(self, account):
        entry = self._pool.get(account)
        if not entry:
            raise RuntimeError(f'账号 {account} 不在线')
        import tg_profile
        client = entry['client']
        me = await client.get_me()
        info = {
            'username': me.username or '',
            'first': me.first_name or '',
            'last': me.last_name or '',
            'phone': str(me.phone or ''),
            'uid': str(me.id),
            'dc': str(getattr(client.session, 'dc_id', '') or ''),
        }
        try:
            os.makedirs(tg_profile.AVATAR_DIR, exist_ok=True)
            path = await client.download_profile_photo(me, tg_profile.avatar_path(account))
            if path:
                info['avatar'] = path
            else:
                # 官方语义: 账号未设置头像(或已删除)时返回 None,不算错误
                self._log(f'[资料] {account}: 该账号未设置头像')
        except Exception as e:
            self._log(f'[资料] {account} 头像下载失败: {type(e).__name__}: {e}')
        prof = tg_profile.load_profiles()
        old = prof.get(account, {})
        if not info.get('avatar') and old.get('avatar'):
            info['avatar'] = old['avatar']
        prof[account] = info
        tg_profile.save_profiles(prof)
        return info

    def registered_date(self, name):
        """估算账号注册时间(遍历最早对话的历史消息取最早日期,不可得返回 None)。"""
        return self._submit(self._do_registered_date(name))

    async def _do_registered_date(self, name):
        entry = self._pool.get(name)
        if not entry:
            raise RuntimeError(f'账号 {name} 不在线')
        client = entry['client']
        best = None
        try:
            async for d in client.iter_dialogs(limit=30):
                try:
                    async for m in client.iter_messages(d.id, limit=1, reverse=True):
                        if m.date:
                            dt = m.date.replace(tzinfo=None)
                            if best is None or dt < best:
                                best = dt
                except Exception:
                    continue
        except Exception:
            pass
        return best.strftime('%Y-%m-%d') if best else None

    def security_info(self, names):
        """批量查询在线账号的邮箱/2FA 密码提示/passkey 数量(仅在线,离线跳过)。"""
        return self._submit(self._do_security_info(names or []))

    async def _do_security_info(self, names):
        _ensure_telethon()
        from telethon.tl.functions.account import GetPasskeysRequest, GetPasswordRequest
        out = {}
        for name in names:
            entry = self._pool.get(name)
            if not entry:
                continue
            client = entry['client']
            info = {}
            try:
                pwd = await asyncio.wait_for(client(GetPasswordRequest()), timeout=8)
                if getattr(pwd, 'current_algo', None):
                    hint = (getattr(pwd, 'hint', '') or '').strip()
                    info['twofa'] = hint if hint else '已设置'
                else:
                    info['twofa'] = '未设置'
                email = (getattr(pwd, 'email', '') or '').strip()
                if email:
                    info['email'] = email
            except Exception as e:
                info['err'] = f'{type(e).__name__}: {str(e)[:50]}'
            try:
                pk = await asyncio.wait_for(client(GetPasskeysRequest()), timeout=8)
                info['passkeys'] = len(list(getattr(pk, 'passkeys', []) or []))
            except Exception:
                pass
            out[name] = info
        return out

    def send_message(self, account, dialog_id, text):
        """发送文本消息到指定会话(目前仅适配文本)。"""
        return self._submit(self._do_send_message(account, dialog_id, text))

    async def _do_send_message(self, account, dialog_id, text):
        entry = self._pool.get(account)
        if not entry:
            raise RuntimeError(f'账号 {account} 不在线')
        text = (text or '').strip()
        if not text:
            raise RuntimeError('消息内容为空')
        m = await entry['client'].send_message(dialog_id, text)
        return {
            'id': m.id,
            'out': True,
            'sender': '',
            'sender_id': None,
            'sender_username': None,
            'text': (m.message or '').strip(),
            'date': m.date.strftime('%m-%d %H:%M') if m.date else '',
        }

    @staticmethod
    def _parse_chat_ref(link):
        """链接 -> (类型, 值)。类型: 'invite' 邀请链接 / 'username' 公开名。"""
        s = (link or '').strip()
        low = s.lower()
        if 't.me/+' in low or 'joinchat/' in low:
            return 'invite', s.rsplit('/', 1)[-1].lstrip('+')
        for prefix in ('https://t.me/', 'http://t.me/', 't.me/', '@'):
            if low.startswith(prefix):
                s = s[len(prefix):]
                break
        return 'username', s.strip('/').split('?')[0]

    async def _do_join_chats(self, links):
        _ensure_telethon()
        if not self._client:
            self._state('done', '未连接账号')
            return None
        from telethon.tl.functions.channels import JoinChannelRequest
        from telethon.tl.functions.messages import ImportChatInviteRequest
        links = [l for l in (links or []) if l and l.strip()]
        if not links:
            self._state('done', '链接列表为空')
            return []
        self._task_running = True
        self._cancel.clear()
        self._state('task_start', '加群/频道')
        results, ok = [], 0
        try:
            self._log(T('t154', len(links)))
            for i, link in enumerate(links, 1):
                if self._check_cancel():
                    self._log('[!] 任务已停止')
                    break
                kind, ref = self._parse_chat_ref(link)
                try:
                    if kind == 'invite':
                        await self._client(ImportChatInviteRequest(ref))
                    else:
                        await self._client(JoinChannelRequest(ref))
                    ok += 1
                    results.append({'link': link, 'ok': True})
                    self._log(T('t155', i, len(links), link))
                except FloodWaitError as e:
                    w = min(e.seconds, 600)
                    self._log(T('t073', w))
                    await self._sleep(w + 1)
                    results.append({'link': link, 'ok': False, 'err': f'限流等待{w}s'})
                except Exception as e:
                    already = 'AlreadyParticipant' in type(e).__name__ or 'already' in str(e).lower()
                    if already:
                        ok += 1
                        results.append({'link': link, 'ok': True, 'already': True})
                        self._log(T('t156', i, len(links), link))
                    else:
                        results.append({'link': link, 'ok': False, 'err': str(e)[:100]})
                        self._log(T('t157', i, len(links), link, str(e)[:80]))
                await self._sleep(random.uniform(*tg_tool.DIALOG_DELAY))
            self._log(T('t158', ok, len(results)))
            self._state('done', f'加群完成 {ok}/{len(results)}')
            return results
        except Exception as e:
            self._log(f'[!] 任务出错: {type(e).__name__}: {e}')
            self._state('done', f'出错: {e}')
            return results
        finally:
            self._task_running = False

    # ---------- 安全: passkey / 邮箱 / 2FA ----------

    def get_password_info(self, on_done=None):
        """读 2FA 状态 + 当前邮箱。返回 account.Password。"""
        return self._submit(self._do_get_password_info(on_done))

    async def _do_get_password_info(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import GetPasswordRequest
            res = await self._client(GetPasswordRequest())
            if on_done:
                self._gui_schedule(lambda r=res: on_done(True, r))
            return res
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def get_passkeys(self, on_done=None):
        """列出账号已有的 passkey。返回 list[Passkey]。"""
        return self._submit(self._do_get_passkeys(on_done))

    async def _do_get_passkeys(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import GetPasskeysRequest
            res = await self._client(GetPasskeysRequest())
            keys = list(getattr(res, 'passkeys', []) or [])
            if on_done:
                self._gui_schedule(lambda r=keys: on_done(True, r))
            return keys
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def delete_passkey(self, key_id, on_done=None):
        return self._submit(self._do_delete_passkey(key_id, on_done))

    async def _do_delete_passkey(self, key_id, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import DeletePasskeyRequest
            res = await self._client(DeletePasskeyRequest(id=key_id))
            if on_done:
                self._gui_schedule(lambda r=res: on_done(True, r))
            return res
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def set_2fa(self, current_password, new_password, on_done=None):
        """设置/修改两步验证密码。current_password 未设时可传 ''。"""
        return self._submit(self._do_set_2fa(current_password, new_password, on_done))

    async def _do_set_2fa(self, current_password, new_password, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            await self._client.edit_2fa(current_password=current_password or None,
                                        new_password=new_password)
            if on_done:
                self._gui_schedule(lambda: on_done(True, '2FA 已设置'))
            return True
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def send_verify_email_code(self, email, on_done=None):
        """给邮箱发送验证码(绑定登录邮箱)。"""
        return self._submit(self._do_send_verify_email_code(email, on_done))

    async def _do_send_verify_email_code(self, email, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import SendVerifyEmailCodeRequest
            from telethon.tl.types import EmailVerifyPurposeLoginChange
            res = await self._client(SendVerifyEmailCodeRequest(
                purpose=EmailVerifyPurposeLoginChange(), email=email))
            if on_done:
                self._gui_schedule(lambda r=res: on_done(True, r))
            return res
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def verify_email(self, code, on_done=None):
        """用验证码完成邮箱绑定。"""
        return self._submit(self._do_verify_email(code, on_done))

    async def _do_verify_email(self, code, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import VerifyEmailRequest
            from telethon.tl.types import EmailVerifyPurposeLoginChange, EmailVerificationCode
            res = await self._client(VerifyEmailRequest(
                purpose=EmailVerifyPurposeLoginChange(),
                verification=EmailVerificationCode(code=code)))
            if on_done:
                self._gui_schedule(lambda r=res: on_done(True, r))
            return res
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def get_authorizations(self, on_done=None):
        """列出登录设备(本设备置顶,其余按官方顺序)。返回 list[Authorization]。"""
        return self._submit(self._do_get_authorizations(on_done))

    async def _do_get_authorizations(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import GetAuthorizationsRequest
            res = await self._client(GetAuthorizationsRequest())
            auths = list(getattr(res, 'authorizations', []) or [])
            # 本设备置顶,其余按最后活跃时间倒序(接近官方排序)
            def _key(a):
                t = getattr(a, 'date_active', None)
                return (0 if getattr(a, 'current', False) else 1,
                        -(t.timestamp() if t else 0))
            auths.sort(key=_key)
            if on_done:
                self._gui_schedule(lambda r=auths: on_done(True, r))
            return auths
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def init_passkey_registration(self, on_done=None):
        """发起 passkey 注册,返回 WebAuthn publicKey JSON。"""
        return self._submit(self._do_init_passkey_registration(on_done))

    async def _do_init_passkey_registration(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import InitPasskeyRegistrationRequest
            res = await self._client(InitPasskeyRegistrationRequest())
            data = getattr(getattr(res, 'options', None), 'data', '') or ''
            if on_done:
                self._gui_schedule(lambda d=data: on_done(True, d))
            return data
        except Exception as e:
            msg = str(e)
            # 服务器防盗号保护: 新登录的 session 24h 内不能管理其他授权
            if 'too new' in msg.lower() or 'SESSION_TOO_NEW' in msg:
                msg = ('新登录的 session 24 小时内不能注册通行密钥'
                       '(Telegram 防盗号保护),请先用该号正常挂机一天后再试')
            if on_done:
                self._gui_schedule(lambda m=msg: on_done(False, m))
            return None

    def register_passkey(self, cred_id, raw_id, client_data, attestation_data, on_done=None):
        """用 WebAuthn 返回的 credential 完成 passkey 注册。"""
        return self._submit(self._do_register_passkey(cred_id, raw_id, client_data, attestation_data, on_done))

    async def _do_register_passkey(self, cred_id, raw_id, client_data, attestation_data, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import RegisterPasskeyRequest
            from telethon.tl.types import InputPasskeyCredentialPublicKey, InputPasskeyResponseRegister, DataJSON
            cred = InputPasskeyCredentialPublicKey(
                id=cred_id,
                raw_id=raw_id,
                response=InputPasskeyResponseRegister(
                    client_data=DataJSON(data=client_data),
                    attestation_data=attestation_data,
                ),
            )
            res = await self._client(RegisterPasskeyRequest(credential=cred))
            if on_done:
                self._gui_schedule(lambda r=res: on_done(True, r))
            return res
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def get_full_info(self, on_done=None):
        """读取账号完整资料(简介/生日/关联频道)。返回 dict。"""
        return self._submit(self._do_get_full_info(on_done))

    async def _do_get_full_info(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            from telethon.tl.functions.channels import GetAdminedPublicChannelsRequest
            full = await self._client(GetFullUserRequest(id='me'))
            chans = await self._client(GetAdminedPublicChannelsRequest())
            users = list(getattr(full, 'users', []) or [])
            me = users[0] if users else await self._client.get_me()
            data = {
                'first': getattr(me, 'first_name', '') or '',
                'last': getattr(me, 'last_name', '') or '',
                'username': getattr(me, 'username', '') or '',
                'about': getattr(full.full_user, 'about', '') or '',
                'birthday': getattr(full.full_user, 'birthday', None),
                'channels': list(getattr(chans, 'chats', []) or []),
            }
            if on_done:
                self._gui_schedule(lambda d=data: on_done(True, d))
            return data
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def get_me(self, on_done=None):
        """获取当前登录账号的 username/姓名。返回 dict。"""
        return self._submit(self._do_get_me(on_done))

    async def _do_get_me(self, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            me = await self._client.get_me()
            data = {
                'username': getattr(me, 'username', '') or '',
                'first': getattr(me, 'first_name', '') or '',
                'last': getattr(me, 'last_name', '') or '',
                'phone': getattr(me, 'phone', '') or '',
            }
            if on_done:
                self._gui_schedule(lambda d=data: on_done(True, d))
            return data
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def update_profile(self, first_name=None, last_name=None, about=None, on_done=None):
        """更新姓名/简介。"""
        return self._submit(self._do_update_profile(first_name, last_name, about, on_done))

    async def _do_update_profile(self, first_name, last_name, about, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import UpdateProfileRequest
            await self._client(UpdateProfileRequest(first_name=first_name,
                                                    last_name=last_name,
                                                    about=about))
            if on_done:
                self._gui_schedule(lambda: on_done(True, '资料已更新'))
            return True
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def update_username(self, username, on_done=None):
        return self._submit(self._do_update_username(username, on_done))

    async def _do_update_username(self, username, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import UpdateUsernameRequest
            await self._client(UpdateUsernameRequest(username=username))
            if on_done:
                self._gui_schedule(lambda: on_done(True, '用户名已更新'))
            return True
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def update_birthday(self, day, month, year, on_done=None):
        return self._submit(self._do_update_birthday(day, month, year, on_done))

    async def _do_update_birthday(self, day, month, year, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import UpdateBirthdayRequest
            from telethon.tl.types import Birthday
            await self._client(UpdateBirthdayRequest(
                birthday=Birthday(day=day, month=month, year=year)))
            if on_done:
                self._gui_schedule(lambda: on_done(True, '生日已更新'))
            return True
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def upload_avatar(self, file_bytes, on_done=None):
        """上传头像(file_bytes 为 PNG 图片字节)。"""
        return self._submit(self._do_upload_avatar(file_bytes, on_done))

    async def _do_upload_avatar(self, file_bytes, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            import io
            from telethon.tl.functions.photos import UploadProfilePhotoRequest
            f = io.BytesIO(file_bytes)
            f.name = 'avatar.png'
            uploaded = await self._client.upload_file(f)
            await self._client(UploadProfilePhotoRequest(file=uploaded))
            if on_done:
                self._gui_schedule(lambda: on_done(True, '头像已更新'))
            return True
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def reset_authorization(self, auth_hash, on_done=None):
        """注销某个在线设备(terminate session)。"""
        return self._submit(self._do_reset_authorization(auth_hash, on_done))

    async def _do_reset_authorization(self, auth_hash, on_done=None):
        _ensure_telethon()
        if not self._client:
            if on_done:
                self._gui_schedule(lambda: on_done(False, '未连接账号'))
            return None
        try:
            from telethon.tl.functions.account import ResetAuthorizationRequest
            await self._client(ResetAuthorizationRequest(hash=auth_hash))
            if on_done:
                self._gui_schedule(lambda: on_done(True, '设备已注销'))
            return True
        except Exception as e:
            if on_done:
                self._gui_schedule(lambda msg=str(e): on_done(False, msg))
            return None

    def convert_tdata(self, account_dir):
        return self._submit(self._do_convert_tdata(account_dir))

    async def _do_convert_tdata(self, account_dir):
        # _convert_tdata 内部用 asyncio.run —— 放到 executor 线程避免嵌套循环
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, tg_tool._convert_tdata, account_dir)

    def update_telegram(self):
        """任务3: 复用 CLI 的 task_update_telegram,GUI 已确认故 input 自动答 y。"""
        return self._submit(self._do_update_telegram())

    async def _do_update_telegram(self):
        if self._task_running:
            self._state('done', '已有任务在运行')
            return
        self._task_running = True
        self._cancel.clear()
        self._state('task_start', '更新 Telegram 本体')
        import builtins
        orig = builtins.input
        builtins.input = lambda *a, **k: 'y'
        try:
            tg_tool.task_update_telegram()
            self._state('done', '更新完成')
        except SystemExit:
            self._state('done', '更新失败(详见日志)')
        except Exception as e:
            self._log(f'[!] 更新出错: {type(e).__name__}: {e}')
            self._state('done', f'更新出错: {e}')
        finally:
            builtins.input = orig
            self._task_running = False

    # ---------- 停止 ----------

    def stop_task(self):
        """温和停止: 当前动作完成后停。返回是否真的请求了停止。"""
        if self._task_running:
            self._cancel.set()
            self._log('[停止] 已请求停止,当前动作完成后中止…')
            return True
        return False

    # ---------- 账号轮询(保活+测活) ----------

    def poll_accounts(self, root):
        """轮询全部账号: 逐个登录一次防死号,顺带测活。结果落盘 poll_results.json。"""
        return self._submit(self._do_poll_accounts(root))

    async def _do_poll_accounts(self, root):
        if self._task_running:
            self._state('done', '已有任务在运行')
            return None
        _ensure_telethon()
        import tg_profile
        accounts = scan_accounts(root)
        results_path = os.path.join(tg_tool.SCRIPT_DIR, 'poll_results.json')
        self._task_running = True
        self._cancel.clear()
        self._state('task_start', '账号轮询')

        def _save(res):
            try:
                json.dump(res, open(results_path, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
            except Exception:
                pass

        def _now():
            return time.strftime('%Y-%m-%d %H:%M')

        results, ok_n = {}, 0
        total = len(accounts)
        self._log(f'[轮询] 开始: 共 {total} 个账号,逐号登录保活+测活(每号间隔 1s)')
        try:
            for i, (name, path, st) in enumerate(accounts, 1):
                if self._check_cancel():
                    self._log(T('t164'))
                    break
                self._prog(i, total, name)
                now = _now()
                if st == 'empty':
                    results[name] = {'alive': False, 'msg': '无登录态', 'time': now}
                    self._log(T('t165', name))
                elif name in self._pool:
                    ok_n += 1
                    results[name] = {'alive': True, 'msg': '在线', 'time': now}
                    self._log(T('t160', i, total, name))
                else:
                    try:
                        if st == 'tdata':
                            loop = asyncio.get_event_loop()
                            okc = await loop.run_in_executor(
                                None, tg_tool._convert_tdata, path)
                            if not okc:
                                results[name] = {'alive': False,
                                                 'msg': 'tdata 转换失败', 'time': now}
                                self._log(T('t161', i, total, name, 'tdata 转换失败'))
                                _save(results)
                                await self._sleep(1.0)
                                continue
                        cfg_path, cfg = find_cfg(path)
                        client = make_client(cfg_path, cfg)
                        try:
                            await asyncio.wait_for(client.connect(), timeout=30)
                            if await client.is_user_authorized():
                                ok_n += 1
                                results[name] = {'alive': True, 'msg': '存活', 'time': now}
                                self._log(T('t160', i, total, name))
                            else:
                                # authorized=False = session 被服务器拒绝,账号未死,重新登录即可
                                results[name] = {'alive': None,
                                                 'msg': 'session 失效,账号未死,请重新登录(勿删号!)',
                                                 'time': now}
                                self._log(f'[轮询] {i}/{total} {name}: session 失效,未判定死号(重新登录可恢复)')
                        finally:
                            try:
                                await client.disconnect()
                            except Exception:
                                pass
                    except SystemExit:
                        results[name] = {'alive': False, 'msg': '无凭据 json', 'time': now}
                        self._log(T('t161', i, total, name, '无凭据 json'))
                    except Exception as e:
                        msg = f'{type(e).__name__}: {str(e)[:70]}'
                        if 'FloodWait' in msg:
                            # 限流=服务器可达=账号活着
                            ok_n += 1
                            results[name] = {'alive': True,
                                             'msg': f'存活(限流)', 'time': now}
                            self._log(T('t160', i, total, name) + '(限流)')
                        else:
                            kind = tg_profile.classify_conn_error(e)
                            # 只有封禁/注销才是真死号;session 失效与网络失败一律不判死
                            results[name] = {'alive': kind == 'banned',
                                             'msg': tg_profile._err_msg(kind, e)[:80],
                                             'time': now}
                            self._log(f'[轮询] {i}/{total} {name}: {tg_profile._err_msg(kind, e)}')
                _save(results)
                await self._sleep(1.0)
            dead_n = sum(1 for v in results.values() if v.get('alive') is False)
            self._log(T('t163', ok_n, len(results), dead_n))
            self._state('done', f'轮询完成: 存活 {ok_n}/{len(results)}')
        except Exception as e:
            self._log(f'[!] 轮询出错: {type(e).__name__}: {e}')
            self._state('done', f'轮询出错: {e}')
        finally:
            self._task_running = False
        return results


def _dlbl_safe(d):
    try:
        return tg_tool._dlbl(d)
    except Exception:
        return f'(id={getattr(d.entity, "id", "?")})'
