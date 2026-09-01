"""TG小号工具箱 GUI —— 风格A(系统原生) 主界面
================================================
布局:
  ┌───────────────────────────────────────────────┐
  │ 顶栏: 当前账号信息(头像+名字+电话)  ● 已连接   │
  ├──────────────┬────────────────────────────────┤
  │ 账号列表      │  [删除联系人][删除对话]        │
  │  搜索框       │  [更新本体][白名单管理]        │
  │  头像+三行    │  速度单选  进度条  日志        │
  │  (定稿布局)   │                                │
  ├──────────────┴────────────────────────────────┤
  │ 状态栏: 状态│摘要            [■ 停止任务]     │
  └───────────────────────────────────────────────┘

线程模型: Tk 主线程 + tg_engine 后台线程(asyncio)。
所有引擎回调经 root.after(0, ...) 投回主线程。
"""
import glob
import os
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from tkinter import ttk, messagebox, simpledialog

import ttkbootstrap as ttkb                  # noqa: E402

import tg_tool                              # noqa: E402  (路径/界面文本/白名单)

SCRIPT_DIR = tg_tool.SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)
# 账号根目录:
#   源码: 工具箱目录的上级(TG小号)
#   打包 onedir: exe 在「程序名」文件夹里,账号在 exe 上级
#   打包 onefile: exe 是单文件,账号就在 exe 所在目录
if tg_tool.IS_FROZEN and not os.path.isdir(os.path.join(SCRIPT_DIR, '_internal')):
    ROOT = SCRIPT_DIR                      # onefile
else:
    ROOT = os.path.dirname(SCRIPT_DIR)     # 源码 / onedir

import tg_engine                            # noqa: E402
import tg_profile                           # noqa: E402

# ---------- 样式常量 ----------
AVATAR_COLORS = ['#E17076', '#7BC862', '#65AADD', '#A695E7', '#EE7AAE',
                 '#6EC9CB', '#FAA774', '#FFA6C9']
PRIMARY = '#229ED9'      # Telegram 蓝
FG = '#1F2937'
FG2 = '#6B7280'
FG3 = '#9CA3AF'
SEL_BG = '#E6F3FB'
CARD_BG = '#FFFFFF'
PANEL_BG = '#F5F7FA'
BORDER = '#E2E8F0'

# ---------- 工具函数 ----------
def mask_phone(p):
    """+6288105366140 -> +62 810****6140"""
    if not p:
        return ''
    p = str(p)
    if len(p) >= 9:
        return f'{p[:5]}****{p[-4:]}'
    return p


def country_of(phone):
    """区号最长前缀匹配 -> (两字母码, 中文名)。"""
    best = None
    for code, (cc, name) in tg_profile.PHONE_CODE_MAP.items():
        if phone.startswith(code) and (best is None or len(code) > len(best[0])):
            best = (code, cc, name)
    if best:
        return best[1], best[2]
    return None, ''


def avatar_color(name):
    return AVATAR_COLORS[hash(str(name)) % len(AVATAR_COLORS)]


def _schedule(fn):
    """线程安全: 引擎回调 -> Tk 主线程。"""
    try:
        APP_ROOT.after(0, fn)
    except RuntimeError:
        pass


APP_ROOT = None     # main() 里赋值


# ---------- 账号条目 (定稿布局: 头像 + 名字/username 同行 + 电话 + id) ----------
class AccountItem(tk.Frame):
    """一条账号卡片:
       [头像]  名字 粗黑  @username 灰
              [ID] +62 810****6140 · 印度尼西亚
              id 7132536809
    """
    def __init__(self, master, acc, on_click, on_double):
        super().__init__(master, bg=CARD_BG, cursor='hand2',
                         highlightthickness=1, highlightbackground=BORDER)
        self.acc = acc                      # dict: name/path/state/phone/username/uid
        self.selected = False
        self._photo = None

        head = tk.Frame(self, bg=CARD_BG)
        head.pack(fill='x', padx=6, pady=5)

        # 头像: 40px 圆角色块(有缓存图片则用图片)
        self.avatar_lbl = tk.Label(head, width=3, height=2, bg=avatar_color(acc['name']),
                                   fg='white', font=('Microsoft YaHei UI', 12, 'bold'))
        self.avatar_lbl.pack(side='left', padx=(2, 8))
        self._try_photo()

        txt = tk.Frame(head, bg=CARD_BG)
        txt.pack(side='left', fill='x', expand=True)

        # 第1行: 用户名(粗黑,联网拉到的) or 文件夹名
        display = acc.get('display') or acc['name']
        r1 = tk.Frame(txt, bg=CARD_BG)
        r1.pack(fill='x')
        tk.Label(r1, text=display, bg=CARD_BG, fg=FG,
                 font=('Microsoft YaHei UI', 9, 'bold'), anchor='w').pack(side='left')
        uname = acc.get('username') or acc.get('phone', '')
        if uname:
            u = f'@{uname}' if uname and not str(uname).startswith('+') else uname
            tk.Label(r1, text=u, bg=CARD_BG, fg=FG2,
                     font=('Microsoft YaHei UI', 8), anchor='w').pack(side='left', padx=(5, 0))

        # 第2行: [国家码] 电话 · 国家中文名
        cc, cname = country_of(acc.get('phone', '') or '')
        phone = mask_phone(acc.get('phone', '') or '')
        r2 = tk.Frame(txt, bg=CARD_BG)
        r2.pack(fill='x')
        if phone:
            tk.Label(r2, text=phone, bg=CARD_BG, fg=FG2,
                     font=('Microsoft YaHei UI', 8), anchor='w').pack(side='left')
        if cname:
            tk.Label(r2, text=f'· {cname}', bg=CARD_BG, fg=FG3,
                     font=('Microsoft YaHei UI', 8), anchor='w').pack(side='left', padx=(4, 0))

        # 第3行: DC + ID
        dc = acc.get('dc') or '?'
        uid = acc.get('uid') or '未知'
        tk.Label(txt, text=f'DC:{dc}  ID:{uid}', bg=CARD_BG, fg=FG3,
                 font=('Microsoft YaHei UI', 8), anchor='w').pack(fill='x')

        # 状态角标
        st = acc.get('state')
        if st != 'ok':
            mark = {'tdata': 'tdata 待转换', 'session': '仅 session', 'empty': '空文件夹'}.get(st, st)
            tk.Label(head, text=mark, bg=CARD_BG, fg=FG3,
                     font=('Microsoft YaHei UI', 7)).pack(side='right', padx=(4, 0))

        for w in (self, head, txt, r1, r2):
            for e in (w,):
                e.bind('<Button-1>', lambda e: on_click(self))
                e.bind('<Double-Button-1>', lambda e: on_double(self))
        for child in head.winfo_children() + r1.winfo_children() + r2.winfo_children() + txt.winfo_children():
            child.bind('<Button-1>', lambda e: on_click(self))
            child.bind('<Double-Button-1>', lambda e: on_double(self))

    def _try_photo(self):
        # 头像异步: 先显示色块,PIL 解码放后台线程,好了再回填主线程
        p = tg_profile.avatar_path(self.acc['name'])
        if p and os.path.isfile(p):
            threading.Thread(target=self._load_photo_bg, args=(p,), daemon=True).start()

    def _load_photo_bg(self, p):
        try:
            from PIL import Image
            im = Image.open(p).resize((40, 40))
            _schedule(lambda: self._apply_photo(im))
        except Exception:
            pass

    def _apply_photo(self, im):
        try:
            from PIL import ImageTk
            self._photo = ImageTk.PhotoImage(im)
            self.avatar_lbl.configure(image=self._photo, width=40, height=40, text='')
        except Exception:
            pass

    def set_selected(self, sel):
        self.selected = sel
        self.configure(bg=SEL_BG if sel else CARD_BG,
                       highlightbackground='#5AA7E0' if sel else BORDER)
        # 子控件同步换底色
        new_bg = SEL_BG if sel else CARD_BG
        for w in self.winfo_children():
            self._recolor(w, new_bg)

    def _recolor(self, w, bg):
        try:
            if w.winfo_class() != 'Label' or w is self.avatar_lbl:
                if w is self.avatar_lbl and w.cget('image'):
                    return
            if isinstance(w, tk.Label) and not w.cget('image'):
                w.configure(bg=bg)
            for c in w.winfo_children():
                self._recolor(c, bg)
        except tk.TclError:
            pass


# ---------- 主窗口 ----------
class App:
    def __init__(self, root):
        self.root = root
        root.title('TG小号工具箱')
        root.geometry('980x660')
        root.minsize(860, 560)

        # 引擎
        self.eng = tg_engine.Engine(on_log=self._cb_log,
                                    on_progress=self._cb_progress,
                                    on_state=self._cb_state)
        self.accounts = []           # 全量
        self.cur = None              # 当前选中条目
        self.cur_item = None
        self.connected = False
        self.busy = False
        self.speed_var = None
        self._pending_connect = None

        self._build()
        self.refresh_accounts()
        global APP_ROOT
        APP_ROOT = root               # _schedule 用
        self.eng.start()               # 启动后台 asyncio 循环线程
        root.protocol('WM_DELETE_WINDOW', self._on_close)

        # 拖放导入: 把含 tdata / session+json 的 zip 拖进窗口自动导入
        self._dnd_ok = False
        try:
            import windnd
            windnd.hook_dropfiles(root, func=self._on_dropfiles, force_unicode=True)
            self._dnd_ok = True
        except Exception:
            pass

        # 后台补全 username/头像(串行,每号1s,完成后刷列表)
        tg_profile.start_refresh(ROOT, on_update=self._on_profile_one)

    # ---------- 界面构建 ----------
    def _build(self):
        # 顶栏: 当前账号
        self.top = tk.Frame(self.root, bg='white', height=64)
        self.top.pack(fill='x')
        self.top.pack_propagate(False)
        self.top_avatar = tk.Label(self.top, text='-', width=3, height=1,
                                   bg='#CCCCCC', fg='white',
                                   font=('Microsoft YaHei UI', 14, 'bold'))
        self.top_avatar.pack(side='left', padx=(14, 10), pady=10)
        tf = tk.Frame(self.top, bg='white')
        tf.pack(side='left', fill='y', pady=8)
        self.top_name = tk.Label(tf, text='未选择账号', bg='white', fg=FG,
                                 font=('Microsoft YaHei UI', 12, 'bold'), anchor='w')
        self.top_name.pack(anchor='w')
        self.top_sub = tk.Label(tf, text='双击左侧账号连接', bg='white', fg=FG2,
                                font=('Microsoft YaHei UI', 9), anchor='w')
        self.top_sub.pack(anchor='w')
        self.top_dot = tk.Label(self.top, text='● 未连接', bg='white', fg=FG3,
                                font=('Microsoft YaHei UI', 9))
        self.top_dot.pack(side='right', padx=16)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x')

        # 主体: 左列表 + 右操作
        body = tk.Frame(self.root, bg=PANEL_BG)
        body.pack(fill='both', expand=True)

        # ---- 左: 账号列表 ----
        left = tk.LabelFrame(body, text=f' 账号 ', bg='white', fg=FG,
                             font=('Microsoft YaHei UI', 9))
        left.pack(side='left', fill='y', padx=8, pady=8, ipadx=0, ipady=0)

        sf = tk.Frame(left, bg='white')
        sf.pack(fill='x', padx=6, pady=(6, 2))
        tk.Label(sf, text='搜索:', bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self.refresh_accounts())
        e = tk.Entry(sf, textvariable=self.search_var, font=('Microsoft YaHei UI', 9),
                     relief='solid', bd=1)
        e.pack(side='left', fill='x', expand=True, padx=4)

        # 滚动列表区
        lf = tk.Frame(left, bg='white')
        lf.pack(fill='both', expand=True, padx=6, pady=(2, 6))
        self.list_canvas = tk.Canvas(lf, bg='white', highlightthickness=0)
        vsb = ttk.Scrollbar(lf, orient='vertical', command=self.list_canvas.yview)
        self.list_inner = tk.Frame(self.list_canvas, bg='white')
        self.list_inner.bind('<Configure>',
                             lambda e: self.list_canvas.configure(
                                 scrollregion=self.list_canvas.bbox('all')))
        self.list_canvas.create_window((0, 0), window=self.list_inner, anchor='nw')
        self.list_canvas.configure(yscrollcommand=vsb.set, width=272)
        self.list_canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        # 鼠标滚轮
        self.list_canvas.bind('<Enter>', lambda e: self._bind_wheel())
        self.list_canvas.bind('<Leave>', lambda e: self._unbind_wheel())
        self._build_right(body)

    def _bind_wheel(self):
        self.root.bind_all('<MouseWheel>', self._on_wheel)

    def _unbind_wheel(self):
        self.root.unbind_all('<MouseWheel>')

    def _on_wheel(self, e):
        try:
            self.list_canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        except Exception:
            pass

    # 在 _build 尾部续: 右侧操作面板
    def _build_right(self, body):
        right = tk.Frame(body, bg=PANEL_BG)
        right.pack(side='left', fill='both', expand=True, padx=(0, 8), pady=8)

        # 按钮区
        bf = tk.Frame(right, bg=PANEL_BG)
        bf.pack(fill='x')
        self.btn_del_contacts = ttkb.Button(
            bf, text='删除联系人', bootstyle='danger',
            state='disabled', command=self.on_delete_contacts)
        self.btn_del_contacts.pack(side='left', expand=True, fill='x', padx=(0, 4))
        self.btn_del_dialogs = ttkb.Button(
            bf, text='删除对话', bootstyle='danger',
            state='disabled', command=self.on_delete_dialogs)
        self.btn_del_dialogs.pack(side='left', expand=True, fill='x', padx=4)
        bf2 = tk.Frame(right, bg=PANEL_BG)
        bf2.pack(fill='x', pady=4)
        self.btn_update = ttkb.Button(
            bf2, text='更新本体', bootstyle='primary',
            state='disabled', command=self.on_update)
        self.btn_update.pack(side='left', expand=True, fill='x', padx=(0, 4))
        self.btn_wl = ttkb.Button(
            bf2, text='白名单管理', bootstyle='secondary',
            command=self.on_whitelist)
        self.btn_wl.pack(side='left', expand=True, fill='x', padx=4)
        self.btn_settings = ttkb.Button(
            bf2, text='程序设置', bootstyle='secondary',
            command=self.on_settings)
        self.btn_settings.pack(side='left', expand=True, fill='x', padx=4)

        # 速度
        spd = tk.LabelFrame(right, text=' 删除速度 ', bg='white', fg=FG,
                            font=('Microsoft YaHei UI', 9))
        spd.pack(fill='x', pady=6)
        sf = tk.Frame(spd, bg='white')
        sf.pack(fill='x', padx=8, pady=6)
        self.speed_var = tk.StringVar(value='2')
        for i, (name, rng) in enumerate(
                [('极快', '0.2~0.4s'), ('快速', '0.4~0.6s'), ('默认', '0.9~1.4s'),
                 ('慢速', '1.3~1.6s'), ('极慢', '1.9~2.2s')], 1):
            rb = tk.Radiobutton(sf, text=f'{name}', variable=self.speed_var, value=str(i),
                                bg='white', font=('Microsoft YaHei UI', 9),
                                command=self._apply_speed)
            rb.pack(side='left', expand=True)

        # 进度区
        pf = tk.LabelFrame(right, text=' 进度 ', bg='white', fg=FG,
                           font=('Microsoft YaHei UI', 9))
        pf.pack(fill='x', pady=6)
        pin = tk.Frame(pf, bg='white')
        pin.pack(fill='x', padx=8, pady=(2, 4))
        self.task_lbl = tk.Label(pin, text='当前任务：无', bg='white', fg=FG,
                                 font=('Microsoft YaHei UI', 9), anchor='w')
        self.task_lbl.pack(fill='x')
        bar = tk.Frame(pin, bg='#E4E4E4', height=14)
        bar.pack(fill='x', pady=2)
        bar.pack_propagate(False)
        self.bar_fill = tk.Label(bar, bg='#5AA7E0', width=0)
        self.bar_fill.place(x=0, rely=0, relheight=1, relwidth=0)
        self.prog_lbl = tk.Label(pin, text='', bg='white', fg=FG2,
                                 font=('Microsoft YaHei UI', 8), anchor='w')
        self.prog_lbl.pack(fill='x')

        # 日志区
        logf = tk.LabelFrame(right, text=' 日志 ', bg='white', fg=FG,
                             font=('Microsoft YaHei UI', 9))
        logf.pack(fill='both', expand=True, pady=6)
        self.log_txt = tk.Text(logf, height=10, bg='white', fg=FG,
                               font=('Consolas', 9), relief='flat',
                               state='disabled', wrap='none')
        lsb = ttk.Scrollbar(logf, orient='vertical', command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=lsb.set)
        self.log_txt.pack(side='left', fill='both', expand=True, padx=(8, 0), pady=6)
        lsb.pack(side='right', fill='y', pady=6)

        # 状态栏
        self.status = tk.Frame(self.root, bg=PANEL_BG, height=30)
        self.status.pack(side='bottom', fill='x')
        self.status.pack_propagate(False)
        self.st_lbl = tk.Label(self.status, text='就绪', bg=PANEL_BG, fg=FG2,
                               font=('Microsoft YaHei UI', 9), anchor='w')
        self.st_lbl.pack(side='left', padx=10)
        self.btn_stop = ttkb.Button(self.status, text='■ 停止任务', bootstyle='danger-outline',
                                    state='disabled', command=self.on_stop)
        self.btn_stop.pack(side='right', padx=10, pady=3)

    # ---------- 账号列表 ----------
    def refresh_accounts(self):
        """重扫账号并按搜索词过滤重建列表。"""
        for w in self.list_inner.winfo_children():
            w.destroy()
        if not self.accounts:
            raw = tg_engine.scan_accounts(ROOT)
            prof = tg_profile.load_profiles()
            for name, path, st in raw:
                a = {'name': name, 'path': path, 'state': st,
                     'phone': '', 'username': '', 'uid': ''}
                # 从账号 json 补 phone/uid
                try:
                    import json as _j
                    import glob as _g
                    js = _g.glob(os.path.join(path, '*.json'))
                    if js:
                        cfg = _j.load(open(js[0], encoding='utf-8'))
                        a['phone'] = str(cfg.get('phone') or '')
                        u = cfg.get('username') or cfg.get('name2') or ''
                        a['username'] = str(u) if not str(cfg.get('phone') or '') or u != cfg.get('phone') else ''
                        uid = cfg.get('user_id') or cfg.get('uid') or ''
                        a['uid'] = str(uid) if uid else ''
                except Exception:
                    pass
                # profiles.json 缓存优先(联网补全过的)
                p = prof.get(name, {})
                for k in ('username', 'phone', 'uid', 'dc'):
                    if p.get(k) and not a.get(k):
                        a[k] = str(p[k])
                # 显示名: first+last 优先(用户名称),否则文件夹名
                if p.get('first') or p.get('last'):
                    a['display'] = (str(p.get('first') or '') + ' ' +
                                    str(p.get('last') or '')).strip()
                self.accounts.append(a)

        q = (self.search_var.get() or '').strip().lower()
        shown = []
        for a in self.accounts:
            if not q:
                shown.append(a)
                continue
            hay = ' '.join(str(a.get(k) or '') for k in
                           ('name', 'display', 'username', 'phone', 'uid'))
            cc, cname = country_of(a.get('phone', '') or '')
            if q in hay.lower() or (cname and q in cname.lower()):
                shown.append(a)

        # 分片渲染: 每批 24 个,间隙让 UI 响应,避免一次性建几百控件卡顿
        self._render_batch(shown, 0)

    def _render_batch(self, items, start, step=24):
        end = min(start + step, len(items))
        for a in items[start:end]:
            it = AccountItem(self.list_inner, a,
                             on_click=self._pick_item, on_double=self._connect_item)
            it.pack(fill='x', padx=3, pady=2)
            if self.cur and self.cur.get('name') == a.get('name'):
                it.set_selected(True)
                self.cur_item = it
        if end < len(items):
            self.root.after(8, lambda: self._render_batch(items, end, step))

    def _pick_item(self, item):
        if self.cur_item and self.cur_item is not item:
            self.cur_item.set_selected(False)
        self.cur_item = item
        self.cur = item.acc
        item.set_selected(True)
        a = item.acc
        self.top_name.configure(text=a['name'])
        self.top_avatar.configure(
            text=(a['name'][:1] or '-'), bg=avatar_color(a['name']))
        sub = mask_phone(a.get('phone', '') or '') or a.get('state', '')
        if a.get('uid'):
            sub += f'   id {a["uid"]}' if sub else f'id {a["uid"]}'
        self.top_sub.configure(text=sub or '双击连接')
        self.set_status('已选中（双击连接）' if not self.connected else '已选中（双击切换连接）')

    def _connect_item(self, item):
        if self.busy:
            messagebox.showinfo('任务运行中', '请先停止当前任务再切换账号。')
            return
        self._pick_item(item)
        a = item.acc
        self._pending_connect = a          # _state('connected') 里用
        self.set_status('正在连接…')
        self.log(f'正在连接账号 {a["name"]} …')
        self.top_dot.configure(text='● 连接中', fg='#E67E22')
        self.eng.connect(a['path'])

    def _on_connected(self, info):
        """引擎 on_state('connected', info) 到达。"""
        a = self._pending_connect or (self.cur or {})
        self.connected = True
        me = info or {}
        self.top_dot.configure(text='● 已连接', fg='#27AE60')
        self.set_status(f'已连接 {a.get("name", "")}')
        # 回填真实资料
        name = ((me.get('first') or '') + ' ' + (me.get('last') or '')).strip() or a.get('name', '')
        if me.get('username') is not None:
            a['username'] = me.get('username') or a.get('username', '')
        if me.get('phone'):
            a['phone'] = me['phone']
        if me.get('uid'):
            a['uid'] = me['uid']
        self.top_name.configure(text=name)
        sub = mask_phone(a.get('phone', '') or '')
        if a.get('uid'):
            sub += f'   id {a["uid"]}' if sub else f'id {a["uid"]}'
        self.top_sub.configure(text=sub or '双击连接')
        # 头像(缓存有则用)
        p = tg_profile.avatar_path(a.get('name', ''))
        if p and os.path.isfile(p):
            try:
                from PIL import Image, ImageTk
                im = Image.open(p).resize((40, 40))
                ph = ImageTk.PhotoImage(im)
                self.top_avatar.configure(image=ph, text='')
                self.top_avatar.image = ph
            except Exception:
                pass
        self._set_task_buttons('normal')
        self.accounts = []
        self.refresh_accounts()

    # ---------- 任务动作 ----------
    def _require_connected(self):
        if not self.connected:
            messagebox.showinfo('未连接', '请先双击左侧账号连接。')
            return False
        if self.busy:
            messagebox.showinfo('任务运行中', '请先停止当前任务。')
            return False
        return True

    def on_delete_contacts(self):
        if not self._require_connected():
            return
        self.eng.count_contacts(on_done=lambda ok, n: _schedule(
            lambda: self._confirm_del_contacts(ok, n)))

    def _confirm_del_contacts(self, ok, n):
        if not ok:
            messagebox.showerror('查询失败', str(n)[:300])
            return
        keep = n.get('whitelist', 0)
        dele = n.get('deletable', 0)
        if dele == 0:
            messagebox.showinfo('无需操作', f'联系人共 {keep} 个，均在白名单，无可删除项。')
            return
        if not messagebox.askyesno(
                '确认删除',
                f'将删除 {dele} 个联系人（白名单保留 {keep} 个，含收藏联系人）。\n'
                f'删除前自动备份。确认执行？'):
            return
        self._apply_speed()
        self._start_task('删除联系人')
        self.eng.delete_contacts()

    def on_delete_dialogs(self):
        if not self._require_connected():
            return
        self._start_task('扫描对话')
        self.eng.scan_dialogs()
        # 扫描结果经 on_state('scan', data) 回调 -> 弹范围选择

    def _ask_scope(self, data):
        """扫描完成后弹范围选择框。"""
        total = data.get('total', 0)
        priv = data.get('users', 0) + data.get('deleted', 0) + data.get('bots', 0)
        grp = data.get('groups', 0)
        keepu = data.get('keep_users', 0)
        keepg = data.get('keep_groups', 0)
        if total == 0:
            messagebox.showinfo('无需操作', '该账号没有可删除的对话。')
            self._end_task()
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(f'删除对话 · {self.cur["name"]}')
        dlg.geometry('420x330')
        dlg.configure(bg='white')
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text='扫描完成（含归档）：', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w', padx=16, pady=(12, 4))
        info = (f'总对话数：{total} 个\n'
                f'　私聊：{priv} 个（普通 {data.get("users", 0)} + 已注销 {data.get("deleted", 0)}'
                f' + 机器人 {data.get("bots", 0)}）\n'
                f'　群组/频道：{grp} 个\n'
                f'　保留：白名单 {keepu} 用户 + {keepg} 群 + 收藏夹')
        tk.Label(dlg, text=info, bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 9), justify='left').pack(anchor='w', padx=16)
        var = tk.StringVar(value='all')
        for text, val in (('仅删除全部私聊（机器人将拉黑）', 'privates'),
                          ('仅退出群组/频道', 'groups'),
                          ('全部执行（私聊 + 群组/频道）', 'all')):
            tk.Radiobutton(dlg, text=text, variable=var, value=val, bg='white',
                           font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=16, pady=2)
        bf = tk.Frame(dlg, bg='white')
        bf.pack(pady=12)

        def go():
            choice = var.get()
            dlg.destroy()
            self._apply_speed()
            self._start_task('删除对话')
            self.eng.delete_dialogs(choice)

        ttkb.Button(bf, text='确认执行', bootstyle='danger',
                    command=go).pack(side='left', padx=6)
        ttkb.Button(bf, text='取消', bootstyle='secondary',
                    command=lambda: (dlg.destroy(), self._end_task())).pack(side='left', padx=6)

    def on_update(self):
        if not self._require_connected():
            return
        if not messagebox.askyesno('确认更新',
                                   '将下载最新版 Telegram Desktop 并替换本体（旧版自动备份）。确认执行？'):
            return
        self._start_task('更新本体')
        self.eng.update_telegram()

    def on_stop(self):
        if self.eng.stop_task():
            self.log('已请求停止（当前动作完成后中止）')

    # ---------- 状态切换 ----------
    def _start_task(self, name):
        self.busy = True
        self.task_lbl.configure(text=f'当前任务：{name}')
        self.st_lbl.configure(text=f'运行中：{name}')
        self.btn_stop.configure(state='normal')
        self._set_task_buttons('disabled')

    def _end_task(self):
        self.busy = False
        self.task_lbl.configure(text='当前任务：无')
        self.btn_stop.configure(state='disabled')
        self.bar_fill.place(relwidth=0)
        self.prog_lbl.configure(text='')
        if self.connected:
            self._set_task_buttons('normal')
            self.set_status(f'已连接 {self.cur["name"] if self.cur else ""}')
        else:
            self.set_status('就绪')

    def _set_task_buttons(self, st):
        for b in (self.btn_del_contacts, self.btn_del_dialogs, self.btn_update):
            b.configure(state=st)

    def _apply_speed(self):
        idx = int(self.speed_var.get())
        self.eng.set_speed(idx)

    def set_status(self, s):
        self.st_lbl.configure(text=s)

    def log(self, line):
        ts = __import__('time').strftime('%H:%M:%S')
        self.log_txt.configure(state='normal')
        self.log_txt.insert('end', f'{ts} {line}\n')
        self.log_txt.see('end')
        self.log_txt.configure(state='disabled')

    # ---------- 引擎回调(在主线程执行) ----------
    def _cb_log(self, line):
        _schedule(lambda: self.log(line))

    def _cb_progress(self, done, total, label):
        _schedule(lambda: self._progress(done, total, label))

    def _progress(self, done, total, label):
        if total > 0:
            pct = done / total
            self.bar_fill.place(relwidth=min(pct, 1.0))
            extra = f' · {label}' if label else ''
            self.prog_lbl.configure(text=f'{done}/{total}（{pct * 100:.1f}%）{extra}')
            est = ''
            self.prog_lbl.configure(text=f'{done}/{total}（{pct * 100:.1f}%）{extra}{est}')

    def _cb_state(self, state, data):
        _schedule(lambda: self._state(state, data))

    def _state(self, state, data):
        if state == 'task_start':
            self.busy = True
            self.btn_stop.configure(state='normal')
            self._set_task_buttons('disabled')
        elif state == 'connected':
            self._on_connected(data if isinstance(data, dict) else {})
        elif state == 'connect_fail':
            self.connected = False
            self._end_task()
            self.top_dot.configure(text='● 连接失败', fg='#C0392B')
            messagebox.showerror('连接失败',
                                 '登录态失效或网络异常，详见日志。')
        elif state == 'scan':
            # 扫描完成 -> 弹范围选择
            self._ask_scope(data if isinstance(data, dict) else {})
        elif state == 'done':
            self._end_task()
            if isinstance(data, dict):
                s = data.get('summary', '')
                if s:
                    self.set_status(s)
            messagebox.showinfo('完成', '任务已完成。')
        elif state == 'error':
            self._end_task()
            messagebox.showerror('任务出错', str(data)[:500])

    # ---------- 关闭 ----------
    def _on_close(self):
        if self.busy:
            if not messagebox.askyesno('任务运行中',
                                       '任务尚未完成，退出将中止任务。确认退出？'):
                return
        self.eng.shutdown()
        self.root.after(150, self.root.destroy)

    # ---------- 拖放导入账号 ----------
    def _on_dropfiles(self, files):
        """windnd 回调: 拖入的文件路径列表(默认 bytes)。"""
        for f in files:
            if isinstance(f, bytes):
                try:
                    f = f.decode('gbk')
                except UnicodeDecodeError:
                    f = f.decode('utf-8', errors='replace')
            if not f or not f.lower().endswith('.zip'):
                continue
            self._import_archive(f)

    def _import_archive(self, zip_path):
        """解压 zip 并导入账号(tdata 或 session+json)到账号根目录 ROOT。"""
        name = os.path.splitext(os.path.basename(zip_path))[0] or '账号'
        tmp = tempfile.mkdtemp(prefix='tgimport_')
        try:
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(tmp)
            except Exception as e:
                messagebox.showerror('导入失败', f'解压失败：{e}')
                return
            src, kind = self._find_account(tmp)
            if src is None:
                messagebox.showerror('导入失败',
                                     '压缩包里没找到 tdata 或 session+json 账号结构。')
                return
            target = self._unique_target_dir(ROOT, name)
            os.makedirs(target, exist_ok=True)
            for entry in os.listdir(src):
                s = os.path.join(src, entry)
                d = os.path.join(target, entry)
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d, ignore_errors=True)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            self.accounts = []
            self.refresh_accounts()
            if kind == 'tdata':
                self.log(f'已导入 tdata 账号 {os.path.basename(target)}，后台转换中…')
                fut = self.eng.convert_tdata(target)
                fut.add_done_callback(
                    lambda f, t=target: self._after_tdata_convert(f, t))
            else:
                self.log(f'已导入账号：{os.path.basename(target)}（session+json）')
                messagebox.showinfo('导入完成', f'已导入账号：{os.path.basename(target)}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _after_tdata_convert(self, fut, target):
        """tdata 后台转换完成后的回调(引擎线程)。"""
        try:
            ok = bool(fut.result())
        except Exception:
            ok = False

        def _cb():
            self.accounts = []
            self.refresh_accounts()
            name = os.path.basename(target)
            if ok:
                self.log(f'账号 {name} 转换完成')
                messagebox.showinfo('导入完成', f'已导入并转换账号：{name}')
            else:
                self.log(f'账号 {name} 转换失败')
                messagebox.showwarning(
                    '导入完成',
                    f'tdata 已导入到 {name}，但转换失败（可能缺 opentele-ng）。')

        _schedule(_cb)

    def _find_account(self, d):
        """在解压目录里找账号结构(支持顶层或一层子目录)。
        返回 (源目录, 'tdata'|'session') 或 (None, None)。"""
        r = self._account_kind(d)
        if r:
            return d, r
        for sub in sorted(os.listdir(d)):
            subd = os.path.join(d, sub)
            if os.path.isdir(subd):
                r = self._account_kind(subd)
                if r:
                    return subd, r
        return None, None

    def _account_kind(self, d):
        """判断目录 d 是否是账号结构。返回 'tdata' / 'session' / None。"""
        if os.path.isdir(os.path.join(d, 'tdata')):
            return 'tdata'
        sess = glob.glob(os.path.join(d, '*.session'))
        js = [f for f in glob.glob(os.path.join(d, '*.json'))
              if tg_tool._is_account_json(f)]
        if sess and js:
            return 'session'
        return None

    def _unique_target_dir(self, root, name):
        """返回 root 下不冲突的账号文件夹路径。"""
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

    # ---------- 程序设置(代理) ----------
    def on_settings(self):
        win = tk.Toplevel(self.root)
        win.title('程序设置')
        win.geometry('440x360')
        win.configure(bg='white')
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text='代理', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w', padx=14, pady=(10, 4))
        tk.Label(win, text='连接 Telegram 时使用的代理（对删联系人 / 删对话 / 资料刷新均生效）。',
                 bg='white', fg=FG2, font=('Microsoft YaHei UI', 8),
                 wraplength=400, justify='left').pack(anchor='w', padx=14)

        mode_var = tk.StringVar(value=tg_tool.PROXY_CFG.get('mode', 'system'))
        mf = tk.Frame(win, bg='white')
        mf.pack(anchor='w', padx=14, pady=4)
        for text, val in (('自动检测系统代理（推荐）', 'system'),
                          ('不使用代理（直连）', 'none'),
                          ('手动指定代理', 'manual')):
            tk.Radiobutton(mf, text=text, variable=mode_var, value=val, bg='white',
                           font=('Microsoft YaHei UI', 9),
                           command=lambda: self._toggle_proxy_fields(win, mode_var)
                           ).pack(anchor='w')

        # 手动字段
        mframe = tk.Frame(win, bg='white')
        mframe.pack(anchor='w', padx=30, pady=4)
        self._proxy_fields = {}
        scheme_var = tk.StringVar(value=tg_tool.PROXY_CFG.get('scheme', 'socks5'))
        row1 = tk.Frame(mframe, bg='white')
        row1.pack(anchor='w', pady=2)
        tk.Label(row1, text='类型:', bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 9)).pack(side='left')
        from tkinter import ttk as _ttk
        cb = _ttk.Combobox(row1, textvariable=scheme_var, width=8, state='readonly',
                           values=('socks5', 'socks4', 'http'), font=('Microsoft YaHei UI', 9))
        cb.pack(side='left', padx=6)
        host_var = tk.StringVar(value=str(tg_tool.PROXY_CFG.get('host', '')))
        tk.Label(row1, text='地址:', bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 9)).pack(side='left')
        tk.Entry(row1, textvariable=host_var, width=16).pack(side='left', padx=6)
        port_var = tk.StringVar(value=str(tg_tool.PROXY_CFG.get('port', '')))
        tk.Label(row1, text='端口:', bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 9)).pack(side='left')
        tk.Entry(row1, textvariable=port_var, width=6).pack(side='left', padx=6)
        self._proxy_fields = {'mframe': mframe, 'scheme': scheme_var,
                              'host': host_var, 'port': port_var}
        self._toggle_proxy_fields(win, mode_var)

        # 当前检测状态
        cur = tg_tool.detect_system_proxy() if tg_tool.PROXY_CFG.get('mode') == 'system' else None
        sys_txt = f'当前系统代理：{cur[0]}://{cur[1]}' if cur else '当前系统代理：未检测到（直连）'
        tk.Label(win, text=sys_txt, bg='white', fg=FG3,
                 font=('Microsoft YaHei UI', 8)).pack(anchor='w', padx=14, pady=6)

        bf = tk.Frame(win, bg='white')
        bf.pack(pady=10)

        def save():
            mode = mode_var.get()
            if mode == 'manual':
                host = host_var.get().strip()
                port = port_var.get().strip()
                if not host or not port.isdigit():
                    messagebox.showerror('参数错误', '请填写代理地址和数字端口。', parent=win)
                    return
                proxy = {'mode': 'manual', 'scheme': scheme_var.get(),
                         'host': host, 'port': int(port)}
            else:
                proxy = {'mode': mode}
            tg_tool.PROXY_CFG = proxy
            p = os.path.join(SCRIPT_DIR, 'settings.json')
            try:
                s = {}
                if os.path.isfile(p):
                    s = json.load(open(p, encoding='utf-8'))
                s['proxy'] = proxy
                json.dump(s, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            except Exception as e:
                messagebox.showerror('保存失败', str(e), parent=win)
                return
            rp = tg_tool.resolve_proxy()
            self.log(f'代理设置已保存：{proxy["mode"]}'
                     + (f' {rp[0]}://{rp[1]}:{rp[2]}' if rp else '（直连）'))
            win.destroy()

        import json as _json
        ttkb.Button(bf, text='保存', bootstyle='primary',
                    command=save).pack(side='left', padx=6)
        ttkb.Button(bf, text='取消', bootstyle='secondary',
                    command=win.destroy).pack(side='left', padx=6)

    def _toggle_proxy_fields(self, win, mode_var):
        f = self._proxy_fields.get('mframe')
        if f is None:
            return
        state = 'normal' if mode_var.get() == 'manual' else 'disabled'
        for child in f.winfo_children():
            self._set_state_recursive(child, state)

    def _set_state_recursive(self, w, state):
        try:
            w.configure(state=state)
        except tk.TclError:
            pass
        for c in w.winfo_children():
            self._set_state_recursive(c, state)

    # ---------- 白名单管理弹窗 ----------
    def on_whitelist(self):
        win = tk.Toplevel(self.root)
        win.title('白名单管理（所有账号共用）')
        win.geometry('560x420')
        win.configure(bg='white')
        win.transient(self.root)
        win.grab_set()

        def rebuild():
            for w in ulist.winfo_children():
                w.destroy()
            for w in glist.winfo_children():
                w.destroy()
            for uid in sorted(tg_tool.USER_WHITELIST):
                r = tk.Frame(ulist, bg='white')
                r.pack(fill='x', pady=1)
                tk.Label(r, text=str(uid), bg='white', fg=FG, width=12, anchor='w',
                         font=('Microsoft YaHei UI', 9)).pack(side='left')
                name = tg_profile.nickname_of(uid)
                tk.Label(r, text=name, bg='white', fg=FG2, anchor='w',
                         font=('Microsoft YaHei UI', 9)).pack(side='left', padx=6)
                ttkb.Button(r, text='移除', bootstyle='secondary-outline',
                            command=lambda u=uid: self._wl_remove_user(u, rebuild)).pack(side='right')
            for gid in sorted(tg_tool.GROUP_WHITELIST):
                r = tk.Frame(glist, bg='white')
                r.pack(fill='x', pady=1)
                tk.Label(r, text=str(gid), bg='white', fg=FG, width=12, anchor='w',
                         font=('Microsoft YaHei UI', 9)).pack(side='left')
                ttkb.Button(r, text='移除', bootstyle='secondary-outline',
                            command=lambda g=gid: self._wl_remove_group(g, rebuild)).pack(side='right')
            cnt1.configure(text=f'用户白名单（{len(tg_tool.USER_WHITELIST)}）')
            cnt2.configure(text=f'群组/频道白名单（{len(tg_tool.GROUP_WHITELIST)}）')

        tk.Label(win, text='删除操作时，白名单内用户 / 群组将保留不删。',
                 bg='white', fg=FG2, font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=14, pady=(10, 4))

        cnt1 = tk.Label(win, text='', bg='white', fg=FG,
                        font=('Microsoft YaHei UI', 9, 'bold'))
        cnt1.pack(anchor='w', padx=14)
        uf = tk.Frame(win, bg='white')
        uf.pack(fill='x', padx=14)
        ttkb.Button(uf, text='＋ 添加用户', bootstyle='primary-outline',
                    command=lambda: self._wl_add_user(rebuild)).pack(side='left')
        ulist = tk.Frame(win, bg='white', highlightthickness=1,
                         highlightbackground=BORDER)
        ulist.pack(fill='x', padx=14, pady=(2, 8))

        cnt2 = tk.Label(win, text='', bg='white', fg=FG,
                        font=('Microsoft YaHei UI', 9, 'bold'))
        cnt2.pack(anchor='w', padx=14)
        gf = tk.Frame(win, bg='white')
        gf.pack(fill='x', padx=14)
        ttkb.Button(gf, text='＋ 添加群/频道', bootstyle='primary-outline',
                    command=lambda: self._wl_add_group(rebuild)).pack(side='left')
        glist = tk.Frame(win, bg='white', highlightthickness=1,
                         highlightbackground=BORDER)
        glist.pack(fill='x', padx=14, pady=(2, 8))

        bf = tk.Frame(win, bg='white')
        bf.pack(pady=8)

        def restore_default():
            global USER_WHITELIST, GROUP_WHITELIST
            tg_tool.USER_WHITELIST = set(tg_tool.DEFAULT_USER_WHITELIST)
            tg_tool.GROUP_WHITELIST = set(tg_tool.DEFAULT_GROUP_WHITELIST)
            tg_tool.save_whitelist()
            rebuild()

        ttkb.Button(bf, text='恢复默认', bootstyle='warning-outline',
                    command=restore_default).pack(side='left', padx=6)
        ttkb.Button(bf, text='关闭', bootstyle='secondary',
                    command=win.destroy).pack(side='left', padx=6)
        rebuild()

    def _wl_add_user(self, rebuild):
        s = simpledialog.askstring('添加用户', '输入用户 ID 或 @用户名：', parent=self.root)
        if not s:
            return
        self._start_task('白名单添加')

        def on_done(ok, info):
            if ok:
                ent = info or {}
                uid = getattr(ent, 'id', None)
                name = (getattr(ent, 'first_name', '') + ' ' + getattr(ent, 'last_name', '')).strip()
                if uid:
                    tg_tool.USER_WHITELIST.add(int(uid))
                    if name:
                        tg_profile.save_nickname(int(uid), name)
                    tg_tool.save_whitelist()
                    _schedule(lambda: (self._end_task(), rebuild(),
                                       self.log(f'白名单已添加用户 {uid} ({name})')))
            else:
                _schedule(lambda: (self._end_task(),
                                   messagebox.showerror('添加失败', str(info)[:300])))

        self.eng.resolve_entity(s.strip(), on_done=on_done)

    def _wl_add_group(self, rebuild):
        s = simpledialog.askstring('添加群/频道', '输入群/频道 ID（正数）或 @用户名：', parent=self.root)
        if not s:
            return
        try:
            gid = int(s.strip())
        except ValueError:
            gid = None
        if gid is not None:
            tg_tool.GROUP_WHITELIST.add(gid)
            tg_tool.save_whitelist()
            rebuild()
            self.log(f'白名单已添加群/频道 {gid}')
        else:
            self._start_task('白名单添加')

            def on_done(ok, info):
                if ok and info:
                    gid2 = info.id if hasattr(info, 'id') else None
                    if gid2:
                        tg_tool.GROUP_WHITELIST.add(int(gid2))
                        tg_tool.save_whitelist()
                        _schedule(lambda: (self._end_task(), rebuild()))
                else:
                    _schedule(lambda: (self._end_task(),
                                       messagebox.showerror('添加失败', str(info)[:300])))

            self.eng.resolve_entity(s.strip(), on_done=on_done)

    def _wl_remove_user(self, uid, rebuild):
        if uid in tg_tool.USER_WHITELIST:
            tg_tool.USER_WHITELIST.discard(uid)
            tg_tool.save_whitelist()
            rebuild()
            self.log(f'白名单已移除用户 {uid}')

    def _wl_remove_group(self, gid, rebuild):
        if gid in tg_tool.GROUP_WHITELIST:
            tg_tool.GROUP_WHITELIST.discard(gid)
            tg_tool.save_whitelist()
            rebuild()
            self.log(f'白名单已移除群/频道 {gid}')

    # ---------- 资料后台补全 ----------
    def _on_profile_one(self, name, info):
        """worker 线程每完成一个账号回调一次。
        返回 True = 让 worker 取消(当前账号已连接,防 session 冲突)。
        资料只落盘 profiles.json,不实时重建账号列表(避免账号区闪烁),
        新资料在下次启动或手动重扫时生效。"""
        # 已连接账号 或 即将连接的账号 -> 取消后续刷新
        cur_name = (self._pending_connect or {}).get('name')
        if self.connected and self.cur and self.cur.get('name') == name:
            return True
        if cur_name == name:
            return True
        return False


# ---------- 入口 ----------
def main():
    global APP_ROOT
    tg_tool.load_proxy_cfg()
    root = ttkb.Window(themename='flatly')
    try:
        root.style.configure('.', font=('Microsoft YaHei UI', 9))
        root.style.configure('TButton', font=('Microsoft YaHei UI', 10, 'bold'))
        root.style.configure('TRadiobutton', font=('Microsoft YaHei UI', 9))
    except Exception:
        pass
    APP_ROOT = root
    app = App(root)
    root.mainloop()


if __name__ == '__main__':
    main()


