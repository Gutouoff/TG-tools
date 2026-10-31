<script lang="ts">
  import { onMount, flushSync } from 'svelte';
  import { t } from './texts';
  import {
    getAccounts,
    connectAccount,
    disconnect,
    switchAccount,
    getOnline,
    postTask,
    connectWS,
    setSpeed,
    updateTelegram,
    getWhitelist,
    addWhitelistUser,
    addWhitelistGroup,
    removeWhitelistUser,
    removeWhitelistGroup,
    getPasskeys,
    deletePasskey,
    initPasskey,
    registerPasskey,
    get2FA,
    set2FA,
    sendEmailCode,
    verifyEmailCode,
    getDevices,
    deleteDevice,
    getProfile,
    updateProfile,
    updateUsername,
    updateBirthday,
    uploadAvatar,
    getGroups,
    createGroup,
    renameGroup,
    reorderGroups,
    moveAccount,
    convertTdata,
    importArchive,
    exportAccounts,
    packAccount,
    refreshAvatar,
    getSettings,
    saveSettings,
    getMe,
    getRecv,
    setRecv,
    getDialogs,
    getHistory,
    joinChats,
    sendChatMsg,
    launchClient,
    openFolder,
    getEmail,
    renameAccount,
    getRenamePending,
    runRenamePending,
    cancelRenamePending,
    type RenamePending,
    pollAccounts,
    convertToTdata,
    refreshSession,
    refreshSsBatch,
    startChat,
    deleteAccount,
    addAccount,
    qrLoginStart,
    qrLoginPoll,
    qrLoginCancel,
    phoneLoginStart,
    phoneLoginSubmit,
    getPing,
    getLogs,
    TOKEN,
    type Account,
    type LogEvent,
    type LogLevel,
    type LogItem,
  } from './api';
  import LogView from './components/LogView.svelte';
  import ContextMenu from './components/ContextMenu.svelte';
  import TopBar from './components/TopBar.svelte';
  import GroupRenameDialog from './components/GroupRenameDialog.svelte';
  import GroupDeleteDialog from './components/GroupDeleteDialog.svelte';
  import GroupCreateDialog from './components/GroupCreateDialog.svelte';
  import DeleteAccountDialog from './components/DeleteAccountDialog.svelte';
  import AccountCard from './components/AccountCard.svelte';
  import FunctionCards from './components/FunctionCards.svelte';
  import JoinView from './components/JoinView.svelte';
  import SecurityViews from './components/SecurityViews.svelte';
  import ProfileView from './components/ProfileView.svelte';
  import ChatView from './components/ChatView.svelte';
  import SettingsDialog from './components/SettingsDialog.svelte';
  import MobileApp from './components/MobileApp.svelte';
  import AddAccountDialog from './components/AddAccountDialog.svelte';

  const AVATAR_COLORS = ['#E17076', '#7BC862', '#65AADD', '#A695E7', '#EE7AAE', '#6EC9CB', '#FAA774', '#FFA6C9'];

  let accounts = $state<Account[]>([]);
  let filtered = $state<Account[]>([]);
  let filterVersion = $state(0);
  let search = $state('');
  let current = $state<Account | null>(null);
  let connected = $state(false);
  // 连接/重连进行中的提示文案(顶栏状态),空=不在连接中
  let connectingLabel = $state('');
  let logs = $state<LogItem[]>([]);
  // 程序版本号(顶栏显示,来自后端 APP_VERSION)
  let appVersion = $state('');
  let progress = $state({ done: 0, total: 0, label: '' });

  function avatarColor(name: string): string {
    let h = 0;
    for (const c of name) h = (h * 31 + c.charCodeAt(0)) | 0;
    return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
  }

  let avatarFailed = $state<Set<string>>(new Set());
  // 卡片折叠记忆
  let cardOpen = $state<Record<string, boolean>>({});
  // 恢复保存的折叠状态前,忽略浏览器对初始 open 属性派发的 toggle 事件,
  // 否则默认状态会被写回 settings.json 覆盖用户保存的值
  let cardOpenRestored = false;
  function onCardToggle(name: string, open: boolean) {
    if (!cardOpenRestored) return;
    cardOpen = { ...cardOpen, [name]: open };
    saveSettings({ card_open: cardOpen }).catch(() => {});
  }
  function isCardOpen(name: string, def: boolean): boolean {
    return cardOpen[name] ?? def;
  }
  // 卡片排序(settings.card_order 逗号分隔持久化)
  const DEFAULT_CARD_ORDER = ['基本信息', '聊天', '安全', '删除', '转换', '其他设置'];
  let cardOrder = $state<string[]>([...DEFAULT_CARD_ORDER]);
  function parseCardOrder(v: unknown): string[] {
    const names = typeof v === 'string' ? v.split(',').map((x) => x.trim()).filter(Boolean) : [];
    const valid = names.filter((n) => DEFAULT_CARD_ORDER.includes(n));
    // 去重并补齐缺失项(防 settings.json 被手改坏)
    return [...new Set([...valid, ...DEFAULT_CARD_ORDER])];
  }
  // 预设色彩主题(Chrome 风格圆盘)
  const PRESET_COLORS = ['#356AE6', '#229ED9', '#2A6D7D', '#3F51B5', '#9C27B0', '#EC407A', '#E53935', '#F2994A', '#66BB6A', '#00BCD4', '#795548', '#607D8B'];
  function isPreset(): boolean {
    return PRESET_COLORS.some((c) => c.toLowerCase() === ((settings.theme_seed as string) || '').toLowerCase());
  }
  function applyPreset(c: string) {
    settings = { ...settings, theme_seed: c };
    applyTheme();
    saveSettings(settings).catch(() => {});
  }
  function setThemeMode(mode: string) {
    settings = { ...settings, theme_mode: mode };
    applyTheme();
    saveSettings(settings).catch(() => {});
  }
  function moveCard(i: number, dir: number) {
    const j = i + dir;
    if (j < 0 || j >= cardOrder.length) return;
    const next = [...cardOrder];
    [next[i], next[j]] = [next[j], next[i]];
    cardOrder = next;
    settings = { ...settings, card_order: cardOrder.join(',') };
    saveSettings({ card_order: settings.card_order }).catch(() => {});
  }
  function onAvatarError(name: string) {
    const next = new Set(avatarFailed);
    next.add(name);
    avatarFailed = next;
  }
  function avatarUrl(a: Account): string {
    // v 参数跟随头像文件更新时间变化,绕开 WebView2 对同 URL 的旧图缓存
    const v = (a as any).avatar_v || a.avatar || '';
    return `/api/avatar-image?name=${encodeURIComponent(a.name)}&v=${encodeURIComponent(String(v))}&token=${encodeURIComponent(TOKEN)}`;
  }

  function applyFilter() {
    // 关键词覆盖: 账号名/姓名/username/手机号/用户ID;
    // '@' 前缀忽略;纯数字关键词按手机号/ID 的数字部分匹配(免输区号)
    const raw = search.trim().toLowerCase();
    const q = raw.replace(/^@+/, '');
    const digits = q.replace(/\D/g, '');
    const base = groupFiltered();
    const result = !q
      ? [...base]
      : base.filter((a) => {
          const hay = `${a.name} ${a.display} ${a.username} ${a.phone} ${a.uid}`.toLowerCase();
          if (hay.includes(q)) return true;
          if (digits && digits.length >= 3) {
            const phoneDigits = String(a.phone ?? '').replace(/\D/g, '');
            const uidDigits = String(a.uid ?? '').replace(/\D/g, '');
            if (phoneDigits.includes(digits) || uidDigits.includes(digits)) return true;
          }
          return false;
        });
    filtered.splice(0, filtered.length, ...result);
    filterVersion++;
  }

  let searchTimer: ReturnType<typeof setTimeout> | undefined;
  function onSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilter, 300);
  }

  function stampNow(): string {
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }

  function classifyLog(line: string): LogLevel {
    if (/失败|错误|异常|崩溃/.test(line)) return 'error';
    if (/警告|超时|未找到|不可用|重试/.test(line)) return 'warn';
    return 'info';
  }

  function addLog(line: string, level: LogLevel = 'info', ts?: string) {
    // 客户端提示也按关键字着色,和服务端判定保持一致
    if (level === 'info' && !ts) level = classifyLog(line);
    // $state 深代理可直接 push,避免每条日志整组拷贝(O(n))
    logs.push({ ts: ts || stampNow(), level, msg: line });
    if (logs.length > 2000) logs.splice(0, logs.length - 2000);
    // 日志视图自动滚到最底,免手动滑动
    if (rightView === 'log') {
      setTimeout(() => {
        const el = document.querySelector('.log');
        if (el) el.scrollTop = el.scrollHeight;
      }, 0);
    }
  }

  async function loadLogHistory() {
    try {
      const r = await getLogs(800);
      const items = Array.isArray(r?.items) ? r.items : [];
      if (!items.length) return;
      const seen = new Set(logs.map((e) => `${e.ts}|${e.msg}`));
      const older = items.filter((e) => !seen.has(`${e.ts}|${e.msg}`));
      if (!older.length) return;
      flushSync(() => {
        logs = [...older, ...logs];
        if (logs.length > 2000) logs.splice(0, logs.length - 2000);
      });
    } catch {
      // 历史加载失败不影响实时日志
    }
  }

  async function loadAccounts() {
    const acc = await getAccounts();
    flushSync(() => {
      accounts = acc;
      applyFilter();
    });
  }

  // 待执行改名(文件夹被占用时排队,占用解除后后端自动改名): old → new
  let renamePending = $state<Record<string, string>>({});
  async function loadRenamePending() {
    try {
      const r = await getRenamePending();
      const items: RenamePending[] = r.items || [];
      flushSync(() => {
        renamePending = Object.fromEntries(
          items.filter((i) => i.old && i.new).map((i) => [i.old, i.new]));
      });
    } catch {
      // 拉取失败不影响主流程
    }
  }
  async function doRunRenamePending() {
    try {
      const r = await runRenamePending();
      const left = (r.items || []).length;
      addLog(left ? `待执行重命名：还有 ${left} 个文件夹被占用` : '待执行重命名：已全部完成');
      await loadRenamePending();
      await loadAccounts();
    } catch (e: any) {
      addLog(`执行待重命名异常：${e?.message ?? e}`);
    }
  }
  async function doCancelRenamePending(oldName: string) {
    try {
      await cancelRenamePending(oldName);
      addLog(`已取消待重命名：${oldName}`);
      await loadRenamePending();
    } catch (e: any) {
      addLog(`取消待重命名异常：${e?.message ?? e}`);
    }
  }

  async function onConnect(a: Account, reconnect = false) {
    // 已在线的账号直接秒切,不重连
    if (onlineNames.has(a.name) && current?.name !== a.name) {
      await onSwitch(a);
      return;
    }
    current = a;
    connectingLabel = reconnect ? '重新连接…' : '连接中…';
    addLog(`${reconnect ? '正在重新连接' : '正在连接'} ${a.name} …`);
    try {
      await doConnectFlow(a);
    } finally {
      connectingLabel = '';
    }
  }

  async function doConnectFlow(a: Account) {
    const r = await connectAccount(a.path);
    if (r.ok && r.info) {
      const uname = r.info.username || '';
      if (uname) {
        a.username = uname;
        applyFilter();
      }
      // 同步整个连接池的在线状态(多账号同时在线)
      if (Array.isArray(r.online) && r.online.length) {
        onlineNames = new Set(r.online.map((x: any) => x.name));
      } else {
        markOnline(a.name, true);
      }
      addLog(`已连接 ${a.name}${uname ? ` (@${uname})` : ''}`);
      // 右栏自动回到日志页,避免停留在上一个账号的视图(资料/会话等)
      if (rightView !== 'log') setView('log');
      // 连接成功: 后端已自动拉取会话列表并开启消息接收,前端直接就绪
      if (Array.isArray(r.dialogs) && r.dialogs.length) {
        dialogs = r.dialogs;
      }
      loadRecv();
      // 连接成功后刷新一次头像
      try {
        const av = await refreshAvatar(a.name);
        if (av.ok && av.info && av.info.avatar) {
          a.avatar = av.info.avatar;
          (a as any).avatar_v = String(Date.now());
          avatarFailed = new Set([...avatarFailed].filter((n) => n !== a.name));
          applyFilter();
        }
      } catch (e) {
        // 忽略头像刷新失败
      }
    } else {
      addLog(`连接失败：${r.msg || '未知错误'}`);
    }
  }

  // 秒切到已在线账号(连接池,不重连)
  async function onSwitch(a: Account) {
    const r = await switchAccount(a.name);
    if (r.ok && r.info) {
      current = a;
      connected = true;
      flushSync(() => {
        onlineNames = new Set([...onlineNames, a.name]);
      });
      addLog(`已切换到 ${a.name}（保持在线）`);
      // 右栏自动回到日志页,避免停留在上一个账号的视图
      if (rightView !== 'log') setView('log');
    } else {
      addLog(`切换失败：${r.msg || '未知错误'}`);
      markOnline(a.name, false);
    }
  }

  async function doDisconnect() {
    await disconnect(current?.name);
    connected = false;
    if (current) markOnline(current.name, false);
    addLog(`已断开连接${current ? `: ${current.name}` : ''}`);
  }

  // 断开池中指定账号(其他账号保持在线)
  async function disconnectOne(name: string) {
    await disconnect(name);
    markOnline(name, false);
    if (current?.name === name) connected = false;
    addLog(`已断开连接：${name}`);
  }
  async function doReconnect() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    await onConnect(current, true);
  }

  // 启动当前账号目录内的 Telegram 便携版客户端
  async function doLaunchClient() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    const r = await launchClient(current.path);
    addLog(r.ok ? `已启动客户端：${current.name}（${r.msg}）` : `启动客户端失败：${r.msg}`);
  }

  // 右键「启动客户端」: 在资源管理器中打开账号文件夹
  async function doOpenAccountFolder() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    const r = await openFolder(current.path);
    if (!r.ok) addLog(`打开文件夹失败：${r.msg}`);
  }

  // 账号轮询: 逐号登录保活+测活(后台任务,进度/结果走日志页)
  async function doPollAccounts() {
    setView('log');
    const scope = curGroup === 'all' ? '全部账号' : curGroup === 'ungrouped' ? '未分组' : `分组「${curGroup}」`;
    addLog(`开始账号轮询（范围：${scope}，逐号登录保活并检测状态，每号间隔 1 秒）…`);
    const r = await pollAccounts(curGroup);
    if (!r.ok) addLog(`轮询启动失败：${r.msg}`);
  }

  // 格式转换: session+json → tdata(二级确认弹窗;覆盖勾选默认不选)
  let convOpen = $state(false);
  let converting = $state(false);
  let convOverwrite = $state(false);
  let convTwofa = $state('');
  function doOpenConvertTdata() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    convOverwrite = false;
    convTwofa = '';
    convOpen = true;
  }
  async function doConvertTdataConfirm() {
    if (!current || converting) return;
    const target = current;
    const overwrite = convOverwrite;
    const twofa = convTwofa.trim();
    convOpen = false;            // 点确认立即关弹窗,结果看日志页
    setView('log');
    converting = true;
    try {
      const r = await convertToTdata(target.path, overwrite, twofa);
      if (r.ok) {
        addLog(`已转换出 tdata: ${r.path}`);
        await loadAccounts();
      } else {
        addLog(`转换失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`转换异常：${e?.message ?? e}`);
    } finally {
      converting = false;
    }
  }

  // tdata → s+s: 覆盖刷新会话(修复过期 ss;在线账号只刷 json)
  let t2sOpen = $state(false);
  let t2sConverting = $state(false);
  function doOpenTdataToSs() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    t2sOpen = true;
  }
  async function doTdataToSsConfirm() {
    if (!current || t2sConverting) return;
    const target = current;
    t2sOpen = false;             // 点确认立即关弹窗,结果看日志页
    setView('log');
    t2sConverting = true;
    try {
      const r = await refreshSession(target.path);
      if (r.ok) {
        addLog(`已从 tdata 刷新 session+json: ${target.name}`);
        await loadAccounts();
      } else {
        addLog(`刷新失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`刷新异常：${e?.message ?? e}`);
    } finally {
      t2sConverting = false;
    }
  }

  // 批量刷新 s+s 数据: 所有有 tdata 且测活失败的离线账号(后台任务)
  async function doRefreshSsBatch() {
    setView('log');
    addLog('开始批量刷新 session（仅处理有 tdata 且登录态失效的账号，每号间隔 1 秒）');
    const r = await refreshSsBatch();
    if (!r.ok) addLog(`批量刷新启动失败：${r.msg}`);
  }

  // 删除账号(二级确认): 弹窗醒目显示将被删除的文件夹,勾选确认才能执行
  let delOpen = $state(false);
  let delTarget = $state<Account | null>(null);
  let delConfirm = $state(false);
  let deleting = $state(false);
  function doOpenDeleteAccount() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    delTarget = current;
    delConfirm = false;
    delOpen = true;
  }
  async function doDeleteAccount() {
    if (!delTarget || deleting || !delConfirm) return;
    const target = delTarget;
    deleting = true;
    try {
      const r = await deleteAccount(target.path);
      if (r.ok) {
        addLog(`已删除账号：${target.name}（${r.deleted_path}）`);
        delOpen = false;
        if (current?.name === target.name) current = null;
        markOnline(target.name, false);
        await loadAccounts();
      } else {
        addLog(`删除失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`删除异常：${e?.message ?? e}`);
    } finally {
      deleting = false;
    }
  }

  // 新建账号(顶栏): 拖入 session/json/tdata/zip 建号;扫码登录标签页
  let addAccOpen = $state(false);
  let addAccTab = $state<'files' | 'qr' | 'phone'>('files');
  let addAccDragging = $state(false);
  let addAccFiles = $state<Array<{ name: string; data: string }>>([]);
  let addAccBusy = $state(false);
  // 扫码登录
  let qrImg = $state('');
  let qrSession = $state('');
  let qrStatus = $state('');      // '' / loading / waiting / expired / error / success
  let qrRemain = $state(0);
  let qrErr = $state('');
  let qrTimer: ReturnType<typeof setTimeout> | undefined;

  function doOpenAddAccount() {
    addAccFiles = [];
    addAccTab = 'files';
    phoneReset();
    addAccOpen = true;
  }
  async function doStartQrLogin() {
    addAccTab = 'qr';
    if (qrSession) return;   // 已在登录中,不重复生成
    qrStatus = 'loading';
    qrErr = '';
    qrImg = '';
    try {
      const r = await qrLoginStart('');
      if (r.ok && r.img) {
        qrImg = r.img;
        qrSession = r.session || '';
        qrStatus = 'waiting';
        qrPollLoop();
      } else {
        qrStatus = 'error';
        qrErr = r.msg || '二维码生成失败';
      }
    } catch (e: any) {
      qrStatus = 'error';
      qrErr = e?.message ?? String(e);
    }
  }
  async function qrPollLoop() {
    if (!qrSession || !addAccOpen || addAccTab !== 'qr') return;
    try {
      const r = await qrLoginPoll(qrSession);
      if (r.status === 'waiting') {
        qrStatus = 'waiting';
        qrRemain = (r as any).remain ?? 0;
        qrTimer = setTimeout(qrPollLoop, 1500);
      } else if (r.status === 'success' && r.user) {
        qrStatus = 'success';
        addLog(`[扫码] 登录成功：${r.user.display}（+${r.user.phone}），已创建账号 ${r.user.name}`);
        qrSession = '';
        addAccOpen = false;
        await loadAccounts();
      } else if (r.status === 'expired') {
        qrStatus = 'expired';
        qrSession = '';
      } else {
        qrStatus = 'error';
        qrErr = r.msg || '登录失败';
      }
    } catch {
      qrTimer = setTimeout(qrPollLoop, 3000);   // 网络抖动继续轮询
    }
  }
  async function closeAddAcc(cancelQr = false) {
    clearTimeout(qrTimer);
    if (qrSession) {
      if (cancelQr || qrStatus !== 'success') {
        qrLoginCancel(qrSession).catch(() => {});
      }
    }
    if (phoneSession) {
      qrLoginCancel(phoneSession).catch(() => {});   // 同一个取消清理
    }
    qrSession = '';
    qrImg = '';
    qrStatus = '';
    qrErr = '';
    phoneReset();
    addAccOpen = false;
  }

  // 手机号登录: phone(输号码) → code(输验证码) → password(2FA) → 成功
  let phoneStage = $state<'phone' | 'code' | 'password'>('phone');
  let phoneInput = $state('');
  let phoneCode = $state('');
  let phonePwd = $state('');
  let phoneSession = $state('');
  let phoneErr = $state('');
  let phoneBusy = $state(false);

  async function doPhoneLoginStart() {
    const p = phoneInput.trim().replace(/\s/g, '');
    if (!p || phoneBusy) return;
    phoneBusy = true;
    phoneErr = '';
    try {
      const r = await phoneLoginStart(p);
      // Svelte 5: await 后赋值需 flushSync 驱动条件渲染(项目已知坑)
      if (r.ok && r.session) {
        flushSync(() => {
          phoneSession = r.session;
          phoneStage = 'code';
        });
      } else {
        flushSync(() => {
          phoneErr = r.msg || '验证码发送失败';
        });
      }
    } catch (e: any) {
      flushSync(() => {
        phoneErr = e?.message ?? String(e);
      });
    } finally {
      phoneBusy = false;
    }
  }
  async function doPhoneLoginSubmit() {
    if (phoneBusy) return;
    phoneBusy = true;
    phoneErr = '';
    try {
      const r = await phoneLoginSubmit(phoneSession, phoneCode.trim(), phonePwd);
      if (r.status === 'need_password') {
        flushSync(() => {
          phoneStage = 'password';
        });
      } else if (r.status === 'success' && r.user) {
        addLog(`[手机登录] 登录成功：${r.user.display}（+${r.user.phone}），已创建账号 ${r.user.name}`);
        flushSync(() => {
          phoneSession = '';
          addAccOpen = false;
        });
        await loadAccounts();
      } else {
        flushSync(() => {
          phoneErr = r.msg || '登录失败';
        });
      }
    } catch (e: any) {
      flushSync(() => {
        phoneErr = e?.message ?? String(e);
      });
    } finally {
      phoneBusy = false;
    }
  }
  function phoneReset() {
    if (phoneSession) qrLoginCancel(phoneSession).catch(() => {});
    phoneSession = '';
    phoneStage = 'phone';
    phoneCode = '';
    phonePwd = '';
    phoneErr = '';
  }

  function addAccAccept(f: File): boolean {
    const n = f.name.toLowerCase();
    return n.endsWith('.session') || n.endsWith('.json') || n.endsWith('.zip')
      || n === '2fa.txt' || n.startsWith('2fa.txt.');
  }
  async function addAccReadFile(f: File): Promise<{ name: string; data: string }> {
    const buf = await f.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let bin = '';
    const CH = 8192;
    for (let i = 0; i < bytes.length; i += CH) {
      bin += String.fromCharCode(...bytes.subarray(i, i + CH));
    }
    return { name: f.name, data: btoa(bin) };
  }
  async function onAddAccDrop(e: DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    addAccDragging = false;
    const files = Array.from(e.dataTransfer?.files || []);
    const items = files.filter(addAccAccept);
    if (!items.length) {
      addLog('[新建] 未识别到可用文件（需要 .session / .json / .zip / 2fa.txt）');
      return;
    }
    addAccBusy = true;
    try {
      const read = await Promise.all(items.map(addAccReadFile));
      addAccFiles = [...addAccFiles, ...read];
    } catch (err: any) {
      addLog(`[新建] 读取文件失败：${err?.message ?? err}`);
    } finally {
      addAccBusy = false;
    }
  }
  function onAddAccDragOver(e: DragEvent) {
    e.preventDefault();
    addAccDragging = true;
  }
  function addAccRemove(i: number) {
    addAccFiles = addAccFiles.filter((_, k) => k !== i);
  }
  async function doAddAccountConfirm() {
    if (!addAccFiles.length || addAccBusy) return;
    addAccBusy = true;
    try {
      const r = await addAccount(addAccFiles);
      if (r.ok) {
        addLog(`[新建] ${r.msg}`);
        addAccOpen = false;
        await loadAccounts();
      } else {
        addLog(`[新建] 失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`[新建] 异常：${e?.message ?? e}`);
    } finally {
      addAccBusy = false;
    }
  }

  // 文件夹重命名弹窗
  let renameOpen = $state(false);
  let renameTarget = $state<Account | null>(null);
  let renameInput = $state('');
  let renaming = $state(false);
  function openRename(a: Account) {
    renameTarget = a;
    renameInput = a.name;
    renameOpen = true;
  }
  // 重命名快捷项: 姓名/username/手机号(无加号)/用户ID,可在设置里开关+自定义前缀
  const RENAME_QUICK_DEFS: Array<[string, string]> = [
    ['display', '姓名'], ['username', 'username'], ['phone', '手机号'], ['uid', '用户ID'],
  ];
  let renameQuickOpts = $derived(
    ((settings.rename_quick as string[]) || [])
      .map((k) => RENAME_QUICK_DEFS.find((d) => d[0] === k))
      .filter(Boolean) as Array<[string, string]>,
  );
  function renameQuickVal(key: string): string {
    const a: any = renameTarget;
    if (!a) return '';
    if (key === 'display') return (a.display || '').trim();
    if (key === 'username') return a.username || '';
    if (key === 'phone') return String(a.phone || '').replace(/^\+/, '').trim();
    if (key === 'uid') return String(a.uid || '').trim();
    return '';
  }
  function applyRenameQuick(key: string, label: string) {
    const val = renameQuickVal(key);
    if (!val) {
      addLog(`该账号没有${label}，无法填充`);
      return;
    }
    renameInput = String(settings.rename_prefix ?? '') + val;
  }
  function toggleRenameQuick(key: string) {
    const cur = new Set<string>((settings.rename_quick as string[]) || []);
    if (cur.has(key)) cur.delete(key);
    else cur.add(key);
    settings = { ...settings, rename_quick: [...cur] };
  }
  async function doRename() {
    if (!renameTarget || renaming) return;
    const newName = renameInput.trim();
    if (!newName) return;
    if (newName === renameTarget.name) {
      renameOpen = false;
      return;
    }
    renaming = true;
    try {
      const r = await renameAccount(renameTarget.path, newName);
      if (r.ok && r.pending) {
        // 文件夹被占用: 已加入待执行,客户端关闭后自动改名
        addLog(`已加入待执行：${renameTarget.name} → ${newName}（该账号客户端关闭后自动重命名）`);
        renameOpen = false;
        await loadRenamePending();
        await loadAccounts();
      } else if (r.ok) {
        addLog(`已重命名：${renameTarget.name} → ${newName}`);
        renameOpen = false;
        if (current?.name === renameTarget.name) current = null;
        markOnline(renameTarget.name, false);
        await loadAccounts();
      } else {
        addLog(`重命名失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`重命名异常：${e?.message ?? e}`);
    } finally {
      renaming = false;
    }
  }
  async function doPack() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    const r = await packAccount(current.path, current.name);
    addLog(r.ok ? `打包完成：${r.msg}` : `打包失败：${r.msg}`);
  }

  // 在线账号集合(头像右下角橘点)
  let onlineNames = $state<Set<string>>(new Set());
  function markOnline(name: string, on: boolean) {
    const next = new Set(onlineNames);
    if (on) next.add(name);
    else next.delete(name);
    onlineNames = next;
  }

  async function doRefreshAccountInfo() {
    // 仅刷新当前账号的头像/资料(替代原「一键获取头像」全量刷新)
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    addLog(`正在刷新账号信息：${current.name} …`);
    try {
      const r = await refreshAvatar(current.name);
      if (r.ok && r.info) {
        if (r.info.avatar) {
          current.avatar = r.info.avatar;
          // v 参数变化才会重新请求头像(URL 不同绕开 WebView2 缓存)
          (current as any).avatar_v = String(Date.now());
          avatarFailed = new Set([...avatarFailed].filter((n) => n !== current!.name));
        }
        if (r.info.first || r.info.last) {
          current.display = `${r.info.first || ''} ${r.info.last || ''}`.trim();
        }
        if (r.info.username) current.username = r.info.username;
        // 刷新成功=账号活着,立即摘掉轮询死号标识(后端已同步 poll_results)
        (current as any).poll_alive = true;
        applyFilter();
        addLog(`已刷新账号信息：${current.name}`);
      } else {
        addLog(`刷新失败：${r.msg || (r.info ? '未知错误' : '该账号无 session 或登录态失效')}`);
      }
    } catch (e: any) {
      addLog(`刷新异常：${e?.message ?? e}`);
    }
  }

  // 速度分段(五档: 极快/快速/默认/慢速/极慢)
  let speedVal = $state(3);
  const SPEED_SEG: Array<[string, number]> = [
    ['极快', 1],
    ['快速', 2],
    ['默认', 3],
    ['慢速', 4],
    ['极慢', 5],
  ];
  function onSpeed(v: number) {
    speedVal = v;
    setSpeed(v);
  }

  // 设置
  let settings = $state<Record<string, any>>({});
  let settingsOpen = $state(false);
  let settingsSection = $state<'general' | 'appearance' | 'proxy' | 'join' | 'whitelist' | 'about'>('general');
  // 手机端设置采用「分组列表 → 子页」的钻取结构，null 表示停留在列表页
  let mobileSettingsSection = $state<'general' | 'appearance' | 'proxy' | 'join' | 'whitelist' | 'about' | null>(null);
  function openSettingsSection(s: 'general' | 'appearance' | 'proxy' | 'join' | 'whitelist' | 'about') {
    settingsSection = s;
    mobileSettingsSection = s;
    if (s === 'whitelist') loadWhitelist();
  }
  let themeMode = $derived((settings.theme_mode as string) || 'light');
  async function loadSettings() {
    settings = {
      pack_naming: '{name}_账号包', pack_password: '',
      theme_seed: '#356AE6', theme_bg: '#F9FAFC', theme_dark: '#EDF0F5', theme_topbar: '#FFFFFF', theme_mode: 'light', card_order: '基本信息,聊天,安全,删除,其他设置',
      proxy_mode: 'none', proxy_scheme: 'socks5', proxy_host: '', proxy_port: '',
      join_links: [],
      log_level: 'info',
      rename_quick: ['display', 'username', 'phone', 'uid'],
      rename_prefix: '',
      email_presets: [],
    };
    settingsOpen = true;
    // 每次打开都回到设置列表页，避免停在上次的子页
    mobileSettingsSection = null;
    try {
      settings = await getSettings();
      applyJoinEntries(settings.join_links);
      applyEmailPresets(settings.email_presets);
      applyTheme();
    } catch (e) {
      // 保持默认值
    }
  }
  function openSettings(section: typeof settingsSection) {
    settingsSection = section;
    loadSettings();
  }
  const settingsMeta: Record<string, { title: string; description: string; icon: string; group: string }> = {
    general: { title: '通用', description: '配置默认行为与文件处理方式。', icon: '⚙', group: '配置' },
    appearance: { title: '外观', description: '选择界面模式、颜色主题与功能区排列。', icon: '◐', group: '配置' },
    proxy: { title: '代理', description: '配置 Telegram 连接所使用的网络代理。', icon: '⇄', group: '配置' },
    join: { title: '加群频道', description: '维护登录时可快速填入的邮箱与常用群组、频道入口。', icon: '↗', group: '工具' },
    whitelist: { title: '白名单', description: '保护指定用户与群组，避免被删除任务处理。', icon: '✓', group: '保护' },
    about: { title: '关于', description: '查看当前版本与项目相关信息。', icon: 'i', group: '帮助' }
  };
  function settingsInfo() {
    return settingsMeta[settingsSection] || settingsMeta.general;
  }
  async function doSaveSettings() {
    settings = { ...settings, join_links: joinEntries, email_presets: emailPresets };
    await saveSettings(settings);
    settingsOpen = false;
    addLog('设置已保存');
    applyTheme();
  }
  let exporting = $state(false);
  async function doExportAccounts() {
    if (exporting) return;
    exporting = true;
    try {
      const r = await exportAccounts();
      if (r.ok) {
        addLog(`表格已更新并打开（${r.count ?? '?'} 个账号）：${r.path || '账号总表.xlsx'}`);
      } else {
        addLog(`导出失败：${r.msg || '未知错误'}`);
      }
    } catch (e: any) {
      addLog(`导出失败：${e?.message ?? e}`);
    } finally {
      exporting = false;
    }
  }
  function toggleTheme() {
    settings = { ...settings, theme_mode: settings.theme_mode === 'dark' ? 'light' : 'dark' };
    applyTheme();
    saveSettings(settings).catch(() => {});
  }
  function applyTheme() {
    const mode = (settings.theme_mode as string) || 'light';
    document.documentElement.dataset.theme = mode;
    if (mode === 'dark') {
      // 深色模式用 app.css 的 data-theme 变量集,不覆盖系统色
      const root = document.documentElement.style;
      root.removeProperty('--md-sys-color-primary');
      root.removeProperty('--md-sys-color-surface');
      root.removeProperty('--md-sys-color-surface-container');
      root.removeProperty('--topbar-color');
      return;
    }
    const seedValue = (settings.theme_seed as string) || '#356AE6';
    const bgValue = (settings.theme_bg as string) || '#F9FAFC';
    const darkValue = (settings.theme_dark as string) || '#EDF0F5';
    const topbarValue = (settings.theme_topbar as string) || '#FFFFFF';
    // 旧版默认青绿色只在内存中迁移，避免旧设置把新主题覆盖掉。
    const seed = seedValue.toUpperCase() === '#009688' ? '#356AE6' : seedValue;
    const bg = bgValue.toUpperCase() === '#F7FAF9' ? '#F9FAFC' : bgValue;
    const dark = darkValue.toUpperCase() === '#FFFFFF' ? '#EDF0F5' : darkValue;
    const topbar = topbarValue.toUpperCase() === '#00796B' ? '#FFFFFF' : topbarValue;
    const root = document.documentElement.style;
    root.setProperty('--md-sys-color-primary', seed);
    root.setProperty('--md-sys-color-surface', bg);
    root.setProperty('--md-sys-color-surface-container', dark);
    root.setProperty('--topbar-color', topbar);
  }

  async function showWhitelist() {
    const wl = await getWhitelist();
    addLog(`白名单用户：${wl.users.join(', ') || '无'}`);
    addLog(`白名单群组/频道：${wl.groups.join(', ') || '无'}`);
  }

  // 右栏视图
  let rightView = $state<'log' | 'passkey' | '2fa' | 'email' | 'devices' | 'profile' | 'settings' | 'chat' | 'join'>('log');
  let mobileTab = $state<'accounts' | 'current' | 'activity' | 'more'>('accounts');
  let mobilePanelOpen = $state(false);

  function openMobilePanel(v: typeof rightView) {
    setView(v);
    mobilePanelOpen = true;
  }
  function closeMobilePanel() {
    mobilePanelOpen = false;
    setView('log');
  }
  // 日志页的「返回」目标: 从哪个界面点进日志,就回哪个界面
  let lastView = $state<typeof rightView>('log');
  function setView(v: typeof rightView) {
    flushSync(() => {
      if (v === 'log' && rightView !== 'log') lastView = rightView;
      rightView = v;
      if (v === 'chat') chatUnread = 0;
    });
    // 切回日志页时滚到最新一条
    if (v === 'log') {
      setTimeout(() => {
        const el = document.querySelector('.log');
        if (el) el.scrollTop = el.scrollHeight;
      }, 0);
    }
  }

  // ---------- 聊天: 消息接收 / 加群频道 ----------
  let dialogs = $state<any[]>([]);
  let dialogsLoading = $state(false);
  let curDialog = $state<any | null>(null);
  let historyMsgs = $state<any[]>([]);
  let historyLoading = $state(false);
  let historyHasMore = $state(false);
  let historyError = $state('');
  let chatUnread = $state(0);
  let recvOn = $state(false);
  let recvRules = $state<Record<string, boolean>>({
    exclude_channels: true, exclude_groups: false, exclude_bots: false,
  });
  // 加群频道条目(备注名 + 链接 + 类型),持久化在 settings.join_links
  let joinEntries = $state<Array<{ name: string; link: string; type: string }>>([]);

  function applyJoinEntries(raw: any) {
    if (Array.isArray(raw)) {
      joinEntries = raw.map((e: any) => ({
        name: String(e?.name ?? ''),
        link: String(e?.link ?? ''),
        type: e?.type === 'channel' ? 'channel' : 'group',
      }));
    } else if (typeof raw === 'string' && raw) {
      // 兼容旧格式(每行一个链接)
      joinEntries = raw.split('\n').map((s) => s.trim()).filter(Boolean)
        .map((link) => ({ name: '', link, type: 'group' }));
    } else {
      joinEntries = [];
    }
  }

  // 打开右栏加群频道控制视图
  function openJoinView() {
    setView('join');
  }
  // 加群频道一体化管理: 本页增删改(即时持久化到 settings.join_links)
  let joinEditIdx = $state(-1);
  async function persistJoinEntries() {
    settings = { ...settings, join_links: joinEntries };
    try {
      await saveSettings({ join_links: joinEntries });
    } catch {
      addLog('[加群] 链接保存失败（本次改动未持久化）');
    }
  }
  function doJoinAddEntry() {
    joinEntries = [...joinEntries, { name: '', link: '', type: 'group' }];
    joinEditIdx = joinEntries.length - 1;
  }
  async function doJoinSaveEdit(i: number) {
    const e = joinEntries[i];
    if (!e) return;
    if (!e.link.trim()) {
      addLog('[加群] 链接不能为空');
      return;
    }
    joinEditIdx = -1;
    await persistJoinEntries();
  }
  function doJoinCancelEdit() {
    // 新添加但没填链接的条目,取消时直接移除
    if (joinEditIdx >= 0 && !joinEntries[joinEditIdx]?.link.trim()) {
      joinEntries = joinEntries.filter((_, k) => k !== joinEditIdx);
    }
    joinEditIdx = -1;
  }
  async function doJoinDelete(i: number) {
    joinEntries = joinEntries.filter((_, k) => k !== i);
    joinEditIdx = -1;
    await persistJoinEntries();
  }

  // ---------- 会话列表 / 聊天记录 ----------
  async function loadDialogs() {
    if (!current || !onlineNames.has(current.name)) {
      addLog('请先连接账号');
      return;
    }
    dialogsLoading = true;
    try {
      const r = await getDialogs(current.name);
      if (r.ok) {
        dialogs = r.dialogs || [];
      } else {
        addLog(`会话获取失败：${r.msg || '未知错误'}`);
      }
    } catch (e: any) {
      addLog(`会话获取异常：${e?.message ?? e}`);
    } finally {
      dialogsLoading = false;
    }
  }
  async function openDialog(d: any) {
    curDialog = d;
    historyMsgs = [];
    historyHasMore = false;
    historyError = '';
    await loadHistory(true);
    scrollHistoryBottom();
  }
  async function loadHistory(initial: boolean) {
    if (!curDialog || !current || historyLoading) return;
    historyLoading = true;
    try {
      const offset = initial ? 0 : (historyMsgs[0]?.id ?? 0);
      const r = await getHistory(current.name, curDialog.id, 20, offset);
      if (r.ok) {
        historyError = '';
        const older = (r.msgs || []).slice().reverse();  // 新->旧 反转为旧->新
        historyMsgs = initial ? older : [...older, ...historyMsgs];
        historyHasMore = (r.msgs || []).length >= 20;
      } else {
        historyError = r.msg || '未知错误';
        addLog(`记录获取失败：${r.msg || '未知错误'}`);
      }
    } catch (e: any) {
      historyError = String(e?.message ?? e);
      addLog(`记录获取异常：${historyError}`);
    } finally {
      historyLoading = false;
    }
  }
  function scrollHistoryBottom() {
    setTimeout(() => {
      const el = document.querySelector('.chat-history');
      if (el) el.scrollTop = el.scrollHeight;
    }, 30);
  }
  // 发送文本消息(目前仅适配文本)
  let chatDraft = $state('');
  let sending = $state(false);
  async function doSendMsg() {
    const text = chatDraft.trim();
    if (!text || !current || !curDialog || sending) return;
    sending = true;
    try {
      const r = await sendChatMsg(current.name, curDialog.id, text);
      if (r.ok && (r as any).msg && typeof (r as any).msg === 'object') {
        historyMsgs = [...historyMsgs, (r as any).msg];
        chatDraft = '';
        scrollHistoryBottom();
      } else {
        addLog(`[发送失败] ${(r as any).msg || '未知错误'}`);
      }
    } catch (e: any) {
      addLog(`[发送异常] ${e?.message ?? e}`);
    } finally {
      sending = false;
    }
  }
  // 直接发起聊天: 自动识别 @用户名 / 纯数字 ID / t.me 链接
  let startChatName = $state('');
  let startingChat = $state(false);
  function detectChatTarget(raw: string) {
    let v = (raw || '').trim();
    if (!v) return { kind: '', value: '', label: '' };
    const link = v.match(/^(?:https?:\/\/)?(?:t(?:elegram)?\.me|telegram\.me)\/(?:s\/)?([^/?#\s]+)\/?$/i);
    if (link) v = link[1];
    v = v.replace(/^@/, '');
    if (!v) return { kind: '', value: '', label: '' };
    if (/^-?\d+$/.test(v)) return { kind: 'id', value: v, label: v };
    return { kind: 'username', value: v, label: `@${v}` };
  }
  let startChatTarget = $derived(detectChatTarget(startChatName));
  async function doStartChat() {
    const u = startChatTarget.value;
    if (!u || startingChat) return;
    if (!current || !onlineNames.has(current.name)) {
      addLog('请先连接账号');
      return;
    }
    startingChat = true;
    try {
      const r = await startChat(current.name, u);
      if (r.ok && r.dialog) {
        startChatName = '';
        await openDialog(r.dialog);
      } else {
        addLog(`发起聊天失败：${r.msg || '未找到该用户'}`);
      }
    } catch (e: any) {
      addLog(`发起聊天异常：${e?.message ?? e}`);
    } finally {
      startingChat = false;
    }
  }
  async function loadRecv() {
    try {
      const r = await getRecv();
      recvOn = r.on;
      recvRules = { ...recvRules, ...r.rules };
    } catch {}
  }
  async function applyRecv(on: boolean, rules?: Record<string, boolean>) {
    const previousOn = recvOn;
    const previousRules = { ...recvRules };
    recvOn = on;
    if (rules) recvRules = { ...recvRules, ...rules };
    try {
      const r = await setRecv(recvOn, recvRules);
      recvOn = r.on;
      recvRules = { ...recvRules, ...r.rules };
      addLog(recvOn ? '[消息接收] 已开启' : '[消息接收] 已关闭');
    } catch (e: any) {
      recvOn = previousOn;
      recvRules = previousRules;
      addLog(`[消息接收] 设置失败：${e?.message ?? e}`);
    }
  }
  function onRecvRuleChange(key: string) {
    applyRecv(recvOn, { ...recvRules, [key]: !recvRules[key] });
  }
  async function doJoinOne(e: { name: string; link: string; type: string }) {
    if (!e.link) return;
    if (!current || !onlineNames.has(current.name)) {
      addLog('[加群] 请先连接账号');
      return;
    }
    addLog(`[加群] 正在加入 ${e.name || e.link} …`);
    try {
      const r = await joinChats([e.link]);
      if (r.ok) {
        const res = (r.results ?? [])[0];
        addLog(`[加群] ${e.name || e.link}: ${res?.ok ? '成功' : `失败 ${res?.err ?? ''}`}`);
      } else {
        addLog(`[加群] 失败：${r.msg}`);
      }
    } catch (err: any) {
      addLog(`[加群] 失败：${err?.message ?? err}`);
    }
  }
  async function doJoinChats() {
    const links = joinEntries.map((e) => e.link.trim()).filter(Boolean);
    if (!links.length) {
      addLog('[加群] 链接列表为空');
      return;
    }
    addLog(`[加群] 开始加入 ${links.length} 个链接…(结果见下方日志)`);
    try {
      const r = await joinChats(links);
      if (r.ok) {
        const okN = (r.results ?? []).filter((x: any) => x.ok).length;
        addLog(`[加群] 完成： 成功 ${okN}/${(r.results ?? []).length}`);
      } else {
        addLog(`[加群] 失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`[加群] 失败：${e?.message ?? e}`);
    }
  }
  let passkeys = $state<any[]>([]);
  let devices = $state<any[]>([]);
  let has2fa = $state(false);
  let emailInput = $state('');
  let codeInput = $state('');
  let new2fa = $state('');
  let cur2fa = $state('');

  async function loadPasskeys() {
    setView('passkey');
    const r = await getPasskeys();
    passkeys = r.ok ? r.passkeys : [];
  }
  async function loadDevices() {
    setView('devices');
    const r = await getDevices();
    devices = r.ok ? r.devices : [];
  }
  async function load2FA() {
    setView('2fa');
    const r = await get2FA();
    has2fa = r.has_2fa ?? false;
  }
  function showEmail() {
    showEmailView();
  }
  async function doDeletePasskey(id: string) {
    await deletePasskey(id);
    addLog('通行密钥已删除');
    await loadPasskeys();
  }
  let pkQrImg = $state('');
  async function doInitPasskey() {
    try {
      addLog('正在生成通行密钥二维码…');
      const r = await initPasskey();
      if (!r.ok) {
        addLog(`生成失败：${r.msg || JSON.stringify(r)}`);
        return;
      }
      pkQrImg = `data:image/png;base64,${r.img}`;
      addLog('[通行密钥] 请用手机扫描二维码，经蓝牙连接完成注册');
    } catch (e) {
      addLog(`生成异常：${String(e)}`);
    }
  }
  async function doDeleteDevice(hash: number) {
    await deleteDevice(hash);
    addLog('设备已注销');
    await loadDevices();
  }
  // 邮箱登录: 已绑邮箱本地持久化(login_email);预选邮箱一键填入
  let boundEmail = $state('');
  let showEmailForm = $state(false);
  let emailPresets = $state<string[]>([]);
  function applyEmailPresets(raw: any) {
    emailPresets = Array.isArray(raw)
      ? raw.map((x) => String(x ?? '').trim()).filter(Boolean)
      : [];
  }
  async function loadEmail() {
    if (!current) return;
    try {
      const r = await getEmail(current.path);
      boundEmail = r.email || '';
    } catch {
      boundEmail = '';
    }
    showEmailForm = !boundEmail;
  }
  function showEmailView() {
    setView('email');
    loadEmail();
  }
  async function doSendEmail() {
    const r = await sendEmailCode(emailInput);
    addLog(r.ok ? '验证码已发送' : `发送失败：${r.msg}`);
  }
  async function doVerifyEmail() {
    const r = await verifyEmailCode(codeInput, emailInput);
    if (r.ok) {
      addLog(`邮箱绑定成功：${emailInput}`);
      boundEmail = emailInput.trim();
      showEmailForm = false;
      codeInput = '';
    } else {
      addLog(`验证失败：${r.msg}`);
    }
  }
  async function doSet2FA() {
    const r = await set2FA(cur2fa, new2fa);
    addLog(r.ok ? '2FA 设置成功' : `设置失败：${r.msg}`);
  }

  // 资料编辑
  let editFirstName = $state('');
  let editLastName = $state('');
  let editUsername = $state('');
  let editAbout = $state('');
  let editDay = $state('');
  let editMonth = $state('');
  let editYear = $state('');

  async function loadProfile() {
    setView('profile');
    editFirstName = current?.display || '';
    editUsername = current?.username || '';
    const r = await getProfile();
    if (r.ok && r.profile) {
      // 名字/姓氏必须取真实字段(display 是姓+名拼接,不能当名字用)
      editFirstName = r.profile.first || '';
      editLastName = r.profile.last || '';
      editUsername = r.profile.username || current?.username || '';
      editAbout = r.profile.about || '';
      if (r.profile.birthday) {
        editDay = String(r.profile.birthday.day || '');
        editMonth = String(r.profile.birthday.month || '');
        editYear = String(r.profile.birthday.year || '');
      }
    }
  }
  async function doSaveProfile() {
    await updateUsername(editUsername);
    await updateProfile(editFirstName, editLastName, editAbout);
    if (editDay && editMonth) {
      await updateBirthday(Number(editDay), Number(editMonth), editYear ? Number(editYear) : null);
    }
    addLog('资料更新已提交');
  }
  async function doUploadAvatar(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const buf = await file.arrayBuffer();
    let bin = '';
    const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    await uploadAvatar(btoa(bin));
    addLog('头像已上传');
  }

  // 白名单管理
  let wlUsers = $state<number[]>([]);
  let wlGroups = $state<number[]>([]);
  let wlUserInput = $state('');
  let wlGroupInput = $state('');

  async function loadWhitelist() {
    const wl = await getWhitelist();
    wlUsers = wl.users;
    wlGroups = wl.groups;
  }
  async function doAddUser() {
    if (!wlUserInput) return;
    const r = await addWhitelistUser(Number(wlUserInput));
    wlUsers = r.users;
    wlUserInput = '';
  }
  async function doAddGroup() {
    if (!wlGroupInput) return;
    const r = await addWhitelistGroup(Number(wlGroupInput));
    wlGroups = r.groups;
    wlGroupInput = '';
  }
  async function doRemoveUser(id: number) {
    const r = await removeWhitelistUser(id);
    wlUsers = r.users;
  }
  async function doRemoveGroup(id: number) {
    const r = await removeWhitelistGroup(id);
    wlGroups = r.groups;
  }

  // 账号分组
  let groups = $state<Record<string, string[]>>({});
  let curGroup = $state('all');
  // 分组选择记忆: 启动时恢复 settings.cur_group,切换时静默持久化
  let restoreGroup = '';

  async function loadGroups() {
    groups = await getGroups();
    if (restoreGroup) {
      const want = restoreGroup;
      restoreGroup = '';
      if (want === 'all' || want === 'ungrouped' || want in groups) {
        curGroup = want;
        applyFilter();
      }
    }
  }
  function groupFiltered(): Account[] {
    const grouped = new Set<string>();
    for (const names of Object.values(groups)) for (const n of names) grouped.add(n);
    if (curGroup === 'ungrouped') return accounts.filter((a) => !grouped.has(a.name));
    if (curGroup !== 'all') return accounts.filter((a) => (groups[curGroup] || []).includes(a.name));
    return accounts;
  }
  function selectGroup(g: string) {
    curGroup = g;
    applyFilter();
    saveSettings({ cur_group: g }).catch(() => {});
  }
  // 新建分组弹窗(M3,替代原生 prompt)
  let groupModalOpen = $state(false);
  let groupInput = $state('');
  let groupCreating = $state(false);
  function doCreateGroup() {
    groupInput = '';
    groupModalOpen = true;
  }
  async function doCreateGroupConfirm() {
    const name = groupInput.trim();
    if (!name || groupCreating) return;
    groupCreating = true;
    try {
      const r = await createGroup(name);
      if (r.ok) {
        groups = r.groups;
        groupModalOpen = false;
      } else {
        addLog(`新建失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`新建异常：${e?.message ?? e}`);
    } finally {
      groupCreating = false;
    }
  }
  async function doMoveAccount(name: string, group: string) {
    const r = await moveAccount(name, group);
    if (r.ok) {
      groups = r.groups;
      applyFilter();
    }
  }

  // ---------- 分组标签: 指针拖动排序 + 右键重命名/删除 ----------
  // 不用 HTML5 DnD: button 上 dragstart 在 Chromium 里不稳定,且拖动中重渲染会中断。
  // 指针方案: mousedown 记录起点,移动超阈值进入拖动态,经过的标签高亮,松手落位。
  let dragGroup = $state('');
  let dragGroupOver = $state('');
  let pressGroup = '';      // mousedown 时的分组(还没确认是拖动)
  let pressX = 0;
  let pressY = 0;
  let suppressGroupClick = false;   // 拖动结束后短暂吞 click,防止误切分组

  function onGroupMouseDown(e: MouseEvent, g: string) {
    if (g === 'all' || g === 'ungrouped' || e.button !== 0) return;
    pressGroup = g;
    pressX = e.clientX;
    pressY = e.clientY;
    e.preventDefault();   // 阻止按钮原生按下行为(焦点框/文字选择),避免干扰拖动
  }
  function onGroupMouseMove(e: MouseEvent) {
    if (!pressGroup) return;
    if (!dragGroup) {
      // 超过 5px 判定为拖动(而不是点击)
      if (Math.abs(e.clientX - pressX) > 5 || Math.abs(e.clientY - pressY) > 5) {
        dragGroup = pressGroup;
      } else {
        return;
      }
    }
    // 命中检测: 鼠标下的分组标签
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const btn = el?.closest?.('button.grp');
    const g = btn?.getAttribute('data-group') || '';
    dragGroupOver = (g && g !== 'all' && g !== 'ungrouped' && g !== dragGroup) ? g : '';
  }
  function onGroupMouseUp() {
    if (dragGroup && dragGroupOver) {
      const from = dragGroup;
      const to = dragGroupOver;
      const wasDragging = true;
      dragGroup = '';
      dragGroupOver = '';
      pressGroup = '';
      // 拖动结束后短时间内吞掉 click(松手位置按钮会收到 click,误触切换分组)
      suppressGroupClick = true;
      setTimeout(() => (suppressGroupClick = false), 250);
      reorderGroupList(from, to);
      return;
    }
    dragGroup = '';
    dragGroupOver = '';
    pressGroup = '';
  }
  async function reorderGroupList(from: string, to: string) {
    const keys = Object.keys(groups);
    const fromIdx = keys.indexOf(from);
    const toIdx = keys.indexOf(to);
    if (fromIdx < 0 || toIdx < 0) return;
    keys.splice(toIdx, 0, keys.splice(fromIdx, 1)[0]);
    const ordered: Record<string, string[]> = {};
    for (const k of keys) ordered[k] = groups[k];
    groups = ordered;
    const r = await reorderGroups(keys);
    if (!r.ok) addLog(`分组排序保存失败：${r.msg}`);
  }
  // 分组右键菜单
  let groupMenu = $state<{ x: number; y: number; name: string } | null>(null);
  function onGroupContext(e: MouseEvent, g: string) {
    if (g === 'all' || g === 'ungrouped') return;
    e.preventDefault();
    e.stopPropagation();
    groupMenu = { x: e.clientX, y: e.clientY, name: g };
  }
  // 分组重命名弹窗
  let groupRenameOpen = $state(false);
  let groupRenameTarget = $state('');
  let groupRenameInput = $state('');
  function doOpenGroupRename() {
    if (!groupMenu) return;
    groupRenameTarget = groupMenu.name;
    groupRenameInput = groupMenu.name;
    groupMenu = null;
    groupRenameOpen = true;
  }
  async function doGroupRenameConfirm() {
    const newName = groupRenameInput.trim();
    if (!newName || newName === groupRenameTarget) {
      groupRenameOpen = false;
      return;
    }
    const r = await renameGroup(groupRenameTarget, newName);
    if (r.ok) {
      groups = r.groups;
      if (curGroup === groupRenameTarget) curGroup = newName;
      groupRenameOpen = false;
    } else {
      addLog(`重命名失败：${r.msg}`);
    }
  }
  // 分组删除确认弹窗(成员回到未分组)
  let groupDelOpen = $state(false);
  let groupDelTarget = $state('');
  let groupDeleting = $state(false);
  function doOpenGroupDelete() {
    if (!groupMenu) return;
    groupDelTarget = groupMenu.name;
    groupMenu = null;
    groupDelOpen = true;
  }
  async function doGroupDeleteConfirm() {
    if (groupDeleting) return;
    groupDeleting = true;
    try {
      const r = await deleteGroup(groupDelTarget);
      if (r.ok) {
        groups = r.groups;
        if (curGroup === groupDelTarget) curGroup = 'all';
        applyFilter();
        groupDelOpen = false;
      } else {
        addLog(`删除分组失败：${r.msg}`);
      }
    } catch (e: any) {
      addLog(`删除分组异常：${e?.message ?? e}`);
    } finally {
      groupDeleting = false;
    }
  }

  let ctxMenu = $state<{ x: number; y: number; name: string } | null>(null);
  function onAccountContext(e: MouseEvent, a: Account) {
    e.preventDefault();
    flushSync(() => {
      ctxMenu = { x: e.clientX, y: e.clientY, name: a.name };
    });
    // 渲染后测量菜单尺寸,靠视口边缘时向内翻转,避免被裁剪
    const el = document.querySelector('.ctx');
    if (!el || !ctxMenu) return;
    const r = el.getBoundingClientRect();
    let { x, y } = ctxMenu;
    if (y + r.height > window.innerHeight - 8) y = Math.max(8, window.innerHeight - r.height - 8);
    if (x + r.width > window.innerWidth - 8) x = Math.max(8, window.innerWidth - r.width - 8);
    if (x !== ctxMenu.x || y !== ctxMenu.y) {
      flushSync(() => {
        ctxMenu = { x, y, name: a.name };
      });
    }
  }
  function closeCtx() {
    ctxMenu = null;
    groupMenu = null;
  }

  // 三栏宽度拖动
  let leftW = $state(280);
  let midW = $state(340);
  let dragTarget = $state<'left' | 'mid' | null>(null);
  function startDrag(e: MouseEvent, t: 'left' | 'mid') {
    dragTarget = t;
    e.preventDefault();
  }
  function onWinMouseMove(e: MouseEvent) {
    onGroupMouseMove(e);   // 分组标签指针拖动排序
    if (!dragTarget) return;
    if (dragTarget === 'left') {
      leftW = Math.max(200, Math.min(500, e.clientX));
    } else {
      midW = Math.max(200, Math.min(700, e.clientX - leftW));
    }
  }
  function onWinMouseUp() {
    onGroupMouseUp();      // 分组拖动落位
    dragTarget = null;
  }

  // tdata 转换
  async function doConvertTdata(a: Account) {
    addLog(`正在转换 ${a.name} …`);
    const r = await convertTdata(a.path);
    addLog(r.ok ? `${a.name} 转换完成` : `${a.name} 转换失败：${r.msg}`);
    await loadAccounts();
  }

  // 拖放导入
  function onDragOver(e: DragEvent) {
    e.preventDefault();
  }
  async function onDrop(e: DragEvent) {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (!files?.length) return;
    for (const f of Array.from(files)) {
      if (!f.name.toLowerCase().endsWith('.zip')) continue;
      addLog(`正在导入 ${f.name} …`);
      const buf = await f.arrayBuffer();
      let bin = '';
      const bytes = new Uint8Array(buf);
      for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
      const r = await importArchive(btoa(bin), f.name.replace(/\.zip$/i, ''));
      addLog(r.ok ? `导入完成：${r.msg}` : `导入失败：${r.msg}`);
    }
    await loadAccounts();
  }

  connectWS((e: LogEvent) => {
    if (e.type === 'log') {
      const msg = (e as any).msg || e.line || '';
      if (msg) addLog(msg, ((e as any).level as LogLevel) || 'info', (e as any).ts);
    }
    if (e.type === 'progress') {
      progress = { done: e.done ?? 0, total: e.total ?? 0, label: e.label ?? '' };
    }
    if (e.type === 'state') {
      if (e.status === 'connected') {
        connected = true;
        if (rightView === 'chat' && !curDialog) loadDialogs();
      }
      if (e.status === 'switched') {
        connected = true;
        if (rightView === 'chat' && !curDialog) loadDialogs();
        // 引擎自动切到池中其他在线账号时,同步 current 指向
        const nm = (e.data as any)?.name;
        if (nm) {
          const acc = accounts.find((x) => x.name === nm);
          if (acc) {
            flushSync(() => {
              current = acc;
              onlineNames = new Set([...onlineNames, nm]);
            });
          }
        }
      }
      if (e.status === 'connect_fail') connected = false;
      if (e.status === 'rename_applied') {
        // 后台把「待执行改名」落地了: 刷新待执行徽标与账号列表
        const d = e.data as any;
        if (d?.old) markOnline(String(d.old), false);
        if (current?.name === d?.old) current = accounts.find((x) => x.name === d?.new) ?? null;
        loadRenamePending();
        loadAccounts();
      }
      if (e.status === 'disconnected') {
        // data 为账号名: 只断该账号;为 null: 当前账号断开
        const nm = typeof e.data === 'string' ? e.data : current?.name;
        if (nm) {
          flushSync(() => {
            onlineNames = new Set([...onlineNames].filter((x) => x !== nm));
          });
          if (current?.name === nm) connected = false;
        } else {
          connected = false;
        }
      }
      if (e.status === 'done') {
        if (e.data === 'poll_done') {
          // 结构化标记事件: 只触发刷新,不进日志(真正的完成文案在下一个事件)
          loadAccounts();
        } else {
          addLog('[完成]');
        }
      }
      if (e.status === 'error') addLog(`[错误] ${String(e.data ?? '')}`);
      if (e.status === 'passkey_done') {
        const d = e.data as any;
        addLog(d?.ok ? '[通行密钥注册成功]' : `[注册失败] ${d?.msg ?? ''}`);
        pkQrImg = '';
        loadPasskeys();
      }
      if (e.status === 'passkey_error') {
        addLog(`[通行密钥异常] ${String(e.data ?? '')}`);
        pkQrImg = '';
      }
      if (e.status === 'passkey_scanning') addLog('[通行密钥] 等待手机扫码（需开启电脑蓝牙）');
      if (e.status && e.status.startsWith('passkey_adv:')) {
        addLog(`[蓝牙] 广播 ${e.status.slice(11)}`);
      }
      if (e.status && e.status.startsWith('passkey_mfg:')) {
        addLog(`[蓝牙] 厂商数据 ${e.status.slice(11)}`);
      }
      if (e.status && e.status.startsWith('passkey_hit:')) {
        addLog(`[命中] ${e.status.slice(12)}`);
      }
      if (e.status && e.status.startsWith('passkey_decrypt_fail:')) {
        addLog(`[蓝牙] EID解密失败 数据长度${e.status.slice(20)}`);
      }
      if (e.status && e.status.startsWith('passkey_diag:')) {
        addLog(`[诊断] ${e.status.slice(12)}`);
      }
      if (e.status && e.status.startsWith('passkey_hint_')) {
        addLog(`[引导] ${e.status.slice(13)}`);
      }
      if (e.status === 'passkey_connecting') addLog('[通行密钥] 蓝牙连接中…');
      if (e.status === 'passkey_handshake') addLog('[通行密钥] 安全握手…');
      if (e.status === 'passkey_awaiting') addLog('[通行密钥] 等待手机确认注册…');
      if (e.status === 'recv_message') {
        const m = e.data as any;
        if (m) {
          // 会话列表页: 对应会话未读+1 并置顶;新会话直接刷新
          if (rightView === 'chat' && !curDialog) {
            const idx = dialogs.findIndex((x) => x.id === m.chat_id);
            if (idx >= 0) {
              const dlg = { ...dialogs[idx], last_text: m.text || '(媒体消息)', last_date: m.date, unread: (dialogs[idx].unread || 0) + 1 };
              dialogs = [dlg, ...dialogs.filter((x) => x.id !== m.chat_id)];
            } else {
              loadDialogs();
            }
          }
          // 聊天记录页: 当前会话实时追加(推送的都是收到的消息)
          if (rightView === 'chat' && curDialog && m.chat_id === curDialog.id) {
            historyMsgs.push({ id: Date.now(), out: false, sender: m.sender || '', sender_id: m.sender_id ?? null, sender_username: m.sender_username ?? null, text: m.text || '(媒体消息)', date: m.date });
            scrollHistoryBottom();
          }
          if (rightView !== 'chat') chatUnread += 1;
        }
      }
    }
    if (e.type === 'avatars_done') {
      addLog('[头像] 获取完成');
      avatarFailed = new Set();
      loadAccounts();
    }
  });

  onMount(async () => {
    // 先取上次所在分组,再加载分组列表(加载完自动恢复)
    try {
      const s = await getSettings();
      if (s?.cur_group) restoreGroup = String(s.cur_group);
    } catch {
      // 忽略: 恢复失败留在「全部」
    }
    loadGroups();
    loadAccounts();
    loadRenamePending();
    loadRecv();
    loadLogHistory();
    try {
      const p = await getPing();
      if (p?.version) {
        appVersion = String(p.version);
        addLog(`程序版本： v${appVersion}（报问题时请带上此版本号和 logs 目录日志）`);
      }
    } catch {
      // 版本号显示失败不影响使用
    }
    // 页面刷新后恢复在线徽标(连接池仍在)
    try {
      const on = await getOnline();
      if (on.ok && Array.isArray(on.online) && on.online.length) {
        flushSync(() => {
          onlineNames = new Set(on.online.map((x) => x.name));
        });
        connected = true;
      }
    } catch (e) {
      // 忽略
    }
    try {
      settings = await getSettings();
      applyTheme();
      cardOrder = parseCardOrder((settings as any).card_order);
      const co = (settings as any).card_open;
      if (co && typeof co === 'object') {
        flushSync(() => {
          cardOpen = co as Record<string, boolean>;
        });
        // 恢复后把 details 元素的 open 同步到保存值(flushSync 不一定触发 open 属性更新)
        for (const el of document.querySelectorAll('details.card')) {
          const name = el.getAttribute('data-card');
          if (name && name in cardOpen) (el as HTMLDetailsElement).open = !!cardOpen[name];
        }
      }
      cardOpenRestored = true;
    } catch (e) {
      // 保持默认主题
    }
  });
</script>

<TopBar
  {connected}
  {connectingLabel}
  {themeMode}
  onAddAccount={doOpenAddAccount}
  onReconnect={doReconnect}
  onLaunchClient={doLaunchClient}
  onOpenFolder={doOpenAccountFolder}
  onDisconnect={doDisconnect}
  onPack={doPack}
  onToggleTheme={toggleTheme}
  onSettings={loadSettings}
/>

<MobileApp
  bind:mobilePanelOpen
  bind:mobileTab
  {rightView}
  {current}
  {accounts}
  {onlineNames}
  {connected}
  {connectingLabel}
  bind:search
  {filtered}
  {groups}
  {curGroup}
  {avatarFailed}
  {appVersion}
  {progress}
  {logs}
  {themeMode}
  onSearch={onSearch}
  onSelectGroup={selectGroup}
  onCreateGroup={doCreateGroup}
  onOpenAddAccount={doOpenAddAccount}
  onSelectAccount={(a) => { current = a; mobileTab = 'current'; }}
  {avatarUrl}
  {avatarColor}
  {onAvatarError}
  onSwitch={onSwitch}
  onConnect={onConnect}
  onLaunchClient={doLaunchClient}
  onOpenAccountFolder={doOpenAccountFolder}
  onDisconnect={doDisconnect}
  onReconnect={doReconnect}
  onLoadProfile={loadProfile}
  onOpenPanel={openMobilePanel}
  onDeleteContacts={() => postTask('/api/tasks/delete-contacts')}
  onDeleteDialogs={(choice) => postTask('/api/tasks/delete-dialogs', { choice })}
  onPack={doPack}
  onRefreshInfo={doRefreshAccountInfo}
  onReloadLogs={loadLogHistory}
  onLoadSettings={loadSettings}
  onToggleTheme={toggleTheme}
/>

<svelte:window onmousemove={onWinMouseMove} onmouseup={onWinMouseUp} /><div class="layout" class:mobile-panel-open={mobilePanelOpen}>
  <aside class="left" style="width:{leftW}px" ondragover={onDragOver} ondrop={onDrop} onclick={closeCtx}>
    <div class="groups">
      {#each ['all', 'ungrouped', ...Object.keys(groups)] as g}
        <button
          class="grp"
          class:on={curGroup === g}
          class:drag-over={dragGroupOver === g}
          class:dragging={dragGroup === g}
          data-group={g}
          draggable={false}
          onclick={() => { if (!suppressGroupClick) selectGroup(g); }}
          oncontextmenu={(e) => onGroupContext(e, g)}
          onmousedown={(e) => onGroupMouseDown(e, g)}
        >
          {g === 'all' ? t('common.all') : g === 'ungrouped' ? t('common.ungrouped') : g}
        </button>
      {/each}
      <button class="grp add" onclick={doCreateGroup}>＋</button>
    </div>
    <input class="search" placeholder={t('app.searchPlaceholder')} bind:value={search} oninput={onSearch} />
    <ul class="list">
      {#key filterVersion}
      {#each filtered as a}
        <AccountCard
          account={a}
          isCurrent={current?.name === a.name}
          isOnline={onlineNames.has(a.name)}
          hasAvatar={!!a.avatar && !avatarFailed.has(a.name)}
          avatarSrc={avatarUrl(a)}
          avatarBg={avatarColor(a.name)}
          renameTarget={renamePending[a.name] || ''}
          onSelect={() => (current = a)}
          onConnect={() => onConnect(a)}
          onContext={(e) => onAccountContext(e, a)}
          onAvatarError={() => onAvatarError(a.name)}
          onConvert={() => doConvertTdata(a)}
        />
      {/each}
      {/key}
    </ul>
  </aside>

  {#if ctxMenu}
    <ContextMenu
      {ctxMenu}
      {groups}
      {onlineNames}
      {renamePending}
      onMove={(name, g) => doMoveAccount(name, g)}
      onClose={closeCtx}
      onDisconnect={disconnectOne}
      onRename={(name) => { const a = accounts.find((x) => x.name === name); if (a) openRename(a); }}
      onRunPending={doRunRenamePending}
      onCancelPending={doCancelRenamePending}
    />
  {/if}

  <div class="splitter" onmousedown={(e) => startDrag(e, 'left')}></div>

  <section class="mid" class:narrow={midW < 340} style="width:{midW}px">
    <FunctionCards
      {cardOrder}
      isOpen={isCardOpen}
      onToggle={onCardToggle}
      {current}
      {avatarFailed}
      {avatarUrl}
      {avatarColor}
      onAvatarError={onAvatarError}
      onEditProfile={loadProfile}
      {recvOn}
      canRecv={!!current && onlineNames.has(current.name)}
      {chatUnread}
      onToggleRecv={() => applyRecv(!recvOn)}
      onOpenChatList={() => { curDialog = null; setView('chat'); }}
      on2FA={load2FA}
      onPasskeys={loadPasskeys}
      onEmail={showEmail}
      onDevices={loadDevices}
      onDeleteContacts={() => postTask('/api/tasks/delete-contacts')}
      onDeleteDialogs={(choice) => postTask('/api/tasks/delete-dialogs', { choice })}
      {speedVal}
      speedSeg={SPEED_SEG}
      onSpeed={onSpeed}
      {converting}
      onOpenTdataToSs={doOpenTdataToSs}
      onOpenConvertTdata={doOpenConvertTdata}
      onRefreshSs={doRefreshSsBatch}
      onUpdateTelegram={() => updateTelegram()}
      onRefreshInfo={doRefreshAccountInfo}
      onPollAccounts={doPollAccounts}
      onJoinChannels={openJoinView}
      {exporting}
      onExport={doExportAccounts}
      onDeleteAccount={doOpenDeleteAccount}
    />
  </section>

  <div class="splitter" onmousedown={(e) => startDrag(e, 'mid')}></div>

  <section class="right">
    {#if mobilePanelOpen}
      <div class="mobile-panel-bar">
        <button class="mobile-panel-back" aria-label={t('common.back')} onclick={closeMobilePanel}>‹ {t('common.back')}</button>
      </div>
    {/if}
    {#if rightView === 'log'}
      <LogView {logs} {progress} showBack={lastView !== 'log'} onBack={() => setView(lastView)} />
    {:else if rightView === 'chat'}
      <ChatView
        {current}
        isOnline={!!current && onlineNames.has(current.name)}
        {chatUnread}
        {dialogs}
        {dialogsLoading}
        onRefreshDialogs={loadDialogs}
        onBack={() => setView('log')}
        {recvOn}
        {recvRules}
        onToggleRecv={() => applyRecv(!recvOn)}
        {onRecvRuleChange}
        bind:startChatName
        {startChatTarget}
        {startingChat}
        onStartChat={doStartChat}
        {avatarColor}
        onOpenDialog={openDialog}
        bind:curDialog
        {historyHasMore}
        {historyLoading}
        {historyError}
        {historyMsgs}
        onLoadHistory={(initial) => loadHistory(initial)}
        bind:chatDraft
        {sending}
        onSendMsg={doSendMsg}
      />

    {:else if rightView === 'passkey' || rightView === '2fa' || rightView === 'email' || rightView === 'devices'}
      <SecurityViews
        view={rightView}
        onBack={() => setView('log')}
        {passkeys}
        pkQrImg={pkQrImg}
        onInitPasskey={doInitPasskey}
        onDeletePasskey={doDeletePasskey}
        {has2fa}
        bind:cur2fa
        bind:new2fa
        onSet2FA={doSet2FA}
        {boundEmail}
        bind:showEmailForm
        {emailPresets}
        bind:emailInput
        bind:codeInput
        onSendEmail={doSendEmail}
        onVerifyEmail={doVerifyEmail}
        {devices}
        onDeleteDevice={doDeleteDevice}
      />
    {:else if rightView === 'profile'}
      <ProfileView
        {current}
        {avatarFailed}
        {avatarUrl}
        {avatarColor}
        onAvatarError={onAvatarError}
        bind:firstName={editFirstName}
        bind:lastName={editLastName}
        bind:username={editUsername}
        bind:about={editAbout}
        bind:month={editMonth}
        bind:day={editDay}
        bind:year={editYear}
        onUploadAvatar={doUploadAvatar}
        onSaveProfile={doSaveProfile}
        onBack={() => setView('log')}
      />
    {:else if rightView === 'join'}
      <JoinView
        entries={joinEntries}
        bind:editIdx={joinEditIdx}
        onAdd={doJoinAddEntry}
        onCancelEdit={doJoinCancelEdit}
        onSaveEdit={doJoinSaveEdit}
        onJoin={doJoinOne}
        onDelete={doJoinDelete}
        onJoinAll={doJoinChats}
        onBack={() => setView('log')}
      />
    {/if}
  </section>
</div>

  {#if groupMenu}
    <div class="ctx" style="left:{groupMenu.x}px;top:{groupMenu.y}px" onclick={(e) => e.stopPropagation()}>
      <div class="ctx-title">{t('group.menuTitle', { name: groupMenu.name })}</div>
      <button onclick={doOpenGroupRename}>{t('common.rename')}</button>
      <button class="ctx-disconnect" onclick={doOpenGroupDelete}>{t('group.deleteMenu')}</button>
    </div>
  {/if}

  {#if groupRenameOpen}
    <GroupRenameDialog
      bind:value={groupRenameInput}
      onClose={() => (groupRenameOpen = false)}
      onConfirm={doGroupRenameConfirm}
    />
  {/if}

{#if addAccOpen}
  <AddAccountDialog
    bind:tab={addAccTab}
    bind:dragging={addAccDragging}
    files={addAccFiles}
    busy={addAccBusy}
    qrImg={qrImg}
    qrStatus={qrStatus}
    qrRemain={qrRemain}
    qrErr={qrErr}
    phoneStage={phoneStage}
    bind:phoneInput
    bind:phoneCode
    bind:phonePwd
    phoneErr={phoneErr}
    phoneBusy={phoneBusy}
    onClose={closeAddAcc}
    onStartQr={doStartQrLogin}
    onRemoveFile={addAccRemove}
    onConfirm={doAddAccountConfirm}
    onDragOver={onAddAccDragOver}
    onDragLeave={() => (addAccDragging = false)}
    onDrop={onAddAccDrop}
    onPhoneStart={doPhoneLoginStart}
    onPhoneSubmit={doPhoneLoginSubmit}
    onPhoneReset={phoneReset}
  />
{/if}

{#if groupDelOpen}
  <GroupDeleteDialog
    target={groupDelTarget}
    deleting={groupDeleting}
    onClose={() => (groupDelOpen = false)}
    onConfirm={doGroupDeleteConfirm}
  />
{/if}

{#if t2sOpen && current}
  <div class="modal-mask" onclick={() => (t2sOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>tdata 转 session+json（覆盖刷新会话）</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (t2sOpen = false)}>✕</button>
      </div>
      <p class="set-hint">
        使用账号 <b>{current.display || current.name}</b> 的 <b>tdata</b> 重新生成 session+json，覆盖现有会话数据。适用于 session 过期、登录态失效的账号。
      </p>
      <p class="set-hint" style="color: var(--md-sys-color-error)">
        在线账号仅刷新 json 元数据；离线账号将删除旧 session 并从 tdata 重建，tdata 已失效则刷新失败。
      </p>
      <div class="rename-btns">
        <md-outlined-button onclick={() => (t2sOpen = false)}>取消</md-outlined-button>
        <md-filled-button disabled={t2sConverting} onclick={doTdataToSsConfirm}>
          {t2sConverting ? '刷新中…' : '开始刷新'}
        </md-filled-button>
      </div>
    </div>
  </div>
{/if}

{#if convOpen && current}
  <div class="modal-mask" onclick={() => (convOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>session+json 转 tdata</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (convOpen = false)}>✕</button>
      </div>
      <p class="set-hint">
        将账号 <b>{current.display || current.name}</b> 的 session 登录态转换为 Telegram Desktop 的 <b>tdata</b>，写入账号文件夹下的 tdata\ 子目录。
      </p>
      <p class="set-hint" style="color: var(--md-sys-color-error)">
        原 session 保留不变，转换后两种登录态并存；tdata 需配合 Telegram.exe 使用。
      </p>
      <label class="del-check">
        <input type="checkbox" bind:checked={convOverwrite} />
        <span>覆盖已有 tdata（默认关闭；开启后目标 tdata\ 非空也会执行）</span>
      </label>
      <div class="set-row" style="margin-top:8px">
        <span class="set-label">2FA 密码</span>
        <input class="set-input" type="password" autocomplete="new-password"
          bind:value={convTwofa} placeholder="开启两步验证的账号必填；留空则使用 json 中保存的密码" />
      </div>
      <div class="rename-btns">
        <md-outlined-button onclick={() => (convOpen = false)}>取消</md-outlined-button>
        <md-filled-button disabled={converting} onclick={doConvertTdataConfirm}>
          {converting ? '转换中…' : '开始转换'}
        </md-filled-button>
      </div>
    </div>
  </div>
{/if}

{#if delOpen && delTarget}
  <DeleteAccountDialog
    target={delTarget}
    bind:confirm={delConfirm}
    {deleting}
    onClose={() => (delOpen = false)}
    onConfirm={doDeleteAccount}
  />
{/if}

{#if groupModalOpen}
  <GroupCreateDialog
    bind:value={groupInput}
    creating={groupCreating}
    onClose={() => (groupModalOpen = false)}
    onConfirm={doCreateGroupConfirm}
  />
{/if}

{#if renameOpen}
  <div class="modal-mask" onclick={() => (renameOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>文件夹重命名</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (renameOpen = false)}>✕</button>
      </div>
      <input
        class="rename-input"
        bind:value={renameInput}
        onkeydown={(e) => { if (e.key === 'Enter') doRename(); }}
        placeholder="输入新的文件夹名称"
        maxlength="60"
      />
      {#if renameQuickOpts.length}
        <div class="rename-quick">
          <span class="rename-quick-label">快捷填充：</span>
          {#each renameQuickOpts as [k, label]}
            {#if renameQuickVal(k)}
              <button class="rule-chip" title={renameQuickVal(k)} onclick={() => applyRenameQuick(k, label)}>{label}</button>
            {/if}
          {/each}
        </div>
      {/if}
      <div class="rename-btns">
        <md-outlined-button onclick={() => (renameOpen = false)}>取消</md-outlined-button>
        <md-filled-button disabled={renaming || !renameInput.trim()} onclick={doRename}>
          {renaming ? '处理中…' : '确定'}
        </md-filled-button>
      </div>
    </div>
  </div>
{/if}

{#if settingsOpen}
  <SettingsDialog
    bind:section={settingsSection}
    bind:mobileSection={mobileSettingsSection}
    {themeMode}
    {appVersion}
    {settings}
    {joinEntries}
    bind:emailPresets
    {wlUsers}
    {wlGroups}
    bind:wlUserInput
    bind:wlGroupInput
    {cardOrder}
    {moveCard}
    renameQuickDefs={RENAME_QUICK_DEFS}
    {toggleRenameQuick}
    presetColors={PRESET_COLORS}
    {applyPreset}
    {isPreset}
    {applyTheme}
    {setThemeMode}
    {settingsInfo}
    {openSettingsSection}
    {doAddUser}
    {doRemoveUser}
    {doAddGroup}
    {doRemoveGroup}
    onLoadWhitelist={loadWhitelist}
    onOpenJoinManager={() => { settingsOpen = false; openJoinView(); }}
    onSave={doSaveSettings}
    onClose={() => (settingsOpen = false)}
  />
{/if}


