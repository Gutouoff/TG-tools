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

    def __init__(self, on_log=None, on_progress=None, on_state=None, gui_schedule=None):
        self.on_log = on_log or (lambda msg: None)
        self.on_progress = on_progress or (lambda done, total, label: None)
        self.on_state = on_state or (lambda st, data: None)
        self._gui_schedule = gui_schedule or (lambda fn: fn())   # 默认同步调
        self._loop = None
        self._thread = None
        self._client = None
        self._me = None
        self._account_dir = None
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
        """断开并结束线程。"""
        if self._loop is None:
            return
        async def _fin():
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
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
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            self._account_dir = account_dir
            self._log(T('t050a', os.path.basename(account_dir)))
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
            users = [u for u in all_users if u.id not in tg_tool.USER_WHITELIST]
            wl = [u for u in all_users if u.id in tg_tool.USER_WHITELIST]
            self._log(T('t066', len(all_users), len(wl), len(users)))
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
                              if u.id != me.id and u.id not in tg_tool.USER_WHITELIST]
                    if remain:
                        w = random.uniform(*tg_tool.CONTACT_ROUND_DELAY)
                        self._log(T('t077', w))
                        await self._sleep(w)
                    else:
                        break

            res2 = await client(functions.contacts.GetContactsRequest(hash=0))
            left = [u for u in res2.users if u.id != me.id and u.id not in tg_tool.USER_WHITELIST]
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
        label = {'privates': '删除全部私聊', 'groups': '退出群组/频道',
                 'all': '全部执行(私聊+群组/频道)'}.get(choice, choice)
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
            for d in dialogs:
                e = d.entity
                eid = getattr(e, 'id', None)
                if eid == me.id:
                    keep_users.append(d)
                elif eid in tg_tool.USER_WHITELIST:
                    keep_users.append(d)
                elif d.is_user:
                    if getattr(e, 'bot', False):
                        bots.append(d)
                    elif getattr(e, 'deleted', False) or getattr(e, 'first_name', None) == 'Deleted Account':
                        deleted.append(d)
                    else:
                        users.append(d)
                elif d.is_group or d.is_channel:
                    if eid in tg_tool.GROUP_WHITELIST:
                        keep_groups.append(d)
                    else:
                        groups.append(d)

            self._log(T('t083', len(dialogs), len(users), len(deleted), len(bots),
                        len(groups), len(keep_users) + len(keep_groups)))

            all_privates = users + deleted + bots

            async def del_user(client, d):
                await client.delete_dialog(d.entity, revoke=True)

            async def block_bot(client, d):
                await client.delete_dialog(d.entity, revoke=True)
                await client(BlockRequest(id=d.entity))

            if choice in ('privates', 'all'):
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
                    if getattr(e, 'bot', False):
                        bots.append(d)
                    elif getattr(e, 'deleted', False) or getattr(e, 'first_name', None) == 'Deleted Account':
                        deleted.append(d)
                    else:
                        users.append(d)
                elif d.is_group or d.is_channel:
                    if eid in tg_tool.GROUP_WHITELIST:
                        keep_groups.append(d)
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
            deletable = [u for u in all_users if u.id not in tg_tool.USER_WHITELIST]
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


def _dlbl_safe(d):
    try:
        return tg_tool._dlbl(d)
    except Exception:
        return f'(id={getattr(d.entity, "id", "?")})'
