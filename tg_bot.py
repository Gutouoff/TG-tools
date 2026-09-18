#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TG工具箱 Bot 收件箱 —— 本地运行一个 TG Bot，自动识别转发给它的账号文件并归档。

用法(由 server.py 驱动):
    inbox = BotInbox(token, allowed_ids, ingest_cb, log_cb, event_cb)
    inbox.start()                # 独立线程 + 独立 asyncio loop(bot client 单循环纪律)
    inbox.wait_ready(45)         # 等连接结果(成功/失败)
    inbox.stop()

工作流:
  1. 用户在 @BotFather 建 bot 拿 token,在工具箱设置里填入并启动;
  2. 允许列表外的用户发消息,bot 只回他的 ID(便于把自己加进列表),不接收文件;
  3. 允许列表内的用户转发 .session/.json/2fa.txt/.zip 给 bot;
  4. 同一用户短时间内的连续转发会被合并成一批(debounce),每个 zip 单独成一个账号,
     散文件(session/json/2fa.txt)合并成一个账号,交给 ingest_cb 归档;
  5. 归档结果回发到 TG 聊天,并经 log_cb 打到工具箱日志页。

ingest_cb: async callable(dir_path, passwords) -> dict(ok, msg, name, path)
    入参目录里是待识别的文件(bot 已下载好);密码候选来自转发时填写的文字说明。
"""
import asyncio
import os
import shutil
import tempfile
import threading
import time

import tg_tool
from tg_tool import T

# 支持的文件类型(其他文档直接拒收,不浪费下载)
ACCEPT_EXTS = ('.session', '.session-journal', '.json', '.zip', '.txt')
# 单文件大小上限(bot 经 MTProto 下载,不走 Bot API 的 20MB 限制)
MAX_FILE = 512 * 1024 * 1024
# 同一用户连续转发的合并窗口: 转发多个文件时 TG 逐条投递,等安静了再统一处理
GROUP_WAIT = 4.0
# 非允许用户提示的冷却时间(秒),防刷屏
NAG_TTL = 3600

# bot 客户端走 Telegram Desktop 公开凭据(与 tdata 转换/自愈补建一致)
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'


class BotInbox:
    """一个 BotInbox 对应一个 bot token。持有独立线程/loop/client。"""

    def __init__(self, token, allowed_ids=None, ingest_cb=None, log_cb=None, event_cb=None):
        self._token = (token or '').strip()
        self._allowed_ids = {int(x) for x in (allowed_ids or [])}
        self._ingest_cb = ingest_cb
        self._log_cb = log_cb or (lambda msg: None)
        self._event_cb = event_cb or (lambda: None)
        self._loop = None
        self._thread = None
        self._client = None
        self._me = None
        self._error = ''
        self._running = False
        self._ready = threading.Event()     # 连接有结果(成功或失败)时置位
        self._nag = {}                      # 非允许用户上次提示时间(uid -> monotonic)
        self._bufs = {}                     # 待发文件缓冲(uid -> {'items': [...], 'task': Task})
        self._ingest_lock = None            # 归档串行(loop 内创建)

    # ---------- 对外(线程安全) ----------

    def start(self):
        self._ready.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True,
                                        name='tg-bot-inbox')
        self._thread.start()

    def wait_ready(self, timeout=45):
        """等首次连接结果。返回 True=已上线,False=失败/超时(原因看 status()['error'])。"""
        return self._ready.wait(timeout) and self._running

    def stop(self):
        loop = self._loop
        if loop is not None and not loop.is_closed():
            def _dc():
                for buf in self._bufs.values():
                    t = buf.get('task')
                    if t and not t.done():
                        t.cancel()
                c = self._client
                if c is not None and c.is_connected():
                    asyncio.ensure_future(c.disconnect())
            try:
                loop.call_soon_threadsafe(_dc)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=15)
        self._running = False

    def set_allowed(self, ids):
        """热更新允许列表(不用重启 bot)。"""
        self._allowed_ids = {int(x) for x in (ids or [])}

    def status(self):
        return {'running': self._running,
                'username': (self._me or {}).get('username', ''),
                'id': (self._me or {}).get('id', 0),
                'error': self._error}

    @property
    def running(self):
        return self._running

    # ---------- 线程/loop ----------

    def _log(self, msg):
        try:
            self._log_cb(msg)
        except Exception:
            pass

    def _thread_main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ingest_lock = asyncio.Lock()
        try:
            self._loop.run_until_complete(self._run())
        except Exception as e:
            if not self._error:
                self._error = f'{type(e).__name__}: {str(e)[:120]}'
            self._log(T('t175', self._error))
        finally:
            self._running = False
            self._ready.set()
            try:
                self._event_cb()
            except Exception:
                pass
            try:
                self._loop.close()
            except Exception:
                pass

    async def _run(self):
        tg_tool._ensure_telethon()   # 惰性导入 telethon + TL 补丁
        from telethon import TelegramClient, events
        from telethon.sessions import MemorySession
        proxy = tg_tool.resolve_proxy()
        if proxy and proxy[0].startswith('socks') and not tg_tool._HAS_SOCKS:
            proxy = None
        client = TelegramClient(MemorySession(), API_ID, API_HASH, proxy=proxy)
        self._client = client
        try:
            await client.start(bot_token=self._token)
            me = await client.get_me()
        except Exception as e:
            self._error = f'{type(e).__name__}: {str(e)[:120]}'
            self._ready.set()
            try:
                await client.disconnect()
            except Exception:
                pass
            return
        self._me = {'id': me.id, 'username': getattr(me, 'username', '') or '',
                    'name': me.first_name or ''}
        self._running = True
        self._error = ''
        self._log(T('t174', self._me['username'] or self._me['name'], self._me['id']))
        try:
            self._event_cb()
        except Exception:
            pass
        self._ready.set()
        client.add_event_handler(self._on_message, events.NewMessage())
        try:
            await client.run_until_disconnected()
        finally:
            self._running = False
            self._log(T('t176'))
            try:
                self._event_cb()
            except Exception:
                pass

    # ---------- 消息处理 ----------

    async def _reply(self, msg, text):
        try:
            await msg.reply(text[:3900])
        except Exception:
            pass   # 回复失败(被拉黑/限流)不影响主流程

    async def _on_message(self, event):
        msg = event.message
        # msg.out=自己发出的消息(回复)——NewMessage 默认收发都触发,必须排除,
        # 否则 bot 会对自己的回复再回一条(循环)
        if not msg or msg.out or not msg.is_private:
            return
        uid = msg.sender_id
        text = (msg.message or '').strip()
        # 允许列表之外: 只回他的 ID(冷却防刷屏),文件一律不收
        if uid not in self._allowed_ids:
            last = self._nag.get(uid, 0)
            if text.lower().startswith('/') or time.monotonic() - last > NAG_TTL:
                self._nag[uid] = time.monotonic()
                self._log(T('t180', uid))
                await self._reply(msg, T('t183', uid))
            return
        # 命令
        if text.startswith('/') and not msg.document:
            await self._reply(msg, T('t184', uid))
            return
        # 只收文档;照片/视频/语音等直接提示
        if not msg.document:
            if msg.media is not None:
                await self._reply(msg, T('t188', getattr(msg.file, 'mime_type', '') or 'media'))
            return
        fname = (msg.file.name if msg.file else '') or f'doc_{msg.id}'
        fname = fname.split('/')[-1].split('\\')[-1] or f'doc_{msg.id}'
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ACCEPT_EXTS:
            await self._reply(msg, T('t188', ext or fname))
            return
        size = msg.file.size if msg.file else 0
        if size and size > MAX_FILE:
            self._log(T('t181', fname))
            await self._reply(msg, T('t189', fname, MAX_FILE // 1048576))
            return
        # 入缓冲并重置合并计时: 连续转发(multiple/album 逐条到达)合并为一批
        buf = self._bufs.setdefault(uid, {'items': [], 'task': None})
        buf['items'].append((msg, fname, text))
        t = buf.get('task')
        if t and not t.done():
            t.cancel()
        buf['task'] = self._loop.create_task(self._flush_later(uid))

    async def _flush_later(self, uid):
        try:
            await asyncio.sleep(GROUP_WAIT)
        except asyncio.CancelledError:
            return
        buf = self._bufs.pop(uid, None)
        if not buf or not buf['items']:
            return
        async with self._ingest_lock:
            try:
                await self._process(uid, buf['items'])
            except Exception as e:
                self._log(T('t179', f'{type(e).__name__}: {str(e)[:120]}'))
                try:
                    await self._reply(buf['items'][0][0],
                                      T('t187', f'{type(e).__name__}: {str(e)[:120]}'))
                except Exception:
                    pass

    async def _process(self, uid, items):
        """下载一批文件并归档。items: [(msg, fname, caption), ...]"""
        tmp = tempfile.mkdtemp(prefix='tgbot_')
        try:
            passwords = []
            zips = []
            loose = []
            for msg, fname, caption in items:
                if caption:
                    passwords.append(caption)
                dst = os.path.join(tmp, fname)
                if os.path.exists(dst):
                    continue   # 同名重复转发,忽略后者
                try:
                    p = await msg.download_media(file=dst)
                except Exception as e:
                    self._log(f'[Bot] 下载失败 {fname}: {type(e).__name__}: {str(e)[:80]}')
                    continue
                if p and os.path.isfile(p):
                    (zips if fname.lower().endswith('.zip') else loose).append(p)
            if not zips and not loose:
                return
            self._log(T('t177', len(zips) + len(loose), uid))
            await self._reply(items[0][0], T('t185', len(zips) + len(loose)))
            results = []
            # 每个 zip 独立成一个账号(互不染指);散文件合并成一个账号
            for zp in zips:
                sub = tempfile.mkdtemp(prefix='tgbotz_')
                try:
                    shutil.move(zp, os.path.join(sub, os.path.basename(zp)))
                    results.append(await self._ingest_cb(sub, passwords))
                finally:
                    shutil.rmtree(sub, ignore_errors=True)
            if loose:
                sub = tempfile.mkdtemp(prefix='tgbotl_')
                try:
                    for p in loose:
                        shutil.move(p, os.path.join(sub, os.path.basename(p)))
                    results.append(await self._ingest_cb(sub, passwords))
                finally:
                    shutil.rmtree(sub, ignore_errors=True)
            lines = []
            for r in results:
                r = r or {}
                line = str(r.get('msg') or '')
                if r.get('ok'):
                    self._log(T('t178', line))
                    lines.append(T('t186', line))
                else:
                    self._log(T('t179', line))
                    lines.append(T('t187', line))
            if lines:
                await self._reply(items[0][0], '\n'.join(lines))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
