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

# 头像加载并发限流(避免几十个线程同时 PIL 解码抢 GIL 导致滚动卡)
_AVATAR_SEM = threading.Semaphore(4)
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
    def __init__(self, master, acc, on_click, on_double, on_right=None):
        super().__init__(master, bg=CARD_BG, cursor='hand2',
                         highlightthickness=1, highlightbackground=BORDER)
        self.acc = acc                      # dict: name/path/state/phone/username/uid
        self.selected = False
        self._photo = None

        head = tk.Frame(self, bg=CARD_BG)
        head.pack(fill='x', padx=8, pady=10)

        # 头像: 60x60 正方形(色块或缓存图片)
        self._ph = tk.PhotoImage(width=60, height=60)
        self.avatar_lbl = tk.Label(head, image=self._ph, compound='center',
                                   width=60, height=60, bg=avatar_color(acc['name']),
                                   fg='white', font=('Microsoft YaHei UI', 18, 'bold'),
                                   text=acc['name'][:1] or '-')
        self.avatar_lbl.pack(side='left', padx=(2, 10))
        self.avatar_lbl.pack_propagate(False)
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
                if on_right:
                    e.bind('<Button-3>', lambda e: on_right(self, e))
        for child in head.winfo_children() + r1.winfo_children() + r2.winfo_children() + txt.winfo_children():
            child.bind('<Button-1>', lambda e: on_click(self))
            child.bind('<Double-Button-1>', lambda e: on_double(self))
            if on_right:
                child.bind('<Button-3>', lambda e: on_right(self, e))

    def _try_photo(self):
        # 头像异步: 先显示色块,PIL 解码放后台线程,好了再回填主线程
        # 优先 profiles.json 存的绝对路径(跨目录也能用),否则按名字找
        p = self.acc.get('avatar') or tg_profile.avatar_path(self.acc['name'])
        if p and os.path.isfile(p):
            threading.Thread(target=self._load_photo_bg, args=(p,), daemon=True).start()

    def _load_photo_bg(self, p):
        with _AVATAR_SEM:   # 限流并发,避免几十线程抢 GIL 拖慢滚动
            try:
                from PIL import Image
                im = Image.open(p).resize((60, 60))
                # 用 self.after 回主线程(不依赖全局 APP_ROOT,时序可靠)
                self.after(0, lambda: self._apply_photo(im))
            except Exception:
                pass

    def _apply_photo(self, im):
        try:
            if not self.winfo_exists():
                return
            from PIL import ImageTk
            self._photo = ImageTk.PhotoImage(im)
            self.avatar_lbl.configure(image=self._photo, text='')
        except Exception:
            pass

    def set_selected(self, sel):
        self.selected = sel
        bg = SEL_BG if sel else CARD_BG
        self.configure(bg=bg, highlightbackground='#5AA7E0' if sel else BORDER)
        # 递归给所有子 Frame/Label 换底色(头像色块除外),让高亮完整覆盖卡片
        for w in self.winfo_children():
            self._recolor(w, bg)

    def _recolor(self, w, bg):
        try:
            if w is self.avatar_lbl:
                # 头像色块保持自身颜色
                for c in w.winfo_children():
                    self._recolor(c, bg)
                return
            if isinstance(w, (tk.Frame, tk.Label)):
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
        root.geometry(self._load_geometry() or '1100x680')
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
        self.groups = self.load_groups()   # 账号分组 {组名: [账号名]}
        self.cur_group = 'all'             # 当前选中分组

        self._build()
        self.refresh_accounts()
        root.after(200, self._restore_sashes)   # 窗口渲染后恢复三栏宽度
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
        self.top = tk.Frame(self.root, bg='white', height=76)
        self.top.pack(fill='x')
        self.top.pack_propagate(False)
        self._top_ph = tk.PhotoImage(width=48, height=48)
        self.top_avatar = tk.Label(self.top, image=self._top_ph, compound='center',
                                   width=48, height=48, bg='#CCCCCC', fg='white',
                                   font=('Microsoft YaHei UI', 16, 'bold'), text='-')
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
        self.btn_settings = ttkb.Button(self.top, text='⚙ 设置', bootstyle='secondary-outline',
                                        command=self.on_settings)
        self.btn_settings.pack(side='right', padx=(0, 12), pady=12)
        self.btn_disconnect = ttkb.Button(self.top, text='断开', bootstyle='danger-outline',
                                          command=self.on_disconnect, state='disabled')
        self.btn_disconnect.pack(side='right', pady=12)
        self.btn_reconnect = ttkb.Button(self.top, text='重连', bootstyle='secondary-outline',
                                         command=self.on_reconnect)
        self.btn_reconnect.pack(side='right', padx=4, pady=12)
        self.btn_launch = ttkb.Button(self.top, text='启动程序', bootstyle='secondary-outline',
                                      command=self.on_launch)
        self.btn_launch.pack(side='right', padx=4, pady=12)
        self.btn_pack = ttkb.Button(self.top, text='打包', bootstyle='secondary-outline',
                                    command=self.on_pack_account)
        self.btn_pack.pack(side='right', padx=4, pady=12)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x')

        # 主体: 三栏可拖动调节(PanedWindow)
        body = tk.Frame(self.root, bg=PANEL_BG)
        body.pack(fill='both', expand=True, padx=8, pady=8)

        self.pw = ttk.PanedWindow(body, orient='horizontal')
        self.pw.pack(fill='both', expand=True)

        # ---- 左: 账号列表 ----
        left = tk.LabelFrame(self.pw, text=f' 账号 ', bg='white', fg=FG,
                             font=('Microsoft YaHei UI', 9))
        self.pw.add(left, weight=1)

        # 分组标签栏
        self.group_bar = tk.Frame(left, bg='white')
        self.group_bar.pack(fill='x', padx=6, pady=(6, 0))

        sf = tk.Frame(left, bg='white')
        sf.pack(fill='x', padx=6, pady=(2, 2))
        tk.Label(sf, text='搜索:', bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self.refresh_accounts())
        e = tk.Entry(sf, textvariable=self.search_var, font=('Microsoft YaHei UI', 9),
                     relief='solid', bd=1)
        e.pack(side='left', fill='x', expand=True, padx=4)

        # 滚动列表区(虚拟滚动: 只渲染可见卡片,滚动动态增删)
        lf = tk.Frame(left, bg='white')
        lf.pack(fill='both', expand=True, padx=6, pady=(2, 6))
        self.list_canvas = tk.Canvas(lf, bg='white', highlightthickness=0)
        self.vsb = ttk.Scrollbar(lf, orient='vertical', command=self._on_vsb_move)
        self.list_canvas.configure(yscrollcommand=self._on_canvas_scroll, width=365)
        self.list_canvas.pack(side='left', fill='both', expand=True)
        self.vsb.pack(side='right', fill='y')
        self._vscroll = {}       # idx -> (AccountItem, window_id)
        self._shown = []
        self._item_h = 100       # 卡片固定高度(实测 AccountItem 约 97px,留余量)
        # 鼠标滚轮
        self.list_canvas.bind('<Enter>', lambda e: self._bind_wheel())
        self.list_canvas.bind('<Leave>', lambda e: self._unbind_wheel())
        self.list_canvas.bind('<Configure>', self._on_list_resize)
        self._build_middle(self.pw)
        self._build_right(self.pw)
        self._build_statusbar()
        self._refresh_group_bar()

    def _bind_wheel(self):
        self.root.bind_all('<MouseWheel>', self._on_wheel)

    def _unbind_wheel(self):
        self.root.unbind_all('<MouseWheel>')

    def _on_wheel(self, e):
        try:
            self.list_canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
            self._render_visible()
        except Exception:
            pass

    # 中面板: 删除组(按钮+速度同框) + 其他 + 安全组
    def load_groups(self):
        import json as _j
        try:
            p = os.path.join(tg_tool.SCRIPT_DIR, 'groups.json')
            if os.path.isfile(p):
                d = _j.load(open(p, encoding='utf-8'))
                if isinstance(d, dict):
                    return d
        except Exception:
            pass
        return {}

    def save_groups(self):
        import json as _j
        try:
            p = os.path.join(tg_tool.SCRIPT_DIR, 'groups.json')
            _j.dump(self.groups, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _refresh_group_bar(self):
        for w in self.group_bar.winfo_children():
            w.destroy()
        tags = ['all', 'ungrouped'] + list(self.groups.keys())
        for g in tags:
            label = {'all': '全部', 'ungrouped': '未分组'}.get(g, g)
            style = 'primary' if g == self.cur_group else 'secondary-outline'
            b = ttkb.Button(self.group_bar, text=label, bootstyle=style,
                            command=lambda gg=g: self._select_group(gg))
            b.pack(side='left', padx=(0, 4))
            if g not in ('all', 'ungrouped'):
                b.bind('<Button-3>', lambda e, gg=g: self._group_menu(gg, e))
        ttkb.Button(self.group_bar, text='＋', bootstyle='primary-outline',
                    width=2, command=self.on_group_new).pack(side='left')

    def _group_menu(self, g, event):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label='重命名', command=lambda: self.on_group_rename(g))
        m.add_command(label='删除分组', command=lambda: self.on_group_delete(g))
        m.tk_popup(event.x_root, event.y_root)

    def _select_group(self, g):
        self.cur_group = g
        self.refresh_accounts()

    def on_group_new(self):
        name = simpledialog.askstring('新建分组', '输入分组名称：', parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name or name in ('all', 'ungrouped') or name in self.groups:
            messagebox.showerror('无效', '分组名无效或已存在。')
            return
        self.groups[name] = []
        self.save_groups()
        self._select_group(name)

    def on_group_rename(self, g):
        new = simpledialog.askstring('重命名分组', f'将「{g}」重命名为：', initialvalue=g, parent=self.root)
        if not new or new.strip() == g:
            return
        new = new.strip()
        if new in ('all', 'ungrouped') or new in self.groups:
            messagebox.showerror('无效', '分组名无效或已存在。')
            return
        self.groups[new] = self.groups.pop(g, [])
        if self.cur_group == g:
            self.cur_group = new
        self.save_groups()
        self.refresh_accounts()

    def on_group_delete(self, g):
        if not messagebox.askyesno('删除分组', f'删除分组「{g}」？账号不会删除，会回到未分组。'):
            return
        self.groups.pop(g, None)
        if self.cur_group == g:
            self.cur_group = 'all'
        self.save_groups()
        self.refresh_accounts()

    def _make_section(self, parent, title):
        """创建可折叠功能组,返回内容 Frame。点击标题折叠/展开。"""
        sec = tk.LabelFrame(parent, text='', bg='white', fg=FG,
                            font=('Microsoft YaHei UI', 9))
        sec.pack(fill='x', pady=6)
        hdr = tk.Frame(sec, bg='white', cursor='hand2')
        hdr.pack(fill='x')
        lbl = tk.Label(hdr, text=f'▾ {title}', bg='white', fg=FG,
                       font=('Microsoft YaHei UI', 9, 'bold'))
        lbl.pack(side='left', padx=8, pady=4)
        body = tk.Frame(sec, bg='white')
        body.pack(fill='x')
        state = {'open': True}

        def toggle(e=None):
            if state['open']:
                body.pack_forget()
                lbl.configure(text=f'▸ {title}')
                state['open'] = False
            else:
                body.pack(fill='x')
                lbl.configure(text=f'▾ {title}')
                state['open'] = True

        hdr.bind('<Button-1>', toggle)
        lbl.bind('<Button-1>', toggle)
        return body

    def _build_middle(self, pw):
        middle = tk.Frame(self.pw, bg=PANEL_BG)
        self.pw.add(middle, weight=2)

        # 删除组
        delf = self._make_section(middle, '删除')
        r1 = tk.Frame(delf, bg='white')
        r1.pack(fill='x', padx=8, pady=(6, 2))
        self.btn_del_contacts = ttkb.Button(r1, text='删联系人', bootstyle='danger-outline',
                                            state='disabled', command=self.on_delete_contacts)
        self.btn_del_contacts.pack(side='left', expand=True, fill='x', padx=(0, 4))
        self.btn_del_dialogs = ttkb.Button(r1, text='删对话', bootstyle='danger-outline',
                                           state='disabled', command=self.on_delete_dialogs)
        self.btn_del_dialogs.pack(side='left', expand=True, fill='x', padx=4)
        r2 = tk.Frame(delf, bg='white')
        r2.pack(fill='x', padx=8, pady=2)
        self.btn_del_bots = ttkb.Button(r2, text='删机器人', bootstyle='danger-outline',
                                        state='disabled', command=self.on_delete_bots)
        self.btn_del_bots.pack(side='left', expand=True, fill='x', padx=(0, 4))
        self.btn_del_channels = ttkb.Button(r2, text='删频道', bootstyle='danger-outline',
                                            state='disabled', command=self.on_delete_channels)
        self.btn_del_channels.pack(side='left', expand=True, fill='x', padx=4)
        # 速度(和删除组同框)
        sf = tk.Frame(delf, bg='white')
        sf.pack(fill='x', padx=8, pady=(4, 6))
        tk.Label(sf, text='速度:', bg='white', fg=FG2,
                 font=('Microsoft YaHei UI', 8)).pack(side='left')
        self.speed_var = tk.StringVar(value='2')
        for i, (name, rng) in enumerate(
                [('极快', '0.2~0.4s'), ('快速', '0.4~0.6s'), ('默认', '0.9~1.4s'),
                 ('慢速', '1.3~1.6s'), ('极慢', '1.9~2.2s')], 1):
            rb = tk.Radiobutton(sf, text=f'{name}', variable=self.speed_var, value=str(i),
                                bg='white', font=('Microsoft YaHei UI', 8),
                                command=self._apply_speed)
            rb.pack(side='left', expand=True)

        # 基本信息组
        self._build_basic_info(middle)

        # 安全组
        self._build_security(middle)

        # 其他设置(置底)
        other = self._make_section(middle, '其他设置')
        of = tk.Frame(other, bg='white')
        of.pack(fill='x', padx=8, pady=6)
        self.btn_update = ttkb.Button(of, text='更新本体', bootstyle='secondary-outline',
                                      state='disabled', command=self.on_update)
        self.btn_update.pack(side='left', expand=True, fill='x', padx=(0, 4))
        self.btn_wl = ttkb.Button(of, text='白名单管理', bootstyle='secondary-outline',
                                  command=self.on_whitelist)
        self.btn_wl.pack(side='left', expand=True, fill='x', padx=4)

    # 右面板: 进度 + 日志
    def _build_right(self, pw):
        right = tk.Frame(self.pw, bg=PANEL_BG)
        self.pw.add(right, weight=2)

        # 进度区
        pf = tk.LabelFrame(right, text=' 进度 ', bg='white', fg=FG,
                           font=('Microsoft YaHei UI', 9))
        pf.pack(fill='x', pady=6)
        pin = tk.Frame(pf, bg='white')
        pin.pack(fill='x', padx=8, pady=(2, 2))
        self.task_lbl = tk.Label(pin, text='当前任务：无', bg='white', fg=FG,
                                 font=('Microsoft YaHei UI', 8), anchor='w')
        self.task_lbl.pack(fill='x')
        bar = tk.Frame(pin, bg='#E4E4E4', height=8)
        bar.pack(fill='x', pady=2)
        bar.pack_propagate(False)
        self.bar_fill = tk.Label(bar, bg='#5AA7E0', width=0)
        self.bar_fill.place(x=0, rely=0, relheight=1, relwidth=0)
        self.prog_lbl = tk.Label(pin, text='', bg='white', fg=FG2,
                                 font=('Microsoft YaHei UI', 8), anchor='w')
        self.prog_lbl.pack(fill='x')

        # 底部选项卡: 操作 / 日志
        self.nb = ttkb.Notebook(right)
        self.nb.pack(fill='both', expand=True, pady=6)

        # Tab 1: 操作(动态页面: 点击安全组按钮切换 passkey/邮箱/2fa)
        op_tab = tk.Frame(self.nb, bg='white')
        self.nb.add(op_tab, text=' 操作 ')
        self.sec_page = tk.Frame(op_tab, bg='white')
        self.sec_page.pack(fill='both', expand=True)
        # 结果提示区
        self.op_txt = tk.Text(op_tab, bg='white', fg=FG, height=5,
                              font=('Consolas', 9), relief='flat',
                              state='disabled', wrap='none')
        op_sb = ttk.Scrollbar(op_tab, orient='vertical', command=self.op_txt.yview)
        self.op_txt.configure(yscrollcommand=op_sb.set)
        self.op_txt.pack(side='left', fill='x', padx=(8, 0), pady=6)
        op_sb.pack(side='right', fill='y', pady=6)

        # Tab 2: 日志
        log_tab = tk.Frame(self.nb, bg='white')
        self.nb.add(log_tab, text=' 日志 ')
        self.log_txt = tk.Text(log_tab, bg='white', fg=FG,
                               font=('Consolas', 9), relief='flat',
                               state='disabled', wrap='none')
        lsb = ttk.Scrollbar(log_tab, orient='vertical', command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=lsb.set)
        self.log_txt.pack(side='left', fill='both', expand=True, padx=(8, 0), pady=6)
        lsb.pack(side='right', fill='y', pady=6)

    # 状态栏(底部)
    def _build_statusbar(self):
        self.status = tk.Frame(self.root, bg=PANEL_BG, height=38)
        self.status.pack(side='bottom', fill='x')
        self.status.pack_propagate(False)
        self.st_lbl = tk.Label(self.status, text='就绪', bg=PANEL_BG, fg=FG2,
                               font=('Microsoft YaHei UI', 9), anchor='w')
        self.st_lbl.pack(side='left', padx=10)
        self.btn_stop = ttkb.Button(self.status, text='■ 停止任务', bootstyle='danger-outline',
                                    state='disabled', command=self.on_stop)
        self.btn_stop.pack(side='right', padx=10, pady=3)

    # ---------- 基本信息组 ----------
    def _build_basic_info(self, middle):
        bf = self._make_section(middle, '基本信息')

        # 头像 + 姓名/用户名
        head = tk.Frame(bf, bg='white')
        head.pack(fill='x', padx=8, pady=(6, 2))
        self._bi_ph = tk.PhotoImage(width=48, height=48)
        self.bi_avatar = tk.Label(head, image=self._bi_ph, compound='center',
                                  width=48, height=48, bg='#CCCCCC', fg='white',
                                  font=('Microsoft YaHei UI', 16, 'bold'), text='-')
        self.bi_avatar.pack(side='left', padx=(0, 8))
        txt = tk.Frame(head, bg='white')
        txt.pack(side='left', fill='x', expand=True)
        self.bi_name = tk.Label(txt, text='未选择账号', bg='white', fg=FG,
                                font=('Microsoft YaHei UI', 10, 'bold'), anchor='w')
        self.bi_name.pack(fill='x')
        self.bi_uname = tk.Label(txt, text='', bg='white', fg=FG2,
                                 font=('Microsoft YaHei UI', 8), anchor='w')
        self.bi_uname.pack(fill='x')

        # 手机号 + 生日
        r = tk.Frame(bf, bg='white')
        r.pack(fill='x', padx=8, pady=(2, 0))
        self.bi_phone = tk.Label(r, text='', bg='white', fg=FG2,
                                 font=('Microsoft YaHei UI', 8), anchor='w')
        self.bi_phone.pack(side='left')
        self.bi_birth = tk.Label(r, text='', bg='white', fg=FG2,
                                 font=('Microsoft YaHei UI', 8), anchor='w')
        self.bi_birth.pack(side='left', padx=12)

        # 简介
        self.bi_about = tk.Label(bf, text='', bg='white', fg=FG2,
                                 font=('Microsoft YaHei UI', 8), anchor='w',
                                 wraplength=300, justify='left')
        self.bi_about.pack(fill='x', padx=8, pady=(2, 0))

        # 关联频道
        self.bi_channels = tk.Label(bf, text='', bg='white', fg=FG2,
                                    font=('Microsoft YaHei UI', 8), anchor='w')
        self.bi_channels.pack(fill='x', padx=8, pady=(2, 2))
        # 编辑按钮(在操作区编辑)
        ttkb.Button(bf, text='编辑', bootstyle='secondary-outline',
                    command=lambda: self._show_sec('edit')).pack(fill='x', padx=8, pady=(0, 6))

    def _build_edit_page(self, parent):
        """操作区: 基本信息编辑表单。"""
        if not self.connected:
            tk.Label(parent, text='请先连接账号再编辑。', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=10, pady=8)
            return
        a = self.cur or {}
        tk.Label(parent, text='编辑基本信息', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
        # 头像区
        av = tk.Frame(parent, bg='white')
        av.pack(fill='x', padx=10, pady=4)
        self._edit_ph = tk.PhotoImage(width=64, height=64)
        self.edit_avatar_lbl = tk.Label(av, image=self._edit_ph, compound='center',
                                        width=64, height=64, bg='#CCCCCC', fg='white',
                                        font=('Microsoft YaHei UI', 20, 'bold'), text='-')
        self.edit_avatar_lbl.pack(side='left', padx=(0, 8))
        ab = tk.Frame(av, bg='white')
        ab.pack(side='left')
        ttkb.Button(ab, text='从文件选择', bootstyle='secondary-outline',
                    command=self.on_change_avatar_file).pack(fill='x', pady=2)
        ttkb.Button(ab, text='从剪贴板', bootstyle='secondary-outline',
                    command=self.on_change_avatar_clipboard).pack(fill='x', pady=2)
        self._load_edit_avatar()
        f = tk.Frame(parent, bg='white')
        f.pack(fill='both', expand=True, padx=10, pady=4)

        tk.Label(f, text='名字:', bg='white', fg=FG2, font=('Microsoft YaHei UI', 9)).pack(anchor='w')
        fn = tk.Entry(f, font=('Microsoft YaHei UI', 9))
        fn.insert(0, a.get('display', '') or '')
        fn.pack(fill='x', pady=2)

        tk.Label(f, text='姓氏:', bg='white', fg=FG2, font=('Microsoft YaHei UI', 9)).pack(anchor='w')
        ln = tk.Entry(f, font=('Microsoft YaHei UI', 9))
        ln.pack(fill='x', pady=2)

        tk.Label(f, text='用户名(不带@):', bg='white', fg=FG2, font=('Microsoft YaHei UI', 9)).pack(anchor='w')
        un = tk.Entry(f, font=('Microsoft YaHei UI', 9))
        un.insert(0, a.get('username', '') or '')
        un.pack(fill='x', pady=2)

        tk.Label(f, text='简介:', bg='white', fg=FG2, font=('Microsoft YaHei UI', 9)).pack(anchor='w')
        ab = tk.Text(f, height=3, font=('Microsoft YaHei UI', 9))
        ab.insert('1.0', getattr(self, '_bi_about_raw', '') or '')
        ab.pack(fill='x', pady=2)

        tk.Label(f, text='生日(月/日/年,可留空):', bg='white', fg=FG2, font=('Microsoft YaHei UI', 9)).pack(anchor='w')
        br = tk.Frame(f, bg='white')
        br.pack(fill='x', pady=2)
        m = tk.Entry(br, width=4); m.pack(side='left', padx=(0, 4))
        d = tk.Entry(br, width=4); d.pack(side='left', padx=(0, 4))
        y = tk.Entry(br, width=6); y.pack(side='left')
        bd = getattr(self, '_bi_birth_raw', None)
        if bd:
            m.insert(0, str(bd[0])); d.insert(0, str(bd[1]))
            if bd[2]:
                y.insert(0, str(bd[2]))

        def save():
            self._apply_basic_edit(fn.get().strip(), ln.get().strip(), un.get().strip().lstrip('@'),
                                   ab.get('1.0', 'end').strip(), m.get().strip(),
                                   d.get().strip(), y.get().strip())
        ttkb.Button(f, text='保存', bootstyle='primary', command=save).pack(fill='x', pady=8)

    def _apply_basic_edit(self, fn, ln, un, about, m, d, y):
        a = self.cur or {}
        if un != (a.get('username', '') or ''):
            self.eng.update_username(un, on_done=lambda ok, r: _schedule(lambda: self._on_edit(ok, r, '用户名')))
        if fn or ln or about:
            self.eng.update_profile(first_name=fn or None, last_name=ln or None, about=about or None,
                                    on_done=lambda ok, r: _schedule(lambda: self._on_edit(ok, r, '资料')))
        if m.isdigit() and d.isdigit():
            year = int(y) if y.isdigit() else None
            self.eng.update_birthday(int(d), int(m), year,
                                     on_done=lambda ok, r: _schedule(lambda: self._on_edit(ok, r, '生日')))
        self.op('基本信息已提交更新')

    def _on_edit(self, ok, r, what):
        if ok:
            self.op(f'{what}已更新')
        else:
            messagebox.showerror(f'{what}更新失败', str(r)[:200])
        self._refresh_basic_info()

    def _load_edit_avatar(self):
        a = self.cur or {}
        p = a.get('avatar') or tg_profile.avatar_path(a.get('name', ''))
        if p and os.path.isfile(p):
            try:
                from PIL import Image, ImageTk
                im = Image.open(p).resize((64, 64))
                ph = ImageTk.PhotoImage(im)
                self.edit_avatar_lbl.configure(image=ph, text='')
                self.edit_avatar_lbl.image = ph
                return
            except Exception:
                pass
        self.edit_avatar_lbl.configure(image=self._edit_ph, text=(a.get('name', '')[:1] or '-'),
                                       bg=avatar_color(a.get('name', '')))

    def on_change_avatar_file(self):
        if not self.connected:
            messagebox.showinfo('未连接', '请先连接账号。')
            return
        from tkinter import filedialog
        p = filedialog.askopenfilename(parent=self.root, title='选择头像图片',
                                       filetypes=[('图片', '*.png *.jpg *.jpeg *.bmp *.webp'), ('所有文件', '*.*')])
        if not p:
            return
        try:
            from PIL import Image
            self._open_avatar_crop(Image.open(p))
        except Exception as e:
            messagebox.showerror('打开失败', str(e)[:200])

    def on_change_avatar_clipboard(self):
        if not self.connected:
            messagebox.showinfo('未连接', '请先连接账号。')
            return
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                messagebox.showerror('剪贴板无图片', '剪贴板里没有图片。')
                return
            self._open_avatar_crop(img)
        except Exception as e:
            messagebox.showerror('读取剪贴板失败', str(e)[:200])

    def _open_avatar_crop(self, img):
        """裁剪头像窗口: 拖动方形裁剪框,右侧圆形预览。"""
        from PIL import Image, ImageTk, ImageDraw
        win = tk.Toplevel(self.root)
        win.title('裁剪头像')
        win.configure(bg='white')
        win.transient(self.root)
        win.grab_set()

        max_disp = 360
        w, h = img.size
        scale = max_disp / max(w, h)
        dw, dh = int(w * scale), int(h * scale)
        disp = img.resize((dw, dh), Image.LANCZOS)

        cv = tk.Canvas(win, width=dw + 20, height=dh + 20, bg='#222', highlightthickness=0)
        cv.pack(side='left', padx=10, pady=10)
        self._crop_tk = ImageTk.PhotoImage(disp)
        cv.create_image(10, 10, image=self._crop_tk, anchor='nw')

        box = min(dw, dh)
        st = {'x': (dw - box) // 2 + 10, 'y': (dh - box) // 2 + 10}
        rect = cv.create_rectangle(st['x'], st['y'], st['x'] + box, st['y'] + box,
                                   outline='#FFD700', width=2)

        pv = tk.Label(win, bg='white')
        pv.pack(side='left', padx=10)

        def update_preview():
            ox = int((st['x'] - 10) / scale)
            oy = int((st['y'] - 10) / scale)
            osize = int(box / scale)
            crop = img.crop((ox, oy, ox + osize, oy + osize)).resize((120, 120), Image.LANCZOS)
            mask = Image.new('L', (120, 120), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 120, 120), fill=255)
            out = Image.new('RGBA', (120, 120), (0, 0, 0, 0))
            out.paste(crop, (0, 0), mask)
            self._crop_prev = ImageTk.PhotoImage(out)
            pv.configure(image=self._crop_prev)

        update_preview()

        drag = {'dx': None, 'dy': None}

        def press(e):
            if st['x'] <= e.x <= st['x'] + box and st['y'] <= e.y <= st['y'] + box:
                drag['dx'], drag['dy'] = e.x - st['x'], e.y - st['y']

        def move(e):
            if drag['dx'] is None:
                return
            nx = max(10, min(e.x - drag['dx'], 10 + dw - box))
            ny = max(10, min(e.y - drag['dy'], 10 + dh - box))
            st['x'], st['y'] = nx, ny
            cv.coords(rect, nx, ny, nx + box, ny + box)
            update_preview()

        def release(e):
            drag['dx'] = None

        cv.bind('<ButtonPress-1>', press)
        cv.bind('<B1-Motion>', move)
        cv.bind('<ButtonRelease-1>', release)

        def confirm():
            import io
            ox = int((st['x'] - 10) / scale)
            oy = int((st['y'] - 10) / scale)
            osize = int(box / scale)
            crop = img.crop((ox, oy, ox + osize, oy + osize)).resize((512, 512), Image.LANCZOS)
            buf = io.BytesIO()
            crop.convert('RGB').save(buf, 'PNG')
            win.destroy()
            self.eng.upload_avatar(buf.getvalue(), on_done=lambda ok, r: _schedule(
                lambda: self._on_avatar_upload(ok, r)))

        bf = tk.Frame(win, bg='white')
        bf.pack(pady=10)
        ttkb.Button(bf, text='确定', bootstyle='primary', command=confirm).pack(side='left', padx=6)
        ttkb.Button(bf, text='取消', bootstyle='secondary', command=win.destroy).pack(side='left', padx=6)

    def _on_avatar_upload(self, ok, r):
        if ok:
            self.op('头像已更新')
            self._load_edit_avatar()
            self._refresh_basic_info()
        else:
            messagebox.showerror('上传失败', str(r)[:200])

    def _refresh_basic_info(self):
        a = self.cur or {}
        name = a.get('display') or a.get('name', '') or '未选择账号'
        self.bi_name.configure(text=name)
        uname = a.get('username') or ''
        self.bi_uname.configure(text=f'@{uname}' if uname else '')
        phone = mask_phone(a.get('phone', '') or '')
        self.bi_phone.configure(text=phone or '')
        # 头像(无图用占位图+首字色块,保持 48x48)
        p = a.get('avatar') or tg_profile.avatar_path(a.get('name', ''))
        if p and os.path.isfile(p):
            try:
                from PIL import Image, ImageTk
                im = Image.open(p).resize((48, 48))
                ph = ImageTk.PhotoImage(im)
                self.bi_avatar.configure(image=ph, text='')
                self.bi_avatar.image = ph
            except Exception:
                self.bi_avatar.configure(image=self._bi_ph, text=(a.get('name', '')[:1] or '-'),
                                         bg=avatar_color(a.get('name', '')))
        else:
            self.bi_avatar.configure(image=self._bi_ph, text=(a.get('name', '')[:1] or '-'),
                                     bg=avatar_color(a.get('name', '')))
        # 简介/生日/频道(连接后从服务器拉)
        self.bi_about.configure(text='')
        self.bi_birth.configure(text='')
        self.bi_channels.configure(text='')
        if self.connected:
            self.eng.get_full_info(on_done=lambda ok, r: _schedule(
                lambda: self._on_full_info(ok, r)))

    def _on_full_info(self, ok, r):
        if not ok or not isinstance(r, dict):
            return
        about = r.get('about', '') or ''
        self._bi_about_raw = about
        self.bi_about.configure(text=f'简介：{about}' if about else '')
        bd = r.get('birthday')
        self._bi_birth_raw = None
        if bd:
            day = getattr(bd, 'day', '')
            month = getattr(bd, 'month', '')
            year = getattr(bd, 'year', None)
            self._bi_birth_raw = (month, day, year)
            s = f'生日：{month}月{day}日'
            if year:
                s += f' {year}'
            self.bi_birth.configure(text=s)
        chans = r.get('channels', []) or []
        self.bi_channels.configure(text=f'关联频道：{len(chans)} 个' if chans else '关联频道：无')

    # ---------- 安全组(按钮,点击后在操作Tab显示对应页面) ----------
    def _build_security(self, middle):
        sec = self._make_section(middle, '安全')
        r1 = tk.Frame(sec, bg='white')
        r1.pack(fill='x', padx=8, pady=(6, 2))
        ttkb.Button(r1, text='两步验证', bootstyle='secondary-outline',
                    command=lambda: self._show_sec('2fa')).pack(side='left', expand=True, fill='x', padx=(0, 3))
        ttkb.Button(r1, text='通行密钥', bootstyle='secondary-outline',
                    command=lambda: self._show_sec('passkey')).pack(side='left', expand=True, fill='x', padx=(3, 0))
        r2 = tk.Frame(sec, bg='white')
        r2.pack(fill='x', padx=8, pady=(0, 6))
        ttkb.Button(r2, text='邮箱登录', bootstyle='secondary-outline',
                    command=lambda: self._show_sec('email')).pack(side='left', expand=True, fill='x', padx=(0, 3))
        ttkb.Button(r2, text='登录设备', bootstyle='secondary-outline',
                    command=lambda: self._show_sec('devices')).pack(side='left', expand=True, fill='x', padx=(3, 0))

    def _show_sec(self, kind):
        """点击安全组按钮: 切到操作Tab并显示对应页面。"""
        self.nb.select(0)
        for w in self.sec_page.winfo_children():
            w.destroy()
        if kind == 'passkey':
            self._build_passkey_page(self.sec_page)
        elif kind == 'email':
            self._build_email_page(self.sec_page)
        elif kind == '2fa':
            self._build_tfa_page(self.sec_page)
        elif kind == 'devices':
            self._build_devices_page(self.sec_page)
        elif kind == 'edit':
            self._build_edit_page(self.sec_page)

    def _build_passkey_page(self, parent):
        tk.Label(parent, text='Passkey', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
        self.pk_list = tk.Frame(parent, bg='white')
        self.pk_list.pack(fill='both', expand=True, padx=10)
        self.qr_lbl = tk.Label(parent, bg='white')
        self.qr_lbl.pack(pady=(2, 4))
        ttkb.Button(parent, text='🔑 添加通行密钥', bootstyle='primary-outline',
                    command=self.on_passkey_add).pack(fill='x', padx=10, pady=(2, 8))
        self._load_passkeys()

    def _load_passkeys(self):
        if not self.connected:
            tk.Label(self.pk_list, text='（未连接账号）', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        self.eng.get_passkeys(on_done=lambda ok, r: _schedule(
            lambda: self._render_passkey_list(ok, r)))

    def _render_passkey_list(self, ok, r):
        for w in self.pk_list.winfo_children():
            w.destroy()
        if not ok:
            tk.Label(self.pk_list, text=f'读取失败: {str(r)[:120]}', bg='white', fg='#C0392B',
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        keys = r if isinstance(r, list) else []
        if not keys:
            tk.Label(self.pk_list, text='暂无通行密钥', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        for pk in keys:
            name = getattr(pk, 'name', '') or '（未命名）'
            kid = getattr(pk, 'id', '')
            date = getattr(pk, 'date', None)
            date_str = date.strftime('%Y年%m月%d日 %H:%M') if date else '时间未知'
            row = tk.Frame(self.pk_list, bg='white')
            row.pack(fill='x', pady=(4, 0))
            tk.Label(row, text=name, bg='white', fg=FG, anchor='w',
                     font=('Microsoft YaHei UI', 10)).pack(side='left', expand=True, fill='x')
            ttkb.Button(row, text='删除', bootstyle='danger-outline',
                        command=lambda i=kid: self._del_pk(i)).pack(side='right')
            tk.Label(self.pk_list, text=f'添加于 {date_str}', bg='white', fg=FG3, anchor='w',
                     font=('Microsoft YaHei UI', 8)).pack(fill='x', pady=(2, 0))
            tk.Frame(self.pk_list, bg=BORDER, height=1).pack(fill='x', pady=(4, 0))

    def _del_pk(self, kid):
        if not messagebox.askyesno('确认', '删除这个通行密钥？'):
            return
        self.eng.delete_passkey(kid, on_done=lambda ok, r: _schedule(
            lambda: self._on_del_pk(ok, r)))

    def _on_del_pk(self, ok, r):
        if ok:
            self.op('通行密钥已删除')
            self._load_passkeys()
        else:
            messagebox.showerror('删除失败', str(r)[:200])

    def _build_email_page(self, parent):
        tk.Label(parent, text='邮箱登录', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
        self.email_box = tk.Frame(parent, bg='white')
        self.email_box.pack(fill='both', expand=True, padx=10)
        self._load_email_status()

    def _load_email_status(self):
        for w in self.email_box.winfo_children():
            w.destroy()
        if not self.connected:
            tk.Label(self.email_box, text='（未连接账号）', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        self.eng.get_password_info(on_done=lambda ok, r: _schedule(
            lambda: self._render_email_status(ok, r)))

    def _render_email_status(self, ok, r):
        for w in self.email_box.winfo_children():
            w.destroy()
        if not ok:
            tk.Label(self.email_box, text='该账号不可绑定邮箱', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        email = getattr(r, 'email_unconfirmed_pattern', '') or ''
        has_recovery = bool(getattr(r, 'has_recovery', False))
        if email:
            tk.Label(self.email_box, text=f'当前邮箱（待验证）：{email}', bg='white', fg=FG,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=4)
        elif has_recovery:
            tk.Label(self.email_box, text='已绑定恢复邮箱', bg='white', fg=FG,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=4)
        else:
            tk.Label(self.email_box, text='未绑定邮箱，可添加：', bg='white', fg=FG,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(4, 2))
            r = tk.Frame(self.email_box, bg='white')
            r.pack(fill='x', pady=4)
            self.email_var = tk.StringVar()
            tk.Entry(r, textvariable=self.email_var, width=24).pack(side='left', padx=(0, 4))
            ttkb.Button(r, text='发送验证码', bootstyle='primary-outline',
                        command=self.on_email_send).pack(side='left')

    def _build_tfa_page(self, parent):
        tk.Label(parent, text='两步验证(2FA)', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
        r = tk.Frame(parent, bg='white')
        r.pack(fill='x', padx=10, pady=4)
        ttkb.Button(r, text='设置/修改密码', bootstyle='primary-outline',
                    command=self.on_2fa_set).pack(side='left', expand=True, fill='x')

    def _build_devices_page(self, parent):
        tk.Label(parent, text='登录设备', bg='white', fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
        self.dev_list = tk.Frame(parent, bg='white')
        self.dev_list.pack(fill='both', expand=True, padx=10)
        self._load_devices()

    def _load_devices(self):
        if not self.connected:
            tk.Label(self.dev_list, text='（未连接账号）', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        self.eng.get_authorizations(on_done=lambda ok, r: _schedule(
            lambda: self._render_devices(ok, r)))

    def _render_devices(self, ok, r):
        for w in self.dev_list.winfo_children():
            w.destroy()
        if not ok:
            tk.Label(self.dev_list, text=f'读取失败: {str(r)[:120]}', bg='white', fg='#C0392B',
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        auths = r if isinstance(r, list) else []
        if not auths:
            tk.Label(self.dev_list, text='暂无设备', bg='white', fg=FG3,
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=8)
            return
        for a in auths:
            is_current = bool(getattr(a, 'current', False))
            model = getattr(a, 'device_model', '') or '未知设备'
            app = getattr(a, 'app_name', '') or ''
            app_ver = getattr(a, 'app_version', '') or ''
            active = getattr(a, 'date_active', None)
            active_str = active.strftime('%Y年%m月%d日 %H:%M') if active else ''
            title = model
            if app:
                title += f' · {app} {app_ver}'.rstrip()
            row = tk.Frame(self.dev_list, bg='white')
            row.pack(fill='x', pady=(4, 0))
            tk.Label(row, text=title, bg='white', fg=FG, anchor='w',
                     font=('Microsoft YaHei UI', 10)).pack(side='left', expand=True, fill='x')
            if is_current:
                tk.Label(row, text='本设备', bg='white', fg=PRIMARY,
                         font=('Microsoft YaHei UI', 8, 'bold')).pack(side='right')
            else:
                ah = getattr(a, 'hash', 0)
                ttkb.Button(row, text='删除', bootstyle='danger-outline',
                            command=lambda h=ah: self._del_device(h)).pack(side='right')
            if active_str:
                tk.Label(self.dev_list, text=f'最后活跃 {active_str}', bg='white', fg=FG3,
                         font=('Microsoft YaHei UI', 8), anchor='w').pack(fill='x', pady=(2, 0))
            tk.Frame(self.dev_list, bg=BORDER, height=1).pack(fill='x', pady=(4, 0))

    def _del_device(self, ah):
        if not messagebox.askyesno('注销设备', '确定注销这个在线设备？该设备会被强制下线。'):
            return
        self.eng.reset_authorization(ah, on_done=lambda ok, r: _schedule(
            lambda: self._on_del_device(ok, r)))

    def _on_del_device(self, ok, r):
        if ok:
            self.op('设备已注销')
            self._load_devices()
        else:
            messagebox.showerror('注销失败', str(r)[:200])

    def on_security_refresh(self):
        """连接后刷新安全信息(2FA/邮箱/passkey)。"""
        pass

    def on_passkey_add(self):
        if not self._require_connected():
            return
        self.op('[passkey] 正在生成二维码…')
        self.eng.init_passkey_registration(on_done=lambda ok, r: _schedule(
            lambda: self._on_pk_init(ok, r)))

    def _on_pk_init(self, ok, data):
        if not ok:
            messagebox.showerror('生成失败', str(data)[:200])
            return
        try:
            import base64
            import qrcode
            from PIL import ImageTk
            # FIDO2 通行密钥二维码: fido:/ + base64url(WebAuthn options)
            b64 = base64.urlsafe_b64encode(data.encode('utf-8')).decode('ascii').rstrip('=')
            uri = f'fido:/{b64}'
            qr = qrcode.QRCode(border=2)
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white').resize((220, 220))
            self._qr_img = ImageTk.PhotoImage(img)
            self.qr_lbl.configure(image=self._qr_img)
            self.op('[passkey] 请用手机扫码完成绑定，完成后自动刷新')
            self.eng.get_passkeys(on_done=lambda ok2, r2: _schedule(
                lambda: self._start_pk_poll(ok2, r2)))
        except Exception as e:
            messagebox.showerror('生成二维码失败', str(e)[:200])

    def _start_pk_poll(self, ok, r):
        self._pk_base = len(r) if (ok and isinstance(r, list)) else 0
        self._pk_poll(0)

    def _pk_poll(self, tries):
        if tries > 90:
            self.op('[passkey] 未检测到新密钥，可稍后手动刷新')
            self.qr_lbl.configure(image='')
            return
        self.eng.get_passkeys(on_done=lambda ok, r: _schedule(
            lambda: self._check_pk_added(ok, r, tries)))

    def _check_pk_added(self, ok, r, tries):
        n = len(r) if (ok and isinstance(r, list)) else 0
        if ok and n > getattr(self, '_pk_base', 0):
            self.op(f'[passkey] 绑定完成，共 {n} 个密钥')
            self.qr_lbl.configure(image='')
            self._load_passkeys()
            return
        self.root.after(2000, lambda: self._pk_poll(tries + 1))

    def on_email_send(self):
        if not self._require_connected():
            return
        email = self.email_var.get().strip()
        if not email or '@' not in email:
            messagebox.showerror('参数错误', '请输入有效邮箱地址。')
            return
        self.eng.send_verify_email_code(email, on_done=lambda ok, r: _schedule(
            lambda: self._on_email_sent(ok, r, email)))

    def _on_email_sent(self, ok, r, email):
        if not ok:
            messagebox.showerror('发送失败', str(r)[:200])
            return
        self.op(f'验证码已发送到 {email}')
        code = simpledialog.askstring('验证邮箱', f'请输入发送到 {email} 的验证码：', parent=self.root)
        if not code:
            return
        self.eng.verify_email(code.strip(), on_done=lambda ok2, r2: _schedule(
            lambda: self._on_email_verified(ok2, r2)))

    def _on_email_verified(self, ok, r):
        if ok:
            self.op('邮箱绑定成功')
            self.on_security_refresh()
        else:
            messagebox.showerror('验证失败', str(r)[:200])

    def on_2fa_set(self):
        if not self._require_connected():
            return
        self.eng.get_password_info(on_done=lambda ok, r: _schedule(
            lambda: self._ask_2fa_password(ok, r)))

    def _ask_2fa_password(self, ok, r):
        if not ok:
            messagebox.showerror('读取失败', str(r)[:200])
            return
        has2fa = bool(getattr(r, 'has_password', False))
        cur = ''
        if has2fa:
            cur = simpledialog.askstring('2FA', '当前已开启 2FA，请输入当前密码：', parent=self.root, show='*')
            if not cur:
                return
        new = simpledialog.askstring('2FA', '请输入新的两步验证密码：', parent=self.root, show='*')
        if not new:
            return
        new2 = simpledialog.askstring('2FA', '再次输入新密码确认：', parent=self.root, show='*')
        if new != new2:
            messagebox.showerror('错误', '两次输入的密码不一致。')
            return
        self.eng.set_2fa(cur, new, on_done=lambda ok2, r2: _schedule(
            lambda: self._on_2fa_done(ok2, r2)))

    def _on_2fa_done(self, ok, r):
        if ok:
            self.op('2FA 设置成功')
            self.on_security_refresh()
        else:
            messagebox.showerror('设置失败', str(r)[:200])

    # ---------- 账号列表 ----------
    def refresh_accounts(self):
        """重扫账号并按搜索词过滤重建列表。"""
        for idx, (it, wid) in self._vscroll.items():
            self.list_canvas.delete(wid)
            it.destroy()
        self._vscroll = {}
        self._shown = []
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
                # 头像: profiles.json 存的绝对路径优先(跨目录也能用)
                if p.get('avatar'):
                    a['avatar'] = p['avatar']
                # 显示名: first+last 优先(用户名称),否则文件夹名
                if p.get('first') or p.get('last'):
                    a['display'] = (str(p.get('first') or '') + ' ' +
                                    str(p.get('last') or '')).strip()
                self.accounts.append(a)

        # 分组过滤
        grouped = set()
        for names in self.groups.values():
            for n in names:
                grouped.add(n)
        q = (self.search_var.get() or '').strip().lower()
        shown = []
        for a in self.accounts:
            name = a.get('name', '')
            if self.cur_group == 'ungrouped':
                if name in grouped:
                    continue
            elif self.cur_group != 'all':
                if name not in self.groups.get(self.cur_group, []):
                    continue
            if not q:
                shown.append(a)
                continue
            hay = ' '.join(str(a.get(k) or '') for k in
                           ('name', 'display', 'username', 'phone', 'uid'))
            cc, cname = country_of(a.get('phone', '') or '')
            if q in hay.lower() or (cname and q in cname.lower()):
                shown.append(a)

        # 虚拟滚动: 只渲染可见卡片,滚动时动态增删
        self._shown = shown
        self.list_canvas.configure(scrollregion=(0, 0, 0, max(len(shown) * self._item_h, 1)))
        self.list_canvas.yview_moveto(0)
        self._render_visible()

    def _on_vsb_move(self, *args):
        self.list_canvas.yview(*args)
        self._render_visible()

    def _on_canvas_scroll(self, first, last):
        self.vsb.set(first, last)
        self._render_visible()

    def _on_list_resize(self, e=None):
        self._render_visible()

    def _render_visible(self):
        h = self.list_canvas.winfo_height()
        if h <= 0 or not self._shown:
            return
        y0 = int(self.list_canvas.canvasy(0))
        first = max(0, y0 // self._item_h - 2)
        last = min(len(self._shown), (y0 + h) // self._item_h + 3)
        # 销毁移出范围的
        for idx in [i for i in self._vscroll if i < first or i >= last]:
            it, wid = self._vscroll.pop(idx)
            self.list_canvas.delete(wid)
            it.destroy()
        # 创建移入范围的
        for idx in range(first, last):
            if idx not in self._vscroll:
                a = self._shown[idx]
                it = AccountItem(self.list_canvas, a,
                                 on_click=self._pick_item, on_double=self._connect_item,
                                 on_right=self.on_account_menu)
                y = idx * self._item_h
                wid = self.list_canvas.create_window((0, y), window=it,
                                                     anchor='nw', width=365, height=self._item_h)
                self._vscroll[idx] = (it, wid)
                if self.cur and self.cur.get('name') == a.get('name'):
                    it.set_selected(True)
                    self.cur_item = it

    def _pick_item(self, item):
        if self.cur_item and self.cur_item is not item:
            self.cur_item.set_selected(False)
        self.cur_item = item
        self.cur = item.acc
        item.set_selected(True)
        a = item.acc
        self.top_name.configure(text=a['name'])
        self._set_top_avatar(a)
        sub = mask_phone(a.get('phone', '') or '') or a.get('state', '')
        if a.get('uid'):
            sub += f'   id {a["uid"]}' if sub else f'id {a["uid"]}'
        self.top_sub.configure(text=sub or '双击连接')
        self.set_status('已选中（双击连接）' if not self.connected else '已选中（双击切换连接）')
        self._refresh_basic_info()

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
        self._set_top_avatar(a)
        self._set_task_buttons('normal')
        self.btn_disconnect.configure(state='normal')
        self.on_security_refresh()
        self._refresh_basic_info()

    def _set_top_avatar(self, a):
        """顶栏头像: 有缓存图显示图,否则首字色块(48x48)。"""
        p = a.get('avatar') or tg_profile.avatar_path(a.get('name', ''))
        if p and os.path.isfile(p):
            try:
                from PIL import Image, ImageTk
                im = Image.open(p).resize((48, 48))
                ph = ImageTk.PhotoImage(im)
                self.top_avatar.configure(image=ph, text='')
                self.top_avatar.image = ph
                return
            except Exception:
                pass
        self.top_avatar.configure(image=self._top_ph, text=(a.get('name', '')[:1] or '-'),
                                  bg=avatar_color(a.get('name', '')))

    def on_disconnect(self):
        if not self.connected:
            return
        self.eng.disconnect()
        self.connected = False
        self.top_dot.configure(text='● 未连接', fg=FG3)
        self.top_name.configure(text=self.cur['name'] if self.cur else '未选择账号')
        self.top_sub.configure(text='双击左侧账号连接')
        self._set_top_avatar(self.cur or {})
        self.set_status('已断开')
        self.btn_disconnect.configure(state='disabled')
        self._set_task_buttons('disabled')
        self.log('已断开连接')

    def on_reconnect(self):
        if not self.cur:
            messagebox.showinfo('未选择账号', '请先双击左侧账号选择。')
            return
        if self.busy:
            messagebox.showinfo('任务运行中', '请先停止当前任务。')
            return
        self._pending_connect = self.cur
        self.set_status('正在重连…')
        self.top_dot.configure(text='● 连接中', fg='#E67E22')
        self.log(f'正在重连账号 {self.cur["name"]} …')
        self.eng.connect(self.cur['path'])

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
        self._delete_by_type('users')

    def on_delete_bots(self):
        self._delete_by_type('bots')

    def on_delete_channels(self):
        self._delete_by_type('groups')

    def _delete_by_type(self, dtype):
        if not self._require_connected():
            return
        self._pending_delete_type = dtype
        self._start_task('扫描对话')
        self.eng.scan_dialogs()

    def _ask_scope(self, data):
        """扫描完成后,按待删类型弹确认框。"""
        dtype = getattr(self, '_pending_delete_type', 'users')
        users = data.get('users', 0)
        deleted = data.get('deleted', 0)
        bots = data.get('bots', 0)
        groups = data.get('groups', 0)
        keepu = data.get('keep_users', 0)
        keepg = data.get('keep_groups', 0)

        if dtype == 'users':
            n = users + deleted
            label = '删除全部私聊'
            desc = f'普通私聊 {users} 个 + 已注销 {deleted} 个'
        elif dtype == 'bots':
            n = bots
            label = '拉黑并删除全部机器人'
            desc = f'机器人 {bots} 个'
        else:
            n = groups
            label = '退出全部群组/频道'
            desc = f'群组/频道 {groups} 个'

        if n == 0:
            messagebox.showinfo('无需操作', f'没有可删除项：{desc}。')
            self._end_task()
            return
        if not messagebox.askyesno('确认删除',
                                   f'{label}\n{desc}\n白名单保留 {keepu} 用户 + {keepg} 群。\n确认执行？'):
            self._end_task()
            return
        self._apply_speed()
        self._start_task(label)
        self.eng.delete_dialogs(dtype)

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
        for b in (self.btn_del_contacts, self.btn_del_dialogs, self.btn_del_bots,
                  self.btn_del_channels, self.btn_update):
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

    def op(self, line):
        """写「操作」选项卡(安全类操作的状态/结果)。"""
        ts = __import__('time').strftime('%H:%M:%S')
        self.op_txt.configure(state='normal')
        self.op_txt.insert('end', f'{ts} {line}\n')
        self.op_txt.see('end')
        self.op_txt.configure(state='disabled')

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
        self._save_geometry()
        self.eng.shutdown()
        self.root.after(150, self.root.destroy)

    def _load_geometry(self):
        import json as _j
        try:
            p = os.path.join(SCRIPT_DIR, 'settings.json')
            if os.path.isfile(p):
                s = _j.load(open(p, encoding='utf-8'))
                return s.get('geometry', '')
        except Exception:
            pass
        return ''

    def _save_geometry(self):
        import json as _j
        try:
            p = os.path.join(SCRIPT_DIR, 'settings.json')
            s = {}
            if os.path.isfile(p):
                try:
                    s = _j.load(open(p, encoding='utf-8'))
                except Exception:
                    s = {}
            s['geometry'] = self.root.geometry()
            try:
                s['sashes'] = [self.pw.sashpos(0), self.pw.sashpos(1)]
            except Exception:
                pass
            _j.dump(s, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _restore_sashes(self):
        import json as _j
        try:
            p = os.path.join(SCRIPT_DIR, 'settings.json')
            if not os.path.isfile(p):
                return
            s = _j.load(open(p, encoding='utf-8'))
            sashes = s.get('sashes')
            if isinstance(sashes, list) and len(sashes) == 2:
                self.pw.sashpos(0, int(sashes[0]))
                self.pw.sashpos(1, int(sashes[1]))
        except Exception:
            pass

    def on_launch(self):
        a = self.cur
        if not a:
            messagebox.showinfo('未选择账号', '请先选择账号。')
            return
        exe = os.path.join(a.get('path', ''), 'Telegram.exe')
        if not os.path.isfile(exe):
            messagebox.showerror('未找到', '该账号目录没有 Telegram.exe。')
            return
        try:
            import subprocess
            subprocess.Popen([exe], cwd=a.get('path', ''))
            self.log(f'已启动 {a.get("name", "")} 的 Telegram')
        except Exception as e:
            messagebox.showerror('启动失败', str(e)[:200])

    def on_pack_account(self):
        a = self.cur
        if not a:
            messagebox.showinfo('未选择账号', '请先选择账号。')
            return
        self._pack_account(a)

    def _pack_account(self, a):
        path = a.get('path', '')
        name = a.get('name', '')
        zip_path = os.path.join(ROOT, f'{name}_账号包.zip')
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for entry in os.listdir(path):
                    full = os.path.join(path, entry)
                    low = entry.lower()
                    if low == 'tdata':
                        for root2, dirs, files in os.walk(full):
                            for f in files:
                                fp = os.path.join(root2, f)
                                zf.write(fp, os.path.relpath(fp, path))
                    elif entry.endswith('.session') or entry.endswith('.session-journal'):
                        zf.write(full, entry)
                    elif entry.endswith('.json') and tg_tool._is_account_json(full):
                        zf.write(full, entry)
                    elif low == '2fa.txt':
                        zf.write(full, entry)
        except Exception as e:
            messagebox.showerror('打包失败', str(e)[:200])
            return
        self.log(f'已打包 {name} -> {os.path.basename(zip_path)}')
        messagebox.showinfo('打包完成', f'已打包到：\n{zip_path}')

    def on_account_menu(self, item, event):
        self._pick_item(item)
        m = tk.Menu(self.root, tearoff=0)
        gm = tk.Menu(m, tearoff=0)
        gm.add_command(label='未分组', command=lambda: self._move_account_to_group(item.acc.get('name', ''), 'ungrouped'))
        for g in self.groups:
            gm.add_command(label=g, command=lambda gg=g: self._move_account_to_group(item.acc.get('name', ''), gg))
        m.add_cascade(label='移动到组', menu=gm)
        m.add_command(label='打包', command=lambda: self._pack_account(item.acc))
        m.add_separator()
        m.add_command(label='删除账号', command=lambda: self.on_delete_account(item.acc))
        m.tk_popup(event.x_root, event.y_root)

    def _move_account_to_group(self, name, group):
        for g in self.groups:
            if name in self.groups[g]:
                self.groups[g].remove(name)
        if group != 'ungrouped':
            self.groups.setdefault(group, []).append(name)
        self.save_groups()
        self._refresh_group_bar()
        self.refresh_accounts()

    def on_delete_account(self, a):
        name = a.get('name', '')
        path = a.get('path', '')
        if not messagebox.askyesno('删除账号', f'确定删除账号「{name}」？\n将删除整个文件夹：\n{path}\n\n此操作不可恢复！'):
            return
        try:
            import shutil
            shutil.rmtree(path)
        except Exception as e:
            messagebox.showerror('删除失败', str(e)[:200])
            return
        for g in self.groups:
            if name in self.groups[g]:
                self.groups[g].remove(name)
        self.save_groups()
        self.accounts = []
        self.refresh_accounts()
        self._refresh_group_bar()
        self.log(f'已删除账号 {name}')

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


