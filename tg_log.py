"""统一日志: 分级 + 按天文件 + 内存环形缓冲 + WebSocket 推送。

原来日志有两套写法: tg_tool.log 只写自己的文件, 引擎日志只广播不落盘,
重启后 Web 日志页全空。这里收敛成一条管线:

    log() -> 打码 -> 内存环形缓冲(供 /api/logs 回放)
                 -> logs/tg-tool-YYYYMMDD.log(按天追加, 保留 N 天)
                 -> sink(Web 端广播结构化条目)

级别: debug < info < warn < error。未显式指定的按关键字粗分(失败/异常 -> error)。
"""
import os
import re
import threading
import time
from collections import deque

LEVELS = {'debug': 10, 'info': 20, 'warn': 30, 'error': 40}
_LABEL = {10: 'DEBUG', 20: 'INFO', 30: 'WARN', 40: 'ERROR'}

_lock = threading.RLock()
_log_dir = ''
_keep_days = 14
_fh = None
_fh_day = ''
_ring = deque(maxlen=3000)
_sink = None
_path = ''

_PHONE_RE = re.compile(r'(?<!\d)(\+?\d{1,3}[-\s]?)?(\d{3})\d{4}(\d{4})(?!\d)')
_ERROR_WORDS = ('失败', '错误', '异常', 'Traceback', 'Exception', 'Error')
_WARN_WORDS = ('警告', '超时', '未找到', '重试', '不可用')


def mask(text):
    """日志里的手机号打码: 13812345678 -> 138****5678。"""
    try:
        return _PHONE_RE.sub(lambda m: '%s%s****%s' % (m.group(1) or '', m.group(2), m.group(3)), str(text))
    except Exception:
        return str(text)


def _classify(msg):
    for w in _ERROR_WORDS:
        if w in msg:
            return 'error'
    for w in _WARN_WORDS:
        if w in msg:
            return 'warn'
    return 'info'


def _day(ts=None):
    return time.strftime('%Y%m%d', time.localtime(ts) if ts else time.localtime())


def _open_file_locked():
    global _fh, _fh_day, _path
    day = _day()
    if _fh is not None and _fh_day == day:
        return
    try:
        if _fh is not None:
            _fh.close()
    except Exception:
        pass
    _fh = None
    _fh_day = day
    _path = os.path.join(_log_dir, 'tg-tool-%s.log' % day)
    try:
        _fh = open(_path, 'a', encoding='utf-8')
    except Exception:
        _fh = None


def _prune_locked():
    """删除超过保留天数的 tg-tool-*.log。"""
    cutoff = time.time() - _keep_days * 86400
    try:
        for name in os.listdir(_log_dir):
            if not (name.startswith('tg-tool-') and name.endswith('.log')):
                continue
            fp = os.path.join(_log_dir, name)
            try:
                if os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
            except Exception:
                continue
    except Exception:
        pass


_PARSE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\s*\] (.*)$')


def _load_tail_locked(limit=300):
    """把今天日志文件的尾部读进内存, 让重启后 Web 日志页还有上文。"""
    try:
        today = os.path.join(_log_dir, 'tg-tool-%s.log' % _day())
        if not os.path.isfile(today):
            return
        size = os.path.getsize(today)
        with open(today, 'r', encoding='utf-8', errors='replace') as f:
            if size > 256 * 1024:
                f.seek(size - 256 * 1024)
                f.readline()   # 丢掉被截断的半行
            lines = f.readlines()[-limit:]
        for raw in lines:
            raw = raw.rstrip('\n')
            if not raw:
                continue
            m = _PARSE_RE.match(raw)
            if m:
                ts, lv, msg = m.group(1), m.group(2).lower(), m.group(3)
            else:
                ts, lv, msg = '', 'info', raw
            if lv not in LEVELS:
                lv = 'info'
            _ring.append({'ts': ts, 'level': lv, 'msg': msg})
    except Exception:
        pass


def init(log_dir=None, keep_days=14):
    """初始化日志目录(幂等)。返回当前日志文件路径, 供 CLI 打印。"""
    global _log_dir, _keep_days
    with _lock:
        if log_dir:
            _log_dir = log_dir
        _keep_days = keep_days
        try:
            os.makedirs(_log_dir, exist_ok=True)
        except Exception:
            pass
        _open_file_locked()
        _prune_locked()
        if not _ring:
            _load_tail_locked()
        return _path


def set_sink(fn):
    """注册广播回调: fn({ts, level, msg})。"""
    global _sink
    _sink = fn


def current_file():
    return _path


def close():
    """关闭日志文件句柄(测试/退出时用)。"""
    global _fh
    with _lock:
        try:
            if _fh is not None:
                _fh.close()
        except Exception:
            pass
        _fh = None


def log(msg, level='info'):
    """写一条日志。level 省略时按关键字归到 warn/error。"""
    try:
        text = mask(msg if isinstance(msg, str) else str(msg))
        lv = (level or '').lower()
        if lv not in LEVELS:
            lv = 'info'
        if lv == 'info':
            lv = _classify(text)
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        entry = {'ts': ts, 'level': lv, 'msg': text}
        line = '%s [%s] %s\n' % (ts, _LABEL[LEVELS[lv]], text)
        with _lock:
            _ring.append(entry)
            _open_file_locked()
            if _fh is not None:
                try:
                    _fh.write(line)
                    _fh.flush()
                except Exception:
                    pass
        if _sink is not None:
            try:
                _sink(entry)
            except Exception:
                pass
    except Exception:
        pass


def history(limit=500, level='', q=''):
    """从内存环形缓冲取最近日志(新->旧过滤后反转成旧->新)。"""
    try:
        limit = max(1, min(int(limit), 3000))
    except Exception:
        limit = 500
    threshold = LEVELS.get((level or '').lower(), 0)
    needle = (q or '').strip().lower()
    out = []
    with _lock:
        snapshot = list(_ring)
    for e in reversed(snapshot):
        if threshold and LEVELS.get(e.get('level'), 20) < threshold:
            continue
        if needle and needle not in (e.get('msg') or '').lower():
            continue
        out.append(dict(e))
        if len(out) >= limit:
            break
    out.reverse()
    return out
