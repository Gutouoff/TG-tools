#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG小号 工具箱 (三合一: 删联系人 / 删对话 / 更新本体)
====================================================
文件位置: 本脚本和 tdata2session.py 都在「TG小号\工具箱\」里,
          根目录的「TG工具箱.bat」是启动器,双击即可。

模式(自动检测,按双击 bat 时所在的目录):
  * 在「TG小号 根目录」双击 bat → 多账号模式: 先选号,之后本次会话固定为该账号的
    工作区;完成一个操作自动退回操作菜单,不用重选号;[9] 随时切换账号
  * 把 bat 复制进某个「账号文件夹」双击 → 单账号模式,直接进该号的工作区

功能:
  [1] 删除联系人 —— 白名单(5434838648/6775358409/238879089)永不删;
                    每批50 + 随机间隔(批间5-10s/轮间20-40s)防风控
  [2] 删除对话   —— 白名单之外全删(私聊+已注销+bot拉黑+退群),
                    白名单群2284618069和用户白名单保留;每个动作间隔约2.5s防风控
  [3] 更新本体   —— 官网下载最新便携版,替换所在目录树的 Telegram.exe(无需账号)

日志 -> 工具箱\\logs\\   备份 -> 工具箱\\backups\\
依赖: python3.14 -m pip install telethon opentele-ng
"""
import asyncio
import glob
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile


# ============ 版本号 ============
# 规则(semver): 大版本.小版本.微调[-beta.N]
#   大版本=架构级/破坏性变更; 小版本=新功能; 微调=bug修复与界面小改
#   大/小版本发布前用 -beta.N 预发布(测试版); beta 不做不可逆配置迁移
APP_VERSION = '1.1.0'


# ============ 界面文本(自定义: 编辑同目录 界面文本.txt,删除即恢复默认) ============
DEFAULT_TEXTS = {
    't001': '[!] TL 补丁加载失败(不影响其他功能): {0}',
    't002': '!! 缺 telethon,先装: python3.14 -m pip install telethon',
    't003': '已加载自定义白名单: 用户 {0} 个,群/频道 {1} 个',
    't004': '白名单文件损坏({0}),用默认值',
    't005': '!! 白名单保存失败: {0}',
    't006': '  白名单管理 (当前配置,所有账号共用)',
    't007': '  用户白名单 {0} 个:',
    't008': '(默认)',
    't009': '  群/频道白名单 {0} 个:',
    't010': '(默认)',
    't011': '  [1] 添加用户  [2] 移除用户',
    't012': '  [3] 添加群/频道  [4] 移除群/频道',
    't013': '  [5] 恢复默认白名单',
    't014': '  [0] 返回',
    't015': '选选项: ',
    't016': '输入用户 ID 或 @用户名: ',
    't017': '找不到该用户(检查 ID/用户名)',
    't018': '{0} 是 bot,白名单是给真人用的,不加了',
    't019': '已添加用户白名单: {0} {1} {2}',
    't020': '输入要移除的用户 ID: ',
    't021': '已移除用户白名单: {0}',
    't022': '该 ID 不在白名单里',
    't023': '输入群/频道 ID 或 @链接名(频道如 @durov): ',
    't024': '找不到该群/频道',
    't025': '已添加群/频道白名单: {0} {1}',
    't026': '输入要移除的群/频道 ID: ',
    't027': '已移除群/频道白名单: {0}',
    't028': '该 ID 不在白名单里',
    't029': '恢复默认白名单? 输入 y 回车: ',
    't030': '已恢复默认白名单',
    't031': '无效选项。',
    't032': '极快',
    't033': '快速',
    't034': '默认',
    't035': '慢速',
    't036': '极慢',
    't037': '回车退出...',
    't038': '  [提示] 未装 opentele-ng,tdata 账号无法自动转换(先装: pip install opentele-ng)',
    't039': '  [tdata转换] {0}: +{1}  {2} {3}  uid={4}',
    't040': '  [tdata转换失败] {0}: {1}: {2}',
    't041': '发现 {0} 个只有 tdata 的账号,自动转换中...',
    't042': '{0} 里没找到账号 json',
    't043': '目录里有多个账号 json,请移走多余的:\n  ',
    't044': '目录里有多个 .session,分不清哪个是正主,请先移走备份:\n  ',
    't045': '登录方式: {0}',
    't046': '登录方式: json 里的 session_str',
    't047': '{0} 里没有 .session,json 里也没有 session_str —— 这个号还没转出登录态',
    't048': '登录态已失效(session 过期或在别处被踢)',
    't049': '账号对不上! json 记录 user_id={0},实际登录 {1} —— 中止,绝不误删',
    't050': '账号: +{0}  昵称: {1} {2}',
    't050a': '正在连接账号: {0} …',
    't050b': '已切换到账号: {0}（保持在线）',
    't051': '  删除速度(每个动作的随机间隔):',
    't052': '选速度(1-5,回车=默认): ',
    't053': '速度档: {0}  对话间隔 {1}~{2}s  联系人批间 {3}~{4}s 轮间 {5}~{6}s',
    't054': '[回车返回] ',
    't055': '  当前账号: {0}',
    't056': '  [1] 删除联系人 (白名单保护)',
    't057': '  [2] 删除对话 (清理/退群/拉黑bot)',
    't058': '  [3] 更新 Telegram 本体 (下载最新版)',
    't059': '  [4] 白名单管理',
    't060': '  [9] 切换账号',
    't061': '  [0] 退出',
    't062': '请输入选项: ',
    't063': '任务出错: {0}: {1}',
    't064': '无效选项。',
    't065': '--- 扫描联系人 ---',
    't066': '联系人总数: {0}  白名单保留: {1}  可删: {2}',
    't067': '  白名单 -> {0} {1}(id={2})',
    't068': '没有可删的联系人。',
    't069': '确认删除这 {0} 个联系人? 输入 y 回车,其他取消: ',
    't070': '已取消。',
    't071': '已备份 {0} 个联系人 -> {1}',
    't072': '第 {0} 轮: 待删 {1} 个',
    't073': '  被限流,等 {0}s ...',
    't074': '  批次失败: {0}',
    't075': '  删联系人 {0}  累计 {1}/{2}',
    't075a': '删除联系人',
    't091a': '退出群/频道',
    't076': '  (等 {0:.0f}s 再删下一批,防风控...)',
    't077': '(等 {0:.0f}s 开始下一轮...)',
    't078': '=== 完成: 共删 {0} 个,残留 {1} 个,白名单保留 {2} 个 ===',
    't079': '正在拉取全部对话(含归档)...',
    't080': '  归档对话 {0} 个',
    't081': '  (归档对话拉取失败,忽略: {0})',
    't082': '共 {0} 个对话。',
    't083': '分类完成: 总 {0} = 私聊 {1} + 已注销 {2} + bot {3} + 群/频道 {4} + 保留 {5}',
    't084': '已备份 {0} 个 -> {1}',
    't085': '[{0}] 没有要处理的。',
    't086': '  被限流,等 {0}s ...',
    't087': '  {0} {1}/{2} 失败 {3}: {4}',
    't088': '[{0}] 完成 {1}/{2}',
    't089': '  总对话数: {0} 个 (含归档)',
    't090': '  [1] 删除全部私聊 : {0} 个 (普通 {1} + 已注销 {2} + bot {3})',
    't091': '  [2] 退出群/频道  : {0} 个',
    't092': '  [3] 全选(1+2)',
    't093': '  (以下保留不删)',
    't094': '  群白名单保留 -> {0}',
    't095': '收藏夹',
    't096': '用户白名单',
    't097': '  {0}保留 -> {1}',
    't098': '  [0] 返回',
    't099': '选选项(1-3),0 返回: ',
    't100': '已取消。',
    't101': '  退出群/频道 {0}  {1}',
    't102': '  被限流,等 {0}s ...',
    't103': '  退出失败 {0}: {1} -> 改用删对话记录',
    't104': '    已删对话记录 {0}  {1}',
    't105': '    删记录也失败 {0}: {1}',
    't106': '[退出群/频道] 完成 {0}/{1}',
    't107': '删已注销',
    't108': '拉黑bot',
    't109': '删私聊',
    't110': '=== 对话清理完成 ===',
    't111': '  下载 {0} MB',
    't112': '更新本体,工作目录: {0}',
    't113': '扫描到 {0} 个程序文件:',
    't114': '确认下载最新版并替换? 输入 y 回车,其他取消: ',
    't115': '已取消。',
    't116': '结束运行中的小号进程 PID {0}: {1}',
    't117': '开始下载最新便携版...',
    't118': '官网直连',
    't119': '官网(经 {0})',
    't120': '  尝试 {0} ...',
    't121': '    失败: {0}',
    't122': '官网走不通,试 GitHub 官方发布页...',
    't123': 'GitHub 也访问不了 —— 检查网络/代理(梯子)再重跑',
    't124': 'GitHub 下载失败: {0}',
    't125': '下载文件太小,不对,中止',
    't126': '下载完成: {0} MB',
    't127': ' (版本 {0})',
    't128': 'zip 校验失败',
    't129': '压缩包校验失败: {0}',
    't130': '压缩包里找不到 Telegram.exe,中止',
    't131': '解压出的 Telegram.exe 大小异常,中止',
    't132': '开始替换...',
    't133': '  跳过 {0} (新包里没有 {1})',
    't134': '  跳过 {0} (与新版同大小,视为已最新)',
    't135': '  替换 {0}  {1}',
    't136': '  !! 失败 {0}: {1}',
    't137': '  已放入根目录 {0}',
    't138': '=== 完成: 替换 {0} 个,跳过(已最新) {1} 个,失败 {2} 个 ===',
    't139': '  新版本: {0}',
    't140': '\n检测到以下账号:',
    't141': '  [0] 返回',
    't142': '选账号(序号或直接输入名字/手机号搜索): ',
    't143': '没找到匹配 "{0}" 的账号。',
    't144': '唯一匹配 -> {0}',
    't145': '匹配到 {0} 个账号:',
    't146': '选一个(序号,0=取消): ',
    't147': '日志文件: {0}',
    't148': '[单账号模式] 账号目录: {0}',
    't149': '[多账号模式] 检测到 {0} 个账号文件夹',
    't150': '未选择账号,退出。',
    't151': '退出。',
    't152': '  官方/认证频道与账号 {0} 个，已保留',
    't153': '消息接收已{0}（在线账号 {1} 个；{2}）',
    't154': '开始加入 {0} 个群/频道链接…',
    't155': '  加群 {0}/{1} 成功：{2}',
    't156': '  加群 {0}/{1} 已在群中：{2}',
    't157': '  加群 {0}/{1} 失败：{2} — {3}',
    't158': '加群完成：成功 {0}/{1}',
    't159': '[tdata] {0}: 检测到仅 tdata 登录态,自动转换为 session …',
    't160': '[轮询] {0}/{1} {2}: 存活',
    't161': '[轮询] {0}/{1} {2}: 死号 ({3})',
    't162': '[轮询] {0}: 在线账号跳过(已登录)',
    't163': '[轮询] 完成: 存活 {0}/{1}, 死号 {2}',
    't164': '[轮询] 已停止',
    't165': '[轮询] {0}: 无登录态(缺 session),无法保活',
    't166': '[自愈] {0}: 缺少凭据 json,正在用 session 自动补建 …',
    't167': '[自愈] {0}: 已补建 json (账号: +{1}  昵称: {2} {3}  id={4})',
    't169': '[刷新] 批量开始: {0} 个账号待刷新(仅处理有 tdata 且测活失败的)',
    't170': '[刷新] {0}/{1} {2}: 完成',
    't172': '[刷新] 批量完成: 刷新 {0}/{1}',
    't173': '  安装客户端(原先没有): {0}',
}
UI_TEXTS = {}

def _load_ui_texts():
    # frozen 打包: 先读 exe 旁(可编辑),再回退到打包模板(_MEIPASS)
    paths = [os.path.join(SCRIPT_DIR, '界面文本.txt')]
    if IS_FROZEN:
        try:
            paths.append(os.path.join(sys._MEIPASS, '界面文本.txt'))
        except Exception:
            pass
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            for ln in open(p, encoding='utf-8-sig'):
                ln = ln.rstrip('\r\n')
                if not ln.strip() or ln.lstrip().startswith('#') or '=' not in ln:
                    continue
                k, v = ln.split('=', 1)
                if v.startswith(' '):
                    v = v[1:]
                v = v.replace('\\n', '\n').replace('\\t', '\t')
                UI_TEXTS[k.strip()] = v
            return
        except Exception:
            pass

def T(key, *args):
    s = UI_TEXTS.get(key) or DEFAULT_TEXTS.get(key) or key
    if not args:
        return s
    try:
        return s.format(*args)
    except Exception:
        d = DEFAULT_TEXTS.get(key) or key
        try:
            return d.format(*args)
        except Exception:
            return d


def _ensure_telethon():
    """惰性导入 telethon + TL 补丁(首次连接/操作账号时加载,省 GUI 启动约 2s)。"""
    if 'TelegramClient' in globals():
        return
    try:
        import telethon as _telethon
        from telethon import functions
        from telethon.sessions import StringSession
        from telethon.errors import FloodWaitError
        from telethon.tl.functions.contacts import BlockRequest
        from telethon.tl.functions.channels import LeaveChannelRequest
        from telethon.tl.functions.messages import DeleteChatUserRequest
    except ImportError:
        print(T('t002'))
        sys.exit(1)
    # Telethon 1.44 新版 message 构造体补丁(服务器 schema 已更新,库还没跟进),失败不影响
    try:
        import tl_patch
        tl_patch.apply()
    except Exception as _e:
        print(T('t001', _e))
    globals()['TelegramClient'] = _telethon.TelegramClient
    globals()['functions'] = functions
    globals()['StringSession'] = StringSession
    globals()['FloodWaitError'] = FloodWaitError
    globals()['BlockRequest'] = BlockRequest
    globals()['LeaveChannelRequest'] = LeaveChannelRequest
    globals()['DeleteChatUserRequest'] = DeleteChatUserRequest

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# ============ 工作目录 ============
IS_FROZEN = getattr(sys, 'frozen', False)

if IS_FROZEN:
    # PyInstaller 打包: exe 所在目录既是数据目录(白名单/日志/备份/界面文本),
    # 也是账号根目录(扫描 exe 旁的各账号文件夹)
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
    WORKDIR = SCRIPT_DIR
else:
    # 源码运行: 工具箱目录为数据目录,当前目录(bat 所在)为账号检测基准
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    WORKDIR = os.getcwd()

LOG_DIR = os.path.join(SCRIPT_DIR, 'logs')
BACKUP_DIR = os.path.join(SCRIPT_DIR, 'backups')
_load_ui_texts()   # 界面文本: 编辑 界面文本.txt 自定义,删除即恢复默认

# ============ 配置 ============
USER_WHITELIST = {5434838648, 6775358409, 238879089}   # 联系人/对话永不删
GROUP_WHITELIST = {2284618069}                         # 永不退出的群/频道
DEFAULT_USER_WHITELIST = set(USER_WHITELIST)           # 恢复默认用
DEFAULT_GROUP_WHITELIST = set(GROUP_WHITELIST)

# 官方/认证实体硬保护(与白名单同级,永不删/退/拉黑)
OFFICIAL_SERVICE_IDS = {777000, 42777}   # Telegram 官方服务通知 / 官方支持


def is_official(e):
    """官方/认证实体判定: verified 认证标志(带蓝勾的官方频道/账号)或 Telegram 官方服务账号。"""
    if getattr(e, 'verified', False):
        return True
    return getattr(e, 'id', 0) in OFFICIAL_SERVICE_IDS
WHITELIST_FILE = os.path.join(SCRIPT_DIR, 'whitelist.json')   # 自定义白名单存这里


def load_whitelist():
    """从 whitelist.json 加载自定义白名单(没有则用代码里的默认值)。"""
    global USER_WHITELIST, GROUP_WHITELIST
    if os.path.isfile(WHITELIST_FILE):
        try:
            data = json.load(open(WHITELIST_FILE, encoding='utf-8'))
            USER_WHITELIST = set(int(x) for x in data.get('users', []))
            GROUP_WHITELIST = set(int(x) for x in data.get('groups', []))
            log(T('t003', len(USER_WHITELIST), len(GROUP_WHITELIST)))
            return
        except Exception as e:
            log(T('t004', e))
    USER_WHITELIST = set(DEFAULT_USER_WHITELIST)
    GROUP_WHITELIST = set(DEFAULT_GROUP_WHITELIST)


def save_whitelist():
    try:
        json.dump({'users': sorted(USER_WHITELIST), 'groups': sorted(GROUP_WHITELIST)},
                  open(WHITELIST_FILE, 'w', encoding='utf-8'), indent=1)
    except Exception as e:
        log(T('t005', e))


async def manage_whitelist(client, me):
    """白名单管理界面: 列表/添加/移除/恢复默认。改完全局生效并持久化。"""
    global USER_WHITELIST, GROUP_WHITELIST

    async def resolve_user(s):
        """输入支持: 纯数字ID 或 @用户名;返回 User 实体或 None。"""
        s = s.strip().lstrip('+')
        if s.isdigit():
            try:
                return await client.get_entity(int(s))
            except Exception:
                return None
        if s.startswith('@'):
            try:
                return await client.get_entity(s)
            except Exception:
                return None
        return None

    while True:
        print('\n' + '=' * 50)
        print(T('t006'))
        print('=' * 50)
        print(T('t007', len(USER_WHITELIST)))
        for i, uid in enumerate(sorted(USER_WHITELIST), 1):
            tag = T('t008') if uid in DEFAULT_USER_WHITELIST else ''
            print(f'    [{i}] {uid} {tag}')
        print(T('t009', len(GROUP_WHITELIST)))
        for i, gid in enumerate(sorted(GROUP_WHITELIST), 1):
            tag = T('t010') if gid in DEFAULT_GROUP_WHITELIST else ''
            print(f'    [{i}] {gid} {tag}')
        print('-' * 50)
        print(T('t011'))
        print(T('t012'))
        print(T('t013'))
        print(T('t014'))
        print('=' * 50)
        try:
            c = input(T('t015')).strip()
        except EOFError:
            c = '0'
        if c == '0':
            return
        elif c == '1':
            s = input(T('t016')).strip()
            u = await resolve_user(s)
            if u is None:
                log(T('t017'))
                continue
            if getattr(u, 'bot', False):
                log(T('t018', u.id))
                continue
            USER_WHITELIST.add(u.id)
            save_whitelist()
            log(T('t019', u.id, u.first_name or '', u.last_name or '').rstrip())
        elif c == '2':
            s = input(T('t020')).strip().lstrip('+')
            if s.isdigit() and int(s) in USER_WHITELIST:
                USER_WHITELIST.discard(int(s))
                save_whitelist()
                log(T('t021', s))
            else:
                log(T('t022'))
        elif c == '3':
            s = input(T('t023')).strip()
            g = await resolve_user(s)
            if g is None:
                log(T('t024'))
                continue
            GROUP_WHITELIST.add(g.id)
            save_whitelist()
            log(T('t025', g.id, getattr(g, 'title', '')).rstrip())
        elif c == '4':
            s = input(T('t026')).strip().lstrip('+')
            if s.isdigit() and int(s) in GROUP_WHITELIST:
                GROUP_WHITELIST.discard(int(s))
                save_whitelist()
                log(T('t027', s))
            else:
                log(T('t028'))
        elif c == '5':
            try:
                ans = input(T('t029')).strip().lower()
            except EOFError:
                ans = ''
            if ans == 'y':
                USER_WHITELIST = set(DEFAULT_USER_WHITELIST)
                GROUP_WHITELIST = set(DEFAULT_GROUP_WHITELIST)
                save_whitelist()
                log(T('t030'))
        else:
            log(T('t031'))
CONTACT_BATCH = 50
CONTACT_BATCH_DELAY = (5, 10)      # 联系人批间(默认档基准,运行时按速度档缩放)
CONTACT_ROUND_DELAY = (20, 40)     # 联系人轮间(默认档基准,运行时按速度档缩放)
DIALOG_DELAY = (2.2, 2.8)          # 对话动作间隔(运行时按速度档覆盖)

# 速度档: (名称, 对话动作间隔, 联系人批间/轮间缩放系数)
# 系数 = 该档对话间隔中值 / 默认档中值;默认档(1.0)时联系人节奏与旧版一致
SPEED_PRESETS = [
    (T('t032'), (0.2, 0.4), 0.26),
    (T('t033'), (0.4, 0.6), 0.45),
    (T('t034'), (0.9, 1.4), 1.0),
    (T('t035'), (1.3, 1.6), 1.30),
    (T('t036'), (1.9, 2.2), 1.85),
]
OFFICIAL_URL = 'https://telegram.org/dl/desktop/win64_portable'
GH_API = 'https://api.github.com/repos/telegramdesktop/tdesktop/releases/latest'
EXE_NAMES = ('Telegram.exe', 'Updater.exe')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0 Safari/537.36'
PROXIES = [None, 'http://127.0.0.1:7890', 'http://127.0.0.1:7897',
           'http://127.0.0.1:10809', 'http://127.0.0.1:1080']

# ============ 日志 + 进度条 ============
LOGFILE = None


def init_log():
    global LOGFILE
    logdir = LOG_DIR
    try:
        os.makedirs(logdir, exist_ok=True)
    except Exception:
        logdir = WORKDIR
    ts = time.strftime('%Y%m%d-%H%M%S')
    path = os.path.join(logdir, f'tg-tool-{ts}.log')
    try:
        LOGFILE = open(path, 'w', encoding='utf-8')
    except Exception:
        LOGFILE = None
    return path


_PHONE_RE = re.compile(r'(?<!\d)(\+?\d{1,3}[-\s]?)?(\d{3})\d{4}(\d{4})(?!\d)')


def _mask_phone_text(s):
    """日志里对手机号打码: 13812345678 -> 138****5678。"""
    try:
        return _PHONE_RE.sub(lambda m: f"{m.group(1) or ''}{m.group(2)}****{m.group(3)}", s)
    except Exception:
        return s


# UI 日志回调(Web 版由 server 挂接,把 log() 的行广播到前端日志页)
UI_LOG_HOOK = None


def log(msg):
    if not isinstance(msg, str):
        msg = str(msg)
    msg = _mask_phone_text(msg)
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    try:
        print(line, flush=True)
    except Exception:
        pass   # windowed 打包时无 stdout,忽略
    if LOGFILE:
        try:
            LOGFILE.write(line + '\n')
            LOGFILE.flush()
        except Exception:
            pass
    if UI_LOG_HOOK:
        try:
            UI_LOG_HOOK(msg)
        except Exception:
            pass


def pbar(done, total, width=20):
    """文本进度条片段,如 [======>------] 60.0%。"""
    if total <= 0:
        return ''
    pct = done / total * 100
    filled = int(width * done / total)
    if done >= total:
        bar = '=' * width
    else:
        bar = '=' * max(filled - 1, 0) + '>' + '-' * (width - filled)
    return f'[{bar}] {pct:5.1f}%'


def die(msg):
    log('!! ' + msg)
    # CLI 交互模式才暂停;引擎线程/窗口化 exe(stdin=None)里 input() 会抛
    # RuntimeError: lost sys.stdin —— 静默直接退出
    if sys.stdin is not None:
        try:
            input(T('t037'))
        except (EOFError, RuntimeError):
            pass
    sys.exit(1)


# ============ 账号检测 / 登录 ============

def _is_account_json(p):
    try:
        cfg = json.load(open(p, encoding='utf-8'))
        return isinstance(cfg, dict) and 'app_id' in cfg and 'app_hash' in cfg
    except Exception:
        return False


def _account_jsons(d):
    return [f for f in glob.glob(os.path.join(d, '*.json'))
            if not os.path.basename(f).startswith(('contacts-backup', 'dialogs-backup', 'shortcut'))
            and _is_account_json(f)]


def _is_tdata_only(d):
    """只有 tdata、没有 json 也没有 .session 的账号文件夹。"""
    if not os.path.isdir(os.path.join(d, 'tdata')):
        return False
    if _account_jsons(d):
        return False
    if glob.glob(os.path.join(d, '*.session')):
        return False
    return True


def _convert_tdata(account_dir):
    """把 tdata 登录态转成 .session + .json,让工具箱能操作。返回 True 成功。"""
    folder = os.path.basename(os.path.abspath(account_dir))
    try:
        from opentele.td import TDesktop
        from opentele.api import UseCurrentSession
    except ImportError:
        log(T('t038'))
        return False
    session_path = os.path.join(account_dir, folder + '.session')
    try:
        tdesk = TDesktop(os.path.join(account_dir, 'tdata'))
        if not tdesk.isLoaded():
            return False

        async def do():
            client = await tdesk.ToTelethon(session=session_path, flag=UseCurrentSession)
            await client.connect()
            try:
                if await client.is_user_authorized():
                    return await client.get_me()
                return None
            finally:
                await client.disconnect()

        me = asyncio.run(do())
        if me is None:
            return False
        cfg = {
            'phone': getattr(me, 'phone', '') or '',
            'session_file': folder + '.session',
            'app_id': 2040,
            'app_hash': 'b18441a1ff607e10a989891a5462e627',
            'device': 'PC',
            'sdk': 'Windows',
            'app_version': '6.6.4 x64',
            'user_id': str(me.id),
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
        }
        json.dump(cfg, open(os.path.join(account_dir, folder + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        log(T('t039', folder, cfg['phone'], me.first_name or '', me.last_name or '', me.id))
        return True
    except BaseException as e:
        if 'No account has been loaded' in str(e):
            return False   # 空 tdata(账号已登出/注销),静默跳过,不报错
        log(T('t040', folder, type(e).__name__, str(e)[:100]))
        return False


def make_json_from_session(account_dir, session_path):
    """自愈: 有 .session 但缺凭据 json 的账号,用官方默认凭据连接拉 me 补写 json。
    返回 True 成功。"""
    import asyncio
    stem = os.path.splitext(os.path.basename(session_path))[0]
    try:
        from telethon import TelegramClient

        async def do():
            client = TelegramClient(
                session_path[:-len('.session')], 2040,
                'b18441a1ff607e10a989891a5462e627',
                device_model='PC', system_version='Windows', app_version='6.6.4 x64')
            await client.connect()
            try:
                if not await client.is_user_authorized():
                    return None
                return await client.get_me()
            finally:
                await client.disconnect()

        me = asyncio.run(do())
        if me is None:
            return False
        cfg = {
            'phone': getattr(me, 'phone', '') or '',
            'session_file': os.path.basename(session_path),
            'app_id': 2040,
            'app_hash': 'b18441a1ff607e10a989891a5462e627',
            'device': 'PC',
            'sdk': 'Windows',
            'app_version': '6.6.4 x64',
            'user_id': str(me.id),
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': getattr(me, 'username', '') or '',
        }
        json.dump(cfg, open(os.path.join(account_dir, stem + '.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)
        log(T('t167', stem, cfg['phone'], me.first_name or '', me.last_name or '', me.id))
        return True
    except BaseException as e:
        log(f'[!] {os.path.basename(session_path)} 补建 json 失败: {type(e).__name__}: {str(e)[:80]}')
        return False


def reconcile_converted_json(account_dir):
    """_convert_tdata 会按【文件夹名】写出 .session/.json;若账号原有的
    json/session 用的是别的名字,把新 session 改回原名、me 信息合并进原 json、
    删除多余的新 json,保证命名与先前一致。返回最终 session 文件名。"""
    import glob as _g
    folder = os.path.basename(os.path.abspath(account_dir))
    new_json = os.path.join(account_dir, folder + '.json')
    new_sess = os.path.join(account_dir, folder + '.session')
    if not os.path.isfile(new_json):
        return None
    try:
        new_cfg = json.load(open(new_json, encoding='utf-8'))
    except Exception:
        return folder + '.session'
    orig_json = None
    for f in _account_jsons(account_dir):
        if os.path.abspath(f) != os.path.abspath(new_json):
            orig_json = f
            break
    # 原命名: 原 json 的 session_file > 残留旧 session 文件名 > 无(保持 folder 命名)
    orig_stem = None
    if orig_json:
        try:
            sf = json.load(open(orig_json, encoding='utf-8')).get('session_file') or ''
            if sf:
                orig_stem = os.path.splitext(os.path.basename(sf))[0]
        except Exception:
            pass
    if not orig_stem:
        olds = [f for f in _g.glob(os.path.join(account_dir, '*.session'))
                if os.path.abspath(f) != os.path.abspath(new_sess)]
        if olds:
            orig_stem = os.path.splitext(os.path.basename(olds[0]))[0]
    if orig_json is None and not orig_stem:
        return folder + '.session'   # 全新账号: 保持文件夹命名
    target_stem = orig_stem or os.path.splitext(os.path.basename(orig_json))[0]
    # session 改回原名
    if target_stem != folder and os.path.isfile(new_sess):
        target_sess = os.path.join(account_dir, target_stem + '.session')
        if os.path.isfile(target_sess):
            os.remove(target_sess)
        os.replace(new_sess, target_sess)
        new_cfg['session_file'] = target_stem + '.session'
    if orig_json:
        # 合并 me 信息进原 json,删除转换产生的多余 json
        try:
            old_cfg = json.load(open(orig_json, encoding='utf-8'))
        except Exception:
            old_cfg = {}
        for k in ('phone', 'user_id', 'first_name', 'last_name', 'username'):
            if new_cfg.get(k):
                old_cfg[k] = new_cfg[k]
        if new_cfg.get('session_file'):
            old_cfg['session_file'] = new_cfg['session_file']
        json.dump(old_cfg, open(orig_json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        if os.path.isfile(new_json):
            os.remove(new_json)
    elif target_stem != folder:
        # 无原 json: 新 json 改名为原 session 同名
        dst = os.path.join(account_dir, target_stem + '.json')
        if os.path.isfile(dst):
            os.remove(dst)
        os.replace(new_json, dst)
    return new_cfg.get('session_file') or (target_stem + '.session')


def detect_mode():
    """返回 (mode, account_dirs)。mode: 'single' / 'multi'。
    自动检测并转换"只有 tdata"的账号,让它们也能被操作。"""
    if _account_jsons(WORKDIR):
        return 'single', [WORKDIR]
    dirs = []
    tdata_only = []
    for sub in sorted(os.listdir(WORKDIR)):
        d = os.path.join(WORKDIR, sub)
        if not os.path.isdir(d):
            continue
        if _account_jsons(d):
            dirs.append(d)
        elif _is_tdata_only(d):
            tdata_only.append(d)
    if tdata_only:
        log(T('t041', len(tdata_only)))
        for d in tdata_only:
            if _convert_tdata(d):
                dirs.append(d)
    return 'multi', dirs


def find_cfg(account_dir):
    js = _account_jsons(account_dir)
    if not js:
        die(T('t042', account_dir))
    if len(js) > 1:
        die(T('t043') + '\n  '.join(js))
    return os.path.abspath(js[0]), json.load(open(js[0], encoding='utf-8'))


# ================= 代理 =================
# 优先级: settings.json 的 proxy 字段 > 系统代理(注册表) > 直连
# proxy 字段: {"mode":"system"} 或 {"mode":"none"} 或
#             {"mode":"manual","scheme":"socks5","host":"127.0.0.1","port":7890}
PROXY_CFG = {'mode': 'system'}       # 默认: 自动检测系统代理


def load_proxy_cfg():
    global PROXY_CFG
    p = os.path.join(SCRIPT_DIR, 'settings.json')
    try:
        cfg = json.load(open(p, encoding='utf-8'))
        if isinstance(cfg.get('proxy'), dict):
            PROXY_CFG = cfg['proxy']
    except Exception:
        pass


def detect_system_proxy():
    """注册表检测系统代理(仅 ProxyEnable/ProxyServer,支持 socks= 前缀)。"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')
        enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
        if not enable:
            return None
        server, _ = winreg.QueryValueEx(key, 'ProxyServer')
        server = server or ''
        # 形如 "socks=127.0.0.1:7890" 或 "http=...;https=..." 或 "127.0.0.1:7890"
        for part in server.split(';'):
            part = part.strip()
            if '=' in part:
                scheme, addr = part.split('=', 1)
                if scheme.lower() in ('socks', 'socks5', 'socks4', 'http', 'https'):
                    m = (scheme.lower().replace('socks', 'socks'), addr)
                    return m
            elif part:
                return ('http', part)
        return None
    except Exception:
        return None


def resolve_proxy():
    """返回 Telethon proxy 参数或 None。"""
    mode = PROXY_CFG.get('mode', 'system')
    if mode == 'none':
        return None
    if mode == 'manual':
        scheme = PROXY_CFG.get('scheme', 'socks5')
        return (scheme, PROXY_CFG['host'], int(PROXY_CFG['port']))
    # system
    m = detect_system_proxy()
    if m:
        return (m[0], m[1].split(':')[0], int(m[1].split(':')[1]))
    return None


def make_client(cfg_path, cfg):
    _ensure_telethon()
    base = os.path.dirname(cfg_path)
    stem = os.path.splitext(os.path.basename(cfg_path))[0]
    kw = dict(device_model=cfg.get('device') or 'PC',
              system_version=cfg.get('sdk') or 'Windows',
              app_version=cfg.get('app_version') or '6.6.4 x64')
    sess = None
    for name in (os.path.basename(cfg.get('session_file') or ''), stem + '.session'):
        if name and os.path.isfile(os.path.join(base, name)):
            sess = os.path.join(base, name)
            break
    if sess is None:
        found = sorted(glob.glob(os.path.join(base, '*.session')))
        if len(found) == 1:
            sess = found[0]
        elif len(found) > 1:
            die(T('t044') + '\n  '.join(found))
    if sess:
        log(T('t045', os.path.basename(sess)))
        proxy = resolve_proxy()
        if proxy:
            log(f'代理: {proxy[0]}://{proxy[1]}:{proxy[2]}')
            if proxy[0].startswith('socks') and not _HAS_SOCKS:
                log('  [!] socks 代理需要 python-socks,已忽略代理改直连')
                proxy = None
        return TelegramClient(sess[:-len('.session')], cfg['app_id'], cfg['app_hash'],
                               proxy=proxy, **kw)
    if cfg.get('session_str'):
        log(T('t046'))
        proxy = resolve_proxy()
        if proxy:
            log(f'代理: {proxy[0]}://{proxy[1]}:{proxy[2]}')
            if proxy[0].startswith('socks') and not _HAS_SOCKS:
                log('  [!] socks 代理需要 python-socks,已忽略代理改直连')
                proxy = None
        return TelegramClient(StringSession(cfg['session_str']), cfg['app_id'],
                              cfg['app_hash'], proxy=proxy, **kw)
    die(T('t047', base))


try:
    import python_socks  # noqa: F401
    _HAS_SOCKS = True
except ImportError:
    _HAS_SOCKS = False


async def connect_account(account_dir):
    """连接并校验账号。返回 (client, me) 或 (None, None)。"""
    cfg_path, cfg = find_cfg(account_dir)
    client = make_client(cfg_path, cfg)
    await client.connect()
    if not await client.is_user_authorized():
        log(T('t048'))
        await client.disconnect()
        return None, None
    me = await client.get_me()
    expect = cfg.get('user_id')
    if expect and str(me.id) != str(expect):
        log(T('t049', expect, me.id))
        await client.disconnect()
        return None, None
    log(T('t050', cfg.get('phone') or me.phone, me.first_name or '', me.last_name or '').rstrip())
    return client, me


def pick_speed():
    """进入账号工作区时询问速度档,应用为本次会话的全局间隔。返回档名或 None。"""
    global DIALOG_DELAY, CONTACT_BATCH_DELAY, CONTACT_ROUND_DELAY
    print('\n' + '-' * 50)
    print(T('t051'))
    for i, (name, rng, _k) in enumerate(SPEED_PRESETS, 1):
        print(f'  [{i}] {name}  {rng[0]}~{rng[1]}s')
    print('-' * 50)
    try:
        c = input(T('t052')).strip()
    except EOFError:
        c = ''
    if not c:
        c = '3'
    if c.isdigit() and 1 <= int(c) <= len(SPEED_PRESETS):
        name, rng, k = SPEED_PRESETS[int(c) - 1]
    else:
        name, rng, k = SPEED_PRESETS[2]
    DIALOG_DELAY = rng
    CONTACT_BATCH_DELAY = (round(5 * k, 1), round(10 * k, 1))
    CONTACT_ROUND_DELAY = (round(20 * k, 1), round(40 * k, 1))
    log(T('t053', name, rng[0], rng[1], CONTACT_BATCH_DELAY[0], CONTACT_BATCH_DELAY[1], CONTACT_ROUND_DELAY[0], CONTACT_ROUND_DELAY[1]))
    return name


async def account_workspace(account_dir, account_dirs, mode):
    """进入某账号的工作区: 连接一次,循环执行操作,直到用户选 [9] 换号 或 [0] 退出。
    返回 'switch' 表示要换号, 'quit' 表示退出程序。"""
    client, me = await connect_account(account_dir)
    if not client:
        print(T('t054'), end='', flush=True)
        try:
            input()
        except EOFError:
            pass
        return 'switch' if len(account_dirs) > 1 else 'quit'
    try:
        while True:
            print('\n' + '=' * 50)
            print(T('t055', os.path.basename(account_dir)))
            print('=' * 50)
            print(T('t056'))
            print(T('t057'))
            print(T('t058'))
            print(T('t059'))
            if len(account_dirs) > 1:
                print(T('t060'))
            print(T('t061'))
            print('=' * 50)
            try:
                choice = input(T('t062')).strip()
            except EOFError:
                choice = '0'
            if choice == '0':
                return 'quit'
            elif choice == '9' and len(account_dirs) > 1:
                return 'switch'
            elif choice == '3':
                task_update_telegram()
            elif choice == '4':
                await manage_whitelist(client, me)
            elif choice in ('1', '2'):
                try:
                    pick_speed()
                    if choice == '1':
                        await task_delete_contacts(client, me)
                    else:
                        await task_delete_dialogs(client, me)
                except Exception as e:
                    log(T('t063', type(e).__name__, e))
            else:
                log(T('t064'))
    finally:
        await client.disconnect()


# ============ 任务1: 删除联系人 ============

async def task_delete_contacts(client, me):
    _ensure_telethon()
    log(T('t065'))
    res = await client(functions.contacts.GetContactsRequest(hash=0))
    all_users = [u for u in res.users if u.id != me.id]
    users = [u for u in all_users if u.id not in USER_WHITELIST and not is_official(u)]
    wl = [u for u in all_users if u.id in USER_WHITELIST]
    official = [u for u in all_users if is_official(u)]
    log(T('t066', len(all_users), len(wl), len(users)))
    if official:
        log(T('t152', len(official)))
    for u in wl:
        log(T('t067', u.first_name or '', u.last_name or '', u.id).rstrip())
    if not users:
        log(T('t068'))
        return

    try:
        ans = input(T('t069', len(users))).strip().lower()
    except EOFError:
        ans = ''
    if ans != 'y':
        log(T('t070'))
        return

    # 备份
    ts = time.strftime('%Y%m%d-%H%M%S')
    bfile = os.path.join(BACKUP_DIR, f'contacts-backup-{ts}.json')
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except Exception:
        bfile = os.path.join(SCRIPT_DIR, f'contacts-backup-{ts}.json')
    json.dump([{'id': u.id, 'first_name': u.first_name, 'last_name': u.last_name or '',
                'username': u.username or '', 'phone': u.phone or ''} for u in users],
              open(bfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log(T('t071', len(users), os.path.basename(bfile)))

    total = 0
    for rnd in range(3):
        res = await client(functions.contacts.GetContactsRequest(hash=0))
        ids = [u.id for u in res.users if u.id != me.id and u.id not in USER_WHITELIST and not is_official(u)]
        if not ids:
            break
        log(T('t072', rnd + 1, len(ids)))
        batches = (len(ids) + CONTACT_BATCH - 1) // CONTACT_BATCH
        for bi in range(0, len(ids), CONTACT_BATCH):
            batch = ids[bi:bi + CONTACT_BATCH]
            ok = False
            for attempt in range(3):
                try:
                    await client(functions.contacts.DeleteContactsRequest(id=batch))
                    total += len(batch)
                    ok = True
                    break
                except FloodWaitError as e:
                    w = min(e.seconds, 600)
                    log(T('t073', w)); await asyncio.sleep(w + 1)
                except Exception as e:
                    if attempt == 2:
                        log(T('t074', e))
                    await asyncio.sleep(3)
            if ok:
                bnum = bi // CONTACT_BATCH + 1
                log(T('t075', pbar(bnum, batches), total, len(ids)))
            if bi + CONTACT_BATCH < len(ids):
                w = random.uniform(*CONTACT_BATCH_DELAY)
                log(T('t076', w))
                await asyncio.sleep(w)
        if rnd < 2:
            r = await client(functions.contacts.GetContactsRequest(hash=0))
            remain = [u.id for u in r.users
                      if u.id != me.id and u.id not in USER_WHITELIST and not is_official(u)]
            if remain:
                w = random.uniform(*CONTACT_ROUND_DELAY)
                log(T('t077', w))
                await asyncio.sleep(w)
            else:
                break

    res2 = await client(functions.contacts.GetContactsRequest(hash=0))
    left = [u for u in res2.users if u.id != me.id and u.id not in USER_WHITELIST and not is_official(u)]
    kept = [u for u in res2.users if u.id in USER_WHITELIST]
    log(T('t078', total, len(left), len(kept)))


# ============ 任务2: 删除对话 ============

async def _analyze_dialogs(client, me):
    """拉取全部对话(含归档)并分类。规则: 只有白名单不删,其余全删。"""
    log(T('t079'))
    dialogs = await client.get_dialogs(limit=None)
    try:
        archived = await client.get_dialogs(limit=None, archived=True)
        dialogs += archived
        if archived:
            log(T('t080', len(archived)))
    except Exception as e:
        log(T('t081', e))
    log(T('t082', len(dialogs)))

    users, bots, deleted, groups, keep_users, keep_groups = [], [], [], [], [], []
    official_kept = 0
    for d in dialogs:
        e = d.entity
        eid = getattr(e, 'id', None)
        if eid == me.id:
            keep_users.append(d)          # 自己的收藏夹(Saved Messages),不动
        elif eid in USER_WHITELIST:
            keep_users.append(d)          # 用户白名单,永不删
        elif d.is_user:
            if is_official(e):
                keep_users.append(d)      # 官方/认证账号,永不删
                official_kept += 1
            elif getattr(e, 'bot', False):
                bots.append(d)
            elif getattr(e, 'deleted', False) or getattr(e, 'first_name', None) == 'Deleted Account':
                deleted.append(d)
            else:
                users.append(d)
        elif d.is_group or d.is_channel:
            if eid in GROUP_WHITELIST:
                keep_groups.append(d)     # 群白名单,永不退
            elif is_official(e):
                keep_groups.append(d)     # 官方/认证频道,永不退
                official_kept += 1
            else:
                groups.append(d)

    if official_kept:
        log(T('t152', official_kept))
    log(T('t083', len(dialogs), len(users), len(deleted), len(bots), len(groups), len(keep_users) + len(keep_groups)))
    return users, bots, deleted, groups, keep_users, keep_groups, dialogs


def _dlbl(d):
    e = d.entity
    if d.is_user:
        name = ((e.first_name or '') + ' ' + (e.last_name or '')).strip()
        return f'{name or "无名字"}(id={e.id})'
    return f'{getattr(e, "title", "") or "未命名"}(id={e.id})'


async def _backup_dialogs(items, tag):
    ts = time.strftime('%Y%m%d-%H%M%S')
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        fname = os.path.join(BACKUP_DIR, f'dialogs-backup-{tag}-{ts}.json')
    except Exception:
        fname = os.path.join(SCRIPT_DIR, f'dialogs-backup-{tag}-{ts}.json')
    rows = [{'id': getattr(d.entity, 'id', None), 'name': _dlbl(d)} for d in items]
    json.dump(rows, open(fname, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log(T('t084', len(rows), os.path.basename(fname)))


async def _run_dialog_action(client, items, desc, fn):
    _ensure_telethon()
    if not items:
        log(T('t085', desc))
        return
    total = len(items)
    done = 0
    for i, d in enumerate(items, 1):
        try:
            await fn(client, d)
            done += 1
            log(f'  {desc} {pbar(i, total)}  {_dlbl(d)}')
        except FloodWaitError as e:
            w = min(e.seconds, 300)
            log(T('t086', w)); await asyncio.sleep(w + 1)
        except Exception as e:
            log(T('t087', desc, i, total, _dlbl(d), e))
        await asyncio.sleep(random.uniform(*DIALOG_DELAY))
    log(T('t088', desc, done, total))


async def task_delete_dialogs(client, me):
    _ensure_telethon()
    users, bots, deleted, groups, keep_users, keep_groups, total_dialogs = await _analyze_dialogs(client, me)
    all_privates = users + deleted + bots   # 规则: 白名单之外全删;bot 额外拉黑

    print('=' * 50)
    print(T('t089', len(total_dialogs)))
    print('-' * 50)
    print(T('t090', len(all_privates), len(users), len(deleted), len(bots)))
    print(T('t091', len(groups)))
    print(T('t092'))
    print('-' * 50)
    print(T('t093'))
    for d in keep_groups:
        print(T('t094', _dlbl(d)))
    for d in keep_users:
        lbl = _dlbl(d)
        _kind = T('t095') if d.entity.id == me.id else T('t096')
        print(T('t097', _kind, lbl))
    print(T('t098'))
    print('=' * 50)
    try:
        choice = input(T('t099')).strip()
    except EOFError:
        choice = ''
    if choice not in ('1', '2', '3'):
        log(T('t100'))
        return

    async def del_user(client, d):
        await client.delete_dialog(d.entity, revoke=True)

    async def block_bot(client, d):
        await client.delete_dialog(d.entity, revoke=True)
        await client(BlockRequest(id=d.entity))

    async def do_groups():
        await _backup_dialogs(groups, 'groups')
        total = len(groups)
        done = 0
        for i, d in enumerate(groups, 1):
            try:
                if d.is_channel:
                    await client(LeaveChannelRequest(channel=d.entity))
                else:
                    await client(DeleteChatUserRequest(chat_id=d.entity.id, user_id='me'))
                done += 1
                log(T('t101', pbar(i, total), _dlbl(d)))
            except FloodWaitError as e:
                w = min(e.seconds, 300)
                log(T('t102', w)); await asyncio.sleep(w + 1)
            except Exception as e:
                log(T('t103', _dlbl(d), e))
                try:
                    await client.delete_dialog(d.entity, revoke=True)
                    done += 1
                    log(T('t104', pbar(i, total), _dlbl(d)))
                except Exception as e2:
                    log(T('t105', _dlbl(d), e2))
            await asyncio.sleep(random.uniform(*DIALOG_DELAY))
        log(T('t106', done, total))

    if choice in ('1', '3'):
        # 已注销和 bot 分开处理(要拉黑),普通私聊批量删
        await _backup_dialogs(all_privates, 'privates')
        await _run_dialog_action(client, deleted, T('t107'), del_user)
        await _run_dialog_action(client, bots, T('t108'), block_bot)
        await _run_dialog_action(client, users, T('t109'), del_user)
    if choice in ('2', '3'):
        await do_groups()
    log(T('t110'))


# ============ 任务3: 更新本体 ============

def _make_opener(proxy):
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    return urllib.request.build_opener()


def _attempt(url, dest, proxy=None):
    op = _make_opener(proxy)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with op.open(req, timeout=30) as resp, open(dest, 'wb') as f:
        final_url = resp.url
        total = int(resp.headers.get('Content-Length') or 0)
        done = 0
        shown = -1
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total and done // (10 * 1024 * 1024) != shown:
                shown = done // (10 * 1024 * 1024)
                log(T('t111', pbar(done // 1048576, total // 1048576)))
        return final_url, done


def _extract_version(s):
    base = os.path.basename((s or '').split('?')[0])
    m = re.search(r'(\d+(?:\.\d+){1,2})\.zip$', base)
    return m.group(1) if m else None


def _github_portable():
    for proxy in PROXIES:
        try:
            op = _make_opener(proxy)
            req = urllib.request.Request(GH_API, headers={'User-Agent': UA})
            with op.open(req, timeout=20) as r:
                data = json.load(r)
            for a in data.get('assets', []):
                n = a.get('name', '')
                if n.startswith('tportable') and n.endswith('.zip'):
                    return a.get('browser_download_url'), n, proxy
        except Exception:
            continue
    return None, None, None


def _find_targets():
    out = []
    for root, dirs, files in os.walk(WORKDIR):
        dirs[:] = [d for d in dirs if d.lower() not in ('tupdates', '$recycle.bin', '__pycache__')]
        for name in EXE_NAMES:
            if name in files:
                out.append(os.path.join(root, name))
    return out


def _under_workdir(path):
    d = os.path.normcase(os.path.dirname(os.path.abspath(path)))
    b = os.path.normcase(WORKDIR)
    return d == b or d.startswith(b + os.sep)


def _running_under_workdir():
    try:
        raw = subprocess.run(
            ['wmic', 'process', 'where', "name='Telegram.exe' or name='Updater.exe'",
             'get', 'ExecutablePath,ProcessId', '/value'],
            capture_output=True, timeout=60).stdout
    except Exception:
        return []
    text = raw.decode('mbcs', errors='replace') if raw else ''
    procs, path, pid = [], None, None
    for line in text.splitlines():
        k, _, v = line.partition('=')
        k = k.strip()
        if k == 'ExecutablePath':
            path = v.strip()
        elif k == 'ProcessId':
            pid = v.strip()
        if path is not None and pid is not None:
            if path and pid and _under_workdir(path):
                procs.append((pid, path))
            path = pid = None
    return procs


def _verify_telegram_signature(exe_path):
    """校验 Telegram.exe 的 Authenticode 代码签名(官方 Telegram FZ-LLC)。

    返回签名者 subject 字符串;校验失败/无签名/签名者非 Telegram 返回空串。
    """
    ps = (
        "$s = Get-AuthenticodeSignature '%s'; "
        "if ($s.Status -eq 'Valid' -and $s.SignerCertificate) "
        "{ $s.SignerCertificate.Subject } else { '' }" % exe_path
    )
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps],
            capture_output=True, timeout=60).stdout
        text = (out or b'').decode('utf-8', errors='replace').strip()
    except Exception:
        return ''
    if text and 'Telegram' in text:
        return text
    return ''


def task_update_telegram():
    log(T('t112', WORKDIR))
    targets = _find_targets()
    log(T('t113', len(targets)))
    for t in sorted(targets):
        sz = os.path.getsize(t) / 1048576
        log(f'  {os.path.relpath(t, WORKDIR)}  {sz:.0f} MB')

    try:
        ans = input(T('t114')).strip().lower()
    except EOFError:
        ans = ''
    if ans != 'y':
        log(T('t115'))
        return

    procs = _running_under_workdir()
    for pid, path in procs:
        log(T('t116', pid, os.path.relpath(path, WORKDIR)))
        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    if procs:
        time.sleep(2)

    tmp = tempfile.mkdtemp(prefix='tgupdate_')
    try:
        zip_path = os.path.join(tmp, 'tportable.zip')
        log(T('t117'))
        version = got = None
        for proxy in PROXIES:
            label = T('t118') if proxy is None else T('t119', proxy)
            try:
                log(T('t120', label))
                final_url, size = _attempt(OFFICIAL_URL, zip_path, proxy)
                got = (final_url, size)
                break
            except Exception as e:
                log(T('t121', str(e)[:100]))
        if not got:
            log(T('t122'))
            gh_url, gh_name, gh_proxy = _github_portable()
            if not gh_url:
                die(T('t123'))
            try:
                final_url, size = _attempt(gh_url, zip_path, gh_proxy)
                got = (gh_name, size)
            except Exception as e:
                die(T('t124', str(e)[:100]))
        final_url, size = got
        version = _extract_version(final_url)
        if size < 10 * 1024 * 1024:
            die(T('t125'))
        log(T('t126', size // 1048576) + (T('t127', version) if version else ''))

        try:
            zf = zipfile.ZipFile(zip_path)
            if zf.testzip() is not None:
                raise RuntimeError(T('t128'))
        except Exception as e:
            die(T('t129', e))

        members = {}
        for n in zf.namelist():
            bn = os.path.basename(n).lower()
            for want in EXE_NAMES:
                if bn == want.lower() and want not in members:
                    members[want] = n
        if 'Telegram.exe' not in members:
            die(T('t130'))

        ext = os.path.join(tmp, 'new')
        os.makedirs(ext)
        for want, member in members.items():
            zf.extract(member, ext)
            src = os.path.join(ext, member)
            dst = os.path.join(ext, want)
            if os.path.normcase(src) != os.path.normcase(dst):
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
        new_tg = os.path.join(ext, 'Telegram.exe')
        if os.path.getsize(new_tg) < 50 * 1024 * 1024:
            die(T('t131'))
        signer = _verify_telegram_signature(new_tg)
        if not signer:
            die('更新中止：Telegram.exe 代码签名校验失败（可能被篡改），已删除临时文件，未覆盖任何文件。')
        log(f'签名校验通过：{signer}')

        new_sizes = {w: os.path.getsize(os.path.join(ext, w))
                     for w in EXE_NAMES if os.path.isfile(os.path.join(ext, w))}

        log(T('t132'))
        ok = same = 0
        fail = []
        total = len(targets)
        for i, t in enumerate(sorted(targets), 1):
            want = os.path.basename(t)
            src = os.path.join(ext, want)
            relp = os.path.relpath(t, WORKDIR)
            if not os.path.isfile(src):
                log(T('t133', relp, want))
                continue
            try:
                if os.path.getsize(t) == new_sizes[want]:
                    same += 1
                    log(T('t134', relp))
                else:
                    os.chmod(t, 0o755)
                    shutil.copyfile(src, t)
                    ok += 1
                    log(T('t135', pbar(i, total), relp))
            except Exception as e:
                fail.append(relp)
                log(T('t136', relp, e))

        for want in EXE_NAMES:
            root_f = os.path.join(WORKDIR, want)
            if not os.path.isfile(root_f) and os.path.isfile(os.path.join(ext, want)):
                shutil.copyfile(os.path.join(ext, want), root_f)
                ok += 1
                log(T('t137', want))

        # 安装: 有登录态但没有客户端的账号文件夹,补一份便携版客户端
        installed = 0
        skip_dirs = {'工具箱', 'logs', 'backups', 'modules', 'tupdates',
                     '空白Telegram', '__pycache__', '_internal'}
        try:
            for sub in sorted(os.listdir(WORKDIR)):
                d = os.path.join(WORKDIR, sub)
                if not os.path.isdir(d) or sub in skip_dirs:
                    continue
                if os.path.isfile(os.path.join(d, 'Telegram.exe')):
                    continue   # 已有客户端,替换逻辑已处理
                has_data = (os.path.isdir(os.path.join(d, 'tdata'))
                            or glob.glob(os.path.join(d, '*.session'))
                            or _account_jsons(d))
                if not has_data:
                    continue   # 不是账号文件夹
                for want in EXE_NAMES:
                    src = os.path.join(ext, want)
                    if os.path.isfile(src):
                        shutil.copyfile(src, os.path.join(d, want))
                        installed += 1
                log(T('t173', sub))
        except Exception as e:
            log(f'[!] 客户端补装步骤出错: {type(e).__name__}: {e}')

        log(T('t138', ok, same, len(fail)))
        log(T('t139', version or '未识别'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============ 主流程 ============

def _match_accounts(account_dirs, query):
    """按 文件夹名/手机号/uid 模糊匹配,返回 (账号目录, 显示名) 列表。
    大小写不敏感,子串匹配;空查询返回全部。"""
    q = query.strip().lower()
    if not q:
        return []
    result = []
    for d in account_dirs:
        _, cfg = find_cfg(d)
        name = os.path.basename(d)
        phone = str(cfg.get('phone', '') or '')
        uid = str(cfg.get('user_id', '') or '')
        if q in name.lower() or q in phone or q in uid:
            result.append((d, f'{name}  (+{cfg.get("phone", "?")}  uid={cfg.get("user_id", "?")})'))
    return result


def pick_account(account_dirs):
    print(T('t140'))
    for i, d in enumerate(account_dirs, 1):
        _, cfg = find_cfg(d)
        print(f'  [{i}] {os.path.basename(d)}  (+{cfg.get("phone", "?")}  uid={cfg.get("user_id", "?")})')
    print(T('t141'))
    try:
        c = input(T('t142')).strip()
    except EOFError:
        return None
    if c.isdigit() and 1 <= int(c) <= len(account_dirs):
        return account_dirs[int(c) - 1]
    if c in ('0', ''):
        return None
    # 模糊搜索
    matches = _match_accounts(account_dirs, c)
    if not matches:
        log(T('t143', c))
        return None
    if len(matches) == 1:
        d, disp = matches[0]
        log(T('t144', disp))
        return d
    # 多个匹配: 列出候选
    print(T('t145', len(matches)))
    for i, (d, disp) in enumerate(matches, 1):
        print(f'  [{i}] {disp}')
    try:
        c2 = input(T('t146')).strip()
    except EOFError:
        return None
    if c2.isdigit() and 1 <= int(c2) <= len(matches):
        return matches[int(c2) - 1][0]
    return None


def main():
    logpath = init_log()
    log(T('t147', logpath))
    load_whitelist()
    load_proxy_cfg()
    mode, account_dirs = detect_mode()
    if mode == 'single':
        log(T('t148', os.path.basename(account_dirs[0])))
    else:
        log(T('t149', len(account_dirs)))

    current = None   # 当前工作区账号目录;None = 还没选
    while True:
        # 单账号模式: 直接用唯一账号;多账号: 没选过就先选
        if mode == 'single':
            current = account_dirs[0]
        elif current is None:
            current = pick_account(account_dirs)
            if not current:
                log(T('t150'))
                break

        result = asyncio.run(account_workspace(current, account_dirs, mode))
        if result == 'quit':
            log(T('t151'))
            break
        # switch: 换号重选
        current = None

    if LOGFILE:
        LOGFILE.close()


if __name__ == '__main__':
    main()
