"""账号资料联网补全: username / 头像 / 真名 缓存到 工具箱\\profiles.json + avatars\\

GUI 打开后后台跑一遍: 对每个账号用已有 session 拉一次 get_me + 头像,
结果落盘缓存,下次启动离线秒开。失败不影响(条目退回首字母色块)。
"""
import asyncio
import glob
import json
import os
import sys
import threading

if getattr(sys, 'frozen', False):
    # PyInstaller 打包: 资料缓存/头像写到 exe 所在目录
    TOOLBOX = os.path.dirname(os.path.abspath(sys.executable))
else:
    TOOLBOX = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE = os.path.join(TOOLBOX, 'profiles.json')
AVATAR_DIR = os.path.join(TOOLBOX, 'avatars')

# 已知死号(登录态失效),不浪费时间连接
DEAD = {'xxxCeay', 'Racoro', '18296957526'}

# 电话区号 -> (两字母码, 中文名)  最长前缀匹配
PHONE_CODE_MAP = {
    '1': ('US', '美国'),      '7': ('RU', '俄罗斯'),
    '20': ('EG', '埃及'),     '27': ('ZA', '南非'),
    '30': ('GR', '希腊'),     '31': ('NL', '荷兰'),
    '32': ('BE', '比利时'),   '33': ('FR', '法国'),
    '34': ('ES', '西班牙'),   '36': ('HU', '匈牙利'),
    '39': ('IT', '意大利'),   '40': ('RO', '罗马尼亚'),
    '41': ('CH', '瑞士'),     '43': ('AT', '奥地利'),
    '44': ('GB', '英国'),     '45': ('DK', '丹麦'),
    '46': ('SE', '瑞典'),     '47': ('NO', '挪威'),
    '48': ('PL', '波兰'),     '49': ('DE', '德国'),
    '51': ('PE', '秘鲁'),     '52': ('MX', '墨西哥'),
    '53': ('CU', '古巴'),     '54': ('AR', '阿根廷'),
    '55': ('BR', '巴西'),     '56': ('CL', '智利'),
    '57': ('CO', '哥伦比亚'), '58': ('VE', '委内瑞拉'),
    '60': ('MY', '马来西亚'), '61': ('AU', '澳大利亚'),
    '62': ('ID', '印度尼西亚'), '63': ('PH', '菲律宾'),
    '64': ('NZ', '新西兰'),   '65': ('SG', '新加坡'),
    '66': ('TH', '泰国'),     '81': ('JP', '日本'),
    '82': ('KR', '韩国'),     '84': ('VN', '越南'),
    '86': ('CN', '中国'),     '90': ('TR', '土耳其'),
    '91': ('IN', '印度'),     '92': ('PK', '巴基斯坦'),
    '93': ('AF', '阿富汗'),   '94': ('LK', '斯里兰卡'),
    '95': ('MM', '缅甸'),     '98': ('IR', '伊朗'),
    '212': ('MA', '摩洛哥'),  '213': ('DZ', '阿尔及利亚'),
    '216': ('TN', '突尼斯'),  '218': ('LY', '利比亚'),
    '220': ('GM', '冈比亚'),  '234': ('NG', '尼日利亚'),
    '250': ('RW', '卢旺达'),  '251': ('ET', '埃塞俄比亚'),
    '252': ('SO', '索马里'),  '254': ('KE', '肯尼亚'),
    '255': ('TZ', '坦桑尼亚'), '256': ('UG', '乌干达'),
    '260': ('ZM', '赞比亚'),  '263': ('ZW', '津巴布韦'),
    '351': ('PT', '葡萄牙'),  '355': ('AL', '阿尔巴尼亚'),
    '370': ('LT', '立陶宛'),  '371': ('LV', '拉脱维亚'),
    '372': ('EE', '爱沙尼亚'), '373': ('MD', '摩尔多瓦'),
    '375': ('BY', '白俄罗斯'), '380': ('UA', '乌克兰'),
    '385': ('HR', '克罗地亚'), '387': ('BA', '波黑'),
    '389': ('MK', '北马其顿'), '420': ('CZ', '捷克'),
    '421': ('SK', '斯洛伐克'), '505': ('NI', '尼加拉瓜'),
    '506': ('CR', '哥斯达黎加'), '507': ('PA', '巴拿马'),
    '509': ('HT', '海地'),    '590': ('GP', '瓜德罗普'),
    '591': ('BO', '玻利维亚'), '592': ('GY', '圭亚那'),
    '593': ('EC', '厄瓜多尔'), '595': ('PY', '巴拉圭'),
    '596': ('MQ', '马提尼克'), '597': ('SR', '苏里南'),
    '598': ('UY', '乌拉圭'),  '670': ('TL', '东帝汶'),
    '672': ('NR', '瑙鲁'),    '673': ('BN', '文莱'),
    '675': ('PG', '巴布亚新几内亚'), '676': ('TO', '汤加'),
    '679': ('FJ', '斐济'),    '686': ('KI', '基里巴斯'),
    '852': ('HK', '香港'),    '853': ('MO', '澳门'),
    '855': ('KH', '柬埔寨'),  '856': ('LA', '老挝'),
    '880': ('BD', '孟加拉国'), '886': ('TW', '台湾'),
    '960': ('MV', '马尔代夫'), '961': ('LB', '黎巴嫩'),
    '962': ('JO', '约旦'),    '963': ('SY', '叙利亚'),
    '964': ('IQ', '伊拉克'),  '965': ('KW', '科威特'),
    '966': ('SA', '沙特'),    '967': ('YE', '也门'),
    '968': ('OM', '阿曼'),    '970': ('PS', '巴勒斯坦'),
    '971': ('AE', '阿联酋'),  '972': ('IL', '以色列'),
    '973': ('BH', '巴林'),    '974': ('QA', '卡塔尔'),
    '975': ('BT', '不丹'),    '976': ('MN', '蒙古'),
    '977': ('NP', '尼泊尔'),  '992': ('TJ', '塔吉克斯坦'),
    '993': ('TM', '土库曼斯坦'), '994': ('AZ', '阿塞拜疆'),
    '995': ('GE', '格鲁吉亚'), '996': ('KG', '吉尔吉斯斯坦'),
    '998': ('UZ', '乌兹别克斯坦'),
    '1242': ('BS', '巴哈马'), '1246': ('BB', '巴巴多斯'),
    '1264': ('AI', '安圭拉'), '1268': ('AG', '安提瓜'),
    '1345': ('KY', '开曼'),   '1473': ('GD', '格林纳达'),
    '1671': ('GU', '关岛'),   '1684': ('AS', '美属萨摩亚'),
    '1758': ('LC', '圣卢西亚'), '1767': ('DM', '多米尼克'),
    '1784': ('VC', '圣文森特'), '1868': ('TT', '特立尼达'),
    '1876': ('JM', '牙买加'),
}


def load_profiles():
    if os.path.isfile(PROFILE_FILE):
        try:
            return json.load(open(PROFILE_FILE, encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_profiles(prof):
    try:
        json.dump(prof, open(PROFILE_FILE, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass


def _ensure_avatar_dir():
    """保证 AVATAR_DIR 是目录。历史 bug 曾把一张头像直接写到 avatars 路径上,
    导致 makedirs(exist_ok=True) 抛 FileExistsError、所有头像下载失败。"""
    if os.path.isdir(AVATAR_DIR):
        return
    if os.path.exists(AVATAR_DIR):  # 是文件: 归档为 avatars.recovered.jpg 再建目录
        try:
            os.replace(AVATAR_DIR, AVATAR_DIR + '.recovered.jpg')
        except OSError:
            pass
    os.makedirs(AVATAR_DIR, exist_ok=True)


def avatar_path(name):
    # Telegram 头像本质是 JPEG,存 .jpg 避免 JPEG 字节塞进 .png 导致前端 content-type 不匹配
    _ensure_avatar_dir()
    return os.path.join(AVATAR_DIR, f'{name}.jpg')


# 白名单昵称缓存(联网验证用户时顺手记录)
NICK_FILE = os.path.join(TOOLBOX, 'nicknames.json')


def nickname_of(uid):
    try:
        d = json.load(open(NICK_FILE, encoding='utf-8'))
        return d.get(str(uid), '')
    except Exception:
        return ''


def save_nickname(uid, name):
    try:
        d = json.load(open(NICK_FILE, encoding='utf-8'))
    except Exception:
        d = {}
    d[str(uid)] = name
    try:
        json.dump(d, open(NICK_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass


def _iter_accounts(root):
    import tg_tool
    for sub in sorted(os.listdir(root)):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        js = tg_tool._account_jsons(d)
        if js:
            import glob as _g
            cfg = json.load(open(js[0], encoding='utf-8'))
            if cfg.get('session_str') or _g.glob(os.path.join(d, '*.session')):
                yield sub, d, js[0], cfg


async def _fetch_one(loop, name, d, cfg_path, cfg):
    """连接一个账号拉 get_me + 头像。返回 dict 或 None。"""
    import tg_tool
    # 应用 TL 构造体补丁(幂等): 冷启动直接刷新时引擎可能还没跑过 make_client
    try:
        import tl_patch
        tl_patch.apply()
    except Exception:
        pass
    from telethon import TelegramClient, functions
    try:
        from telethon.sessions import StringSession
    except Exception:
        StringSession = None
    base = os.path.dirname(cfg_path)
    kw = dict(device_model=cfg.get('device') or 'PC',
              system_version=cfg.get('sdk') or 'Windows',
              app_version=cfg.get('app_version') or '6.6.4 x64')
    proxy = tg_tool.resolve_proxy()
    if proxy and proxy[0].startswith('socks') and not tg_tool._HAS_SOCKS:
        proxy = None
    client = None
    sess = None
    for nm in (os.path.basename(cfg.get('session_file') or ''),
               os.path.splitext(os.path.basename(cfg_path))[0] + '.session'):
        if nm and os.path.isfile(os.path.join(base, nm)):
            sess = os.path.join(base, nm)
            break
    if sess is None:
        found = sorted(glob.glob(os.path.join(base, '*.session')))
        if len(found) == 1:
            sess = found[0]
    if sess:
        client = TelegramClient(sess[:-len('.session')], cfg['app_id'], cfg['app_hash'],
                                proxy=proxy, **kw)
    elif cfg.get('session_str') and StringSession:
        client = TelegramClient(StringSession(cfg['session_str']), cfg['app_id'],
                                cfg['app_hash'], proxy=proxy, **kw)
    if client is None:
        tg_tool.log(f'[资料] {name}: 无 session 文件且无 session_str,无法连接')
        return None
    try:
        await asyncio.wait_for(client.connect(), timeout=20)
        if not await asyncio.wait_for(client.is_user_authorized(), timeout=10):
            tg_tool.log(f'[资料] {name}: 登录态失效(session 过期或在别处被踢)')
            return None
        me = await asyncio.wait_for(client.get_me(), timeout=15)
        info = {
            'username': me.username or '',
            'first': me.first_name or '',
            'last': me.last_name or '',
            'phone': str(me.phone or ''),
            'uid': str(me.id),
            'dc': str(getattr(client.session, 'dc_id', '') or ''),
        }
        # 头像: 用 download_profile_photo(走 dc_id / InputPeerPhotoFileLocation,
        # 头像在别的 DC 也能拉),写入 .jpg 保持字节与扩展名一致
        try:
            os.makedirs(AVATAR_DIR, exist_ok=True)
            path = await asyncio.wait_for(
                client.download_profile_photo(me, avatar_path(name)), timeout=30)
            if path:
                info['avatar'] = path
        except Exception:
            pass
        return info
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=10)
        except Exception:
            pass


def _worker(root, on_update):
    """后台线程: 串行刷全部账号(每号间隔 1s 防风控),增量落盘。
    on_update 返回 True = 取消。已连接账号跳过(防 session 冲突)。
    全部结束后回调 on_update(None, None) 作为完成信号。"""
    prof = load_profiles()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for name, d, cfg_path, cfg in _iter_accounts(root):
            if name in DEAD:
                continue
            if on_update and on_update(name, None):   # 返回 True = 取消
                break
            try:
                info = loop.run_until_complete(
                    asyncio.wait_for(_fetch_one(loop, name, d, cfg_path, cfg), timeout=90))
            except Exception:
                info = None
            if info:
                # 本次没拉到新头像时保留旧缓存头像,避免重复刷新把已有图抹掉
                old = prof.get(name, {})
                if not info.get('avatar') and old.get('avatar'):
                    info['avatar'] = old['avatar']
                prof[name] = info
                save_profiles(prof)
            if on_update:
                on_update(name, info)
            loop.run_until_complete(asyncio.sleep(1.0))
    finally:
        loop.close()
    if on_update:
        try:
            on_update(None, None)   # 完成信号
        except Exception:
            pass


def start_refresh(root, on_update=None):
    """启动后台刷新线程。on_update(name, info) 每号回调一次(在 worker 线程执行)。"""
    t = threading.Thread(target=_worker, args=(root, on_update), daemon=True)
    t.start()
    return t


def refresh_one(root, name):
    """连接单个账号拉一次头像+资料,同步返回 info dict 或 None。"""
    import tg_tool
    js = tg_tool._account_jsons(os.path.join(root, name))
    if not js:
        tg_tool.log(f'[资料] {name}: 找不到账号 json(目录结构不符)')
        return None
    try:
        cfg = json.load(open(js[0], encoding='utf-8'))
    except Exception as e:
        tg_tool.log(f'[资料] {name}: json 解析失败 {type(e).__name__}: {e}')
        return None
    loop = asyncio.new_event_loop()
    try:
        info = loop.run_until_complete(
            asyncio.wait_for(_fetch_one(loop, name, os.path.join(root, name), js[0], cfg), timeout=90))
    except Exception as e:
        tg_tool.log(f'[资料] {name}: 连接/拉取失败 {type(e).__name__}: {e}')
        info = None
    finally:
        loop.close()
    if info:
        prof = load_profiles()
        old = prof.get(name, {})
        if not info.get('avatar') and old.get('avatar'):
            info['avatar'] = old['avatar']
        prof[name] = info
        save_profiles(prof)
    return info
