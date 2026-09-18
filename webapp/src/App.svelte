<script lang="ts">
  import { onMount, flushSync } from 'svelte';
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
    pollAccounts,
    convertToTdata,
    refreshSession,
    refreshSsBatch,
    startChat,
    getBotStatus,
    startBot,
    stopBot,
    deleteAccount,
    addAccount,
    qrLoginStart,
    qrLoginPoll,
    qrLoginCancel,
    phoneLoginStart,
    phoneLoginSubmit,
    getPing,
    TOKEN,
    type Account,
    type LogEvent,
  } from './api';

  const AVATAR_COLORS = ['#E17076', '#7BC862', '#65AADD', '#A695E7', '#EE7AAE', '#6EC9CB', '#FAA774', '#FFA6C9'];

  let accounts = $state<Account[]>([]);
  let filtered = $state<Account[]>([]);
  let filterVersion = $state(0);
  let search = $state('');
  let current = $state<Account | null>(null);
  let connected = $state(false);
  // 连接/重连进行中的提示文案(顶栏状态),空=不在连接中
  let connectingLabel = $state('');
  let logs = $state<string[]>([]);
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
  const PRESET_COLORS = ['#009688', '#229ED9', '#2A6D7D', '#3F51B5', '#9C27B0', '#EC407A', '#E53935', '#F2994A', '#66BB6A', '#00BCD4', '#795548', '#607D8B'];
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

  function addLog(line: string) {
    // $state 深代理可直接 push,避免每条日志整组拷贝(O(n))
    logs.push(line);
    if (logs.length > 2000) logs.splice(0, logs.length - 2000);
    // 日志视图自动滚到最底,免手动滑动
    if (rightView === 'log') {
      setTimeout(() => {
        const el = document.querySelector('.log');
        if (el) el.scrollTop = el.scrollHeight;
      }, 0);
    }
  }

  async function loadAccounts() {
    const acc = await getAccounts();
    flushSync(() => {
      accounts = acc;
      applyFilter();
    });
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
      addLog(`连接失败: ${r.msg || '未知错误'}`);
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
      addLog(`已切换到 ${a.name}(保持在线)`);
      // 右栏自动回到日志页,避免停留在上一个账号的视图
      if (rightView !== 'log') setView('log');
    } else {
      addLog(`切换失败: ${r.msg || '未知错误'}`);
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
    addLog(`已断开连接: ${name}`);
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
    addLog(r.ok ? `已启动客户端: ${current.name}(${r.msg})` : `启动客户端失败: ${r.msg}`);
  }

  // 右键「启动客户端」: 在资源管理器中打开账号文件夹
  async function doOpenAccountFolder() {
    if (!current) {
      addLog('请先选择账号');
      return;
    }
    const r = await openFolder(current.path);
    if (!r.ok) addLog(`打开文件夹失败: ${r.msg}`);
  }

  // 账号轮询: 逐号登录保活+测活(后台任务,进度/结果走日志页)
  async function doPollAccounts() {
    setView('log');
    const scope = curGroup === 'all' ? '全部账号' : curGroup === 'ungrouped' ? '未分组' : `分组「${curGroup}」`;
    addLog(`开始账号轮询(范围: ${scope},逐号登录保活+测活,每号间隔1s)…`);
    const r = await pollAccounts(curGroup);
    if (!r.ok) addLog(`轮询启动失败: ${r.msg}`);
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
        addLog(`转换失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`转换异常: ${e?.message ?? e}`);
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
        addLog(`刷新失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`刷新异常: ${e?.message ?? e}`);
    } finally {
      t2sConverting = false;
    }
  }

  // 批量刷新 s+s 数据: 所有有 tdata 且测活失败的离线账号(后台任务)
  async function doRefreshSsBatch() {
    setView('log');
    addLog('开始批量刷新 session（仅处理有 tdata 且测活失败的账号，每号间隔 1s）');
    const r = await refreshSsBatch();
    if (!r.ok) addLog(`批量刷新启动失败: ${r.msg}`);
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
        addLog(`已删除账号: ${target.name}(${r.deleted_path})`);
        delOpen = false;
        if (current?.name === target.name) current = null;
        markOnline(target.name, false);
        await loadAccounts();
      } else {
        addLog(`删除失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`删除异常: ${e?.message ?? e}`);
    } finally {
      deleting = false;
    }
  }

  // 新建账号(顶栏): 拖入 session/json/tdata/zip 建号;扫码登录标签页
  let addAccOpen = $state(false);
  let addAccTab = $state<'files' | 'qr'>('files');
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
        addLog(`[扫码] 登录成功: ${r.user.display}(+${r.user.phone}),已创建账号 ${r.user.name}`);
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
        addLog(`[手机登录] 登录成功: ${r.user.display}(+${r.user.phone}),已创建账号 ${r.user.name}`);
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
      addLog(`[新建] 读取文件失败: ${err?.message ?? err}`);
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
        addLog(`[新建] 失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`[新建] 异常: ${e?.message ?? e}`);
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
      addLog(`该账号没有${label},无法填充`);
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
      if (r.ok) {
        addLog(`已重命名: ${renameTarget.name} → ${newName}`);
        renameOpen = false;
        if (current?.name === renameTarget.name) current = null;
        markOnline(renameTarget.name, false);
        await loadAccounts();
      } else {
        addLog(`重命名失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`重命名异常: ${e?.message ?? e}`);
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
    addLog(r.ok ? `打包完成: ${r.msg}` : `打包失败: ${r.msg}`);
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
    addLog(`正在刷新账号信息: ${current.name} …`);
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
        addLog(`已刷新账号信息: ${current.name}`);
      } else {
        addLog(`刷新失败: ${r.msg || (r.info ? '未知错误' : '该账号无 session 或登录态失效')}`);
      }
    } catch (e: any) {
      addLog(`刷新异常: ${e?.message ?? e}`);
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
  let settingsSection = $state<'general' | 'appearance' | 'proxy' | 'join' | 'whitelist' | 'about' | 'bot'>('general');
  // Bot 收件箱
  let botStatus = $state({ running: false, username: '', id: 0, error: '', allowed_ids: [] as number[], bot_on: false, has_token: false });
  let botAllowedInput = $state('');
  let botBusy = $state(false);
  let themeMode = $derived((settings.theme_mode as string) || 'light');
  async function loadSettings() {
    settings = {
      pack_naming: '{name}_账号包', pack_password: '',
      theme_seed: '#009688', theme_bg: '#F7FAF9', theme_dark: '#FFFFFF', theme_topbar: '#00796B', theme_mode: 'light', card_order: '基本信息,聊天,安全,删除,其他设置',
      proxy_mode: 'none', proxy_scheme: 'socks5', proxy_host: '', proxy_port: '',
      join_links: [],
      log_level: 'info',
      rename_quick: ['display', 'username', 'phone', 'uid'],
      rename_prefix: '',
      email_presets: [],
      bot_token: '', bot_allowed_ids: [], bot_on: false,
    };
    settingsOpen = true;
    try {
      settings = await getSettings();
      applyJoinEntries(settings.join_links);
      applyEmailPresets(settings.email_presets);
      botAllowedInput = ((settings.bot_allowed_ids as number[]) || []).join(', ');
      refreshBotStatus();
      applyTheme();
    } catch (e) {
      // 保持默认值
    }
  }
  function openSettings(section: typeof settingsSection) {
    settingsSection = section;
    loadSettings();
  }
  function parseBotIds(s: string): number[] {
    return (s.match(/\d+/g) || []).map((x) => Number(x));
  }
  async function refreshBotStatus() {
    try {
      botStatus = await getBotStatus();
    } catch {
      // 忽略: 状态拉取失败保持旧值
    }
  }
  async function doSaveSettings() {
    settings = { ...settings, join_links: joinEntries, email_presets: emailPresets, bot_allowed_ids: parseBotIds(botAllowedInput) };
    await saveSettings(settings);
    settingsOpen = false;
    addLog('设置已保存');
    applyTheme();
  }
  // Bot 收件箱: 启动前先把当前表单落盘(token/允许列表),再拉起 bot
  async function doStartBot() {
    if (botBusy) return;
    botBusy = true;
    try {
      settings = { ...settings, join_links: joinEntries, email_presets: emailPresets, bot_allowed_ids: parseBotIds(botAllowedInput) };
      await saveSettings(settings);
      const r = await startBot();
      addLog(r.ok ? `[Bot] ${r.msg}` : `[Bot] 启动失败: ${r.msg || '未知错误'}`);
      if (r.status) botStatus = r.status;
      else await refreshBotStatus();
    } catch (e: any) {
      addLog(`[Bot] 启动失败: ${e?.msg ?? e}`);
      await refreshBotStatus();
    } finally {
      botBusy = false;
    }
  }
  async function doStopBot() {
    if (botBusy) return;
    botBusy = true;
    try {
      const r = await stopBot();
      addLog(`[Bot] ${r.msg || '已停止'}`);
      if (r.status) botStatus = r.status;
      else await refreshBotStatus();
    } catch (e: any) {
      addLog(`[Bot] 停止失败: ${e?.msg ?? e}`);
      await refreshBotStatus();
    } finally {
      botBusy = false;
    }
  }
  let exporting = $state(false);
  async function doExportAccounts() {
    if (exporting) return;
    exporting = true;
    try {
      const r = await exportAccounts();
      if (r.ok) {
        addLog(`表格已更新并打开(${r.count ?? '?'} 个账号): ${r.path || '账号总表.xlsx'}`);
      } else {
        addLog(`导出失败: ${r.msg || '未知错误'}`);
      }
    } catch (e: any) {
      addLog(`导出失败: ${e?.message ?? e}`);
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
    const seed = (settings.theme_seed as string) || '#009688';
    const bg = (settings.theme_bg as string) || '#F7FAF9';
    const dark = (settings.theme_dark as string) || '#FFFFFF';
    const topbar = (settings.theme_topbar as string) || '#00796B';
    const root = document.documentElement.style;
    root.setProperty('--md-sys-color-primary', seed);
    root.setProperty('--md-sys-color-surface', bg);
    root.setProperty('--md-sys-color-surface-container', dark);
    root.setProperty('--topbar-color', topbar);
  }

  async function showWhitelist() {
    const wl = await getWhitelist();
    addLog(`白名单用户: ${wl.users.join(', ') || '无'}`);
    addLog(`白名单群/频道: ${wl.groups.join(', ') || '无'}`);
  }

  // 右栏视图
  let rightView = $state<'log' | 'passkey' | '2fa' | 'email' | 'devices' | 'profile' | 'settings' | 'chat' | 'join'>('log');
  // 日志页的「返回」目标: 从哪个界面点进日志,就回哪个界面
  let lastView = $state<typeof rightView>('log');
  function setView(v: typeof rightView) {
    flushSync(() => {
      if (v === 'log' && rightView !== 'log') lastView = rightView;
      rightView = v;
      if (v === 'chat') chatUnread = 0;
    });
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
      addLog('[加群] 链接保存失败(本次改动未持久化)');
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
        addLog(`会话获取失败: ${r.msg || '未知错误'}`);
      }
    } catch (e: any) {
      addLog(`会话获取异常: ${e?.message ?? e}`);
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
        addLog(`记录获取失败: ${r.msg || '未知错误'}`);
      }
    } catch (e: any) {
      historyError = String(e?.message ?? e);
      addLog(`记录获取异常: ${historyError}`);
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
  // 按用户名直接发起聊天(解析实体后打开会话)
  let startChatName = $state('');
  let startingChat = $state(false);
  async function doStartChat() {
    const u = startChatName.trim();
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
        addLog(`发起聊天失败: ${r.msg || '未找到该用户'}`);
      }
    } catch (e: any) {
      addLog(`发起聊天异常: ${e?.message ?? e}`);
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
    recvOn = on;
    if (rules) recvRules = { ...recvRules, ...rules };
    try {
      const r = await setRecv(recvOn, recvRules);
      recvOn = r.on;
      recvRules = { ...recvRules, ...r.rules };
    } catch (e: any) {
      addLog(`[消息接收] 设置失败: ${e?.message ?? e}`);
    }
    addLog(recvOn ? '[消息接收] 已开启' : '[消息接收] 已关闭');
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
        addLog(`[加群] 失败: ${r.msg}`);
      }
    } catch (err: any) {
      addLog(`[加群] 失败: ${err?.message ?? err}`);
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
        addLog(`[加群] 完成: 成功 ${okN}/${(r.results ?? []).length}`);
      } else {
        addLog(`[加群] 失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`[加群] 失败: ${e?.message ?? e}`);
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
        addLog(`生成失败: ${r.msg || JSON.stringify(r)}`);
        return;
      }
      pkQrImg = `data:image/png;base64,${r.img}`;
      addLog('[通行密钥] 请用手机扫描二维码，经蓝牙连接完成注册');
    } catch (e) {
      addLog(`生成异常: ${String(e)}`);
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
    addLog(r.ok ? '验证码已发送' : `发送失败: ${r.msg}`);
  }
  async function doVerifyEmail() {
    const r = await verifyEmailCode(codeInput, emailInput);
    if (r.ok) {
      addLog(`邮箱绑定成功: ${emailInput}`);
      boundEmail = emailInput.trim();
      showEmailForm = false;
      codeInput = '';
    } else {
      addLog(`验证失败: ${r.msg}`);
    }
  }
  async function doSet2FA() {
    const r = await set2FA(cur2fa, new2fa);
    addLog(r.ok ? '2FA 设置成功' : `设置失败: ${r.msg}`);
  }

  // 资料编辑
  let editFirstName = $state('');
  let editLastName = $state('');
  let editUsername = $state('');
  let editAbout = $state('');
  let aboutEl = $state<HTMLTextAreaElement>();
  // 简介自动增高: 打开资料/内容变化时都调整(替代只在 oninput 时触发)
  $effect(() => {
    const el = aboutEl;
    const _content = editAbout;   // 建立依赖: 内容变化时重新调高
    if (el && rightView === 'profile') {
      el.style.height = 'auto';
      el.style.height = el.scrollHeight + 'px';
    }
  });
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
        addLog(`新建失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`新建异常: ${e?.message ?? e}`);
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
    if (!r.ok) addLog(`分组排序保存失败: ${r.msg}`);
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
      addLog(`重命名失败: ${r.msg}`);
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
        addLog(`删除分组失败: ${r.msg}`);
      }
    } catch (e: any) {
      addLog(`删除分组异常: ${e?.message ?? e}`);
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
    addLog(r.ok ? `${a.name} 转换完成` : `${a.name} 转换失败: ${r.msg}`);
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
      addLog(r.ok ? `导入完成: ${r.msg}` : `导入失败: ${r.msg}`);
    }
    await loadAccounts();
  }

  connectWS((e: LogEvent) => {
    if (e.type === 'log' && e.line) addLog(e.line);
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
      // Bot 收件箱: 状态变更刷新设置页显示;归档成功刷新账号列表
      if (e.status === 'bot' && e.data) botStatus = { ...botStatus, ...(e.data as any) };
      if (e.status === 'bot_imported') loadAccounts();
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
    loadRecv();
    try {
      const p = await getPing();
      if (p?.version) {
        appVersion = String(p.version);
        addLog(`程序版本: v${appVersion}（报问题时请带上此版本号和 logs 目录日志）`);
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

<header class="topbar">
  <span class="title">TG小号工具箱</span>
  <span class="conn" class:on={connected && !connectingLabel}>{connectingLabel ? `● ${connectingLabel}` : connected ? '● 已连接' : '● 未连接'}</span>
  <button class="topbtn" onclick={doOpenAddAccount}>新建账号</button>
  <button class="topbtn" onclick={doReconnect}>重新连接</button>
  <button class="topbtn" onclick={doLaunchClient}
    oncontextmenu={(e) => { e.preventDefault(); doOpenAccountFolder(); }}
    title="启动当前账号的 Telegram 客户端（右键打开账号文件夹）">启动客户端</button>
  <button class="topbtn" onclick={doDisconnect}>断开连接</button>
  <button class="topbtn" onclick={doPack}>打包</button>
  <button class="topbtn iconbtn" onclick={toggleTheme} title={themeMode === 'dark' ? '切换到浅色' : '切换到深色'}>
    {themeMode === 'dark' ? '☀️' : '🌙'}
  </button>
  <button class="topbtn" onclick={loadSettings}>设置</button>
</header>

<svelte:window onmousemove={onWinMouseMove} onmouseup={onWinMouseUp} /><div class="layout">
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
          {g === 'all' ? '全部' : g === 'ungrouped' ? '未分组' : g}
        </button>
      {/each}
      <button class="grp add" onclick={doCreateGroup}>＋</button>
    </div>
    <input class="search" placeholder="搜索账号…" bind:value={search} oninput={onSearch} />
    <ul class="list">
      {#key filterVersion}
      {#each filtered as a}
        <li
          class="item"
          class:cur={current?.name === a.name}
          ondblclick={() => onConnect(a)}
          onclick={() => (current = a)}
          oncontextmenu={(e) => onAccountContext(e, a)}
        >
          <div class="avatar-wrap">
            {#if a.avatar && !avatarFailed.has(a.name)}
              <img class="avatar" src={avatarUrl(a)} alt="" onerror={() => onAvatarError(a.name)} />
            {:else}
              <span class="avatar" style="background:{avatarColor(a.name)}">{a.display?.[0] || a.username?.[0] || a.name[0] || '-'}</span>
            {/if}
            {#if onlineNames.has(a.name)}
              <span class="online-dot"></span>
            {/if}
          </div>
          <span class="meta">
            <span class="nm">
              {a.display || a.name}
              {#if (a as any).poll_alive === false}<span class="dead-tag" title={`轮询: ${(a as any).poll_msg || '死号'}${(a as any).poll_time ? ` @ ${(a as any).poll_time}` : ''}`}>死</span>{:else if (a as any).poll_alive === null}<span class="unk-tag" title={`轮询: ${(a as any).poll_msg || '状态未知'}${(a as any).poll_time ? ` @ ${(a as any).poll_time}` : ''} —— 状态未知，可重试或重新登录`}>?</span>{/if}
              {#if a.username}<span class="uname">{a.username}</span>{/if}
            </span>
            <span class="sub">{a.country ? `${a.country} ` : ''}{a.phone ? `+${a.phone}` : a.state}</span>
          </span>
          {#if a.state === 'tdata'}
            <button class="conv" onclick={(e) => { e.stopPropagation(); doConvertTdata(a); }}>转换</button>
          {/if}
        </li>
      {/each}
      {/key}
    </ul>
  </aside>

  {#if ctxMenu}
    <div class="ctx" style="left:{ctxMenu.x}px;top:{ctxMenu.y}px" onclick={(e) => e.stopPropagation()}>
      <div class="ctx-title">移动分组（可多选）</div>
      {#each Object.keys(groups) as g}
        <label class="ctx-check">
          <input
            class="ctx-check-native"
            type="checkbox"
            checked={(groups[g] || []).includes(ctxMenu.name)}
            onchange={() => doMoveAccount(ctxMenu.name, g)}
          />
          <span class="ctx-check-box" class:on={(groups[g] || []).includes(ctxMenu.name)}>
            {#if (groups[g] || []).includes(ctxMenu.name)}✓{/if}
          </span>
          <span>{g}</span>
        </label>
      {/each}
      <button onclick={() => { doMoveAccount(ctxMenu.name, 'ungrouped'); closeCtx(); }}>移出所有分组</button>
      {#if onlineNames.has(ctxMenu.name)}
        <button class="ctx-disconnect" onclick={() => { disconnectOne(ctxMenu.name); closeCtx(); }}>断开连接（保持其他在线）</button>
      {/if}
      <button onclick={() => { const a = accounts.find((x) => x.name === ctxMenu!.name); if (a) openRename(a); closeCtx(); }}>重命名文件夹…</button>
    </div>
  {/if}

  <div class="splitter" onmousedown={(e) => startDrag(e, 'left')}></div>

  <section class="mid" class:narrow={midW < 340} style="width:{midW}px">
    {#each cardOrder as c (c)}
      {#if c === '基本信息'}
    <details class="card" data-card="基本信息" open={isCardOpen('基本信息', true)} ontoggle={(e) => onCardToggle('基本信息', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>基本信息</summary>
      <div class="bi">
        {#if current?.avatar && !avatarFailed.has(current.name)}
          <img class="avatar big" src={avatarUrl(current)} alt="" onerror={() => onAvatarError(current.name)} />
        {:else}
          <span class="avatar big" style="background:{avatarColor(current?.name || '-')}">
            {current?.display?.[0] || current?.name?.[0] || '-'}
          </span>
        {/if}
        <div class="bi-meta">
          <div class="bi-name">{current?.display || current?.name || '未选择账号'}</div>
          <div class="bi-sub">@{current?.username || current?.phone || '-'}</div>
        </div>
        <button class="edit-btn" onclick={loadProfile}>编辑</button>
      </div>
    </details>
      {:else if c === '聊天'}
    <details class="card" data-card="聊天" open={isCardOpen('聊天', true)} ontoggle={(e) => onCardToggle('聊天', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>聊天</summary>
      <div class="chat-ctl">
        <div class="chat-switch-row">
          <span class="chat-switch-label">
            <span class="status-dot" class:on={recvOn}></span>
            接收新消息
            <em class="chat-state">{recvOn ? '监听中' : '已停止'}</em>
          </span>
          <button
            class="toggle"
            class:on={recvOn}
            role="switch"
            aria-checked={recvOn}
            title={recvOn ? '停止接收' : '开始接收'}
            onclick={() => applyRecv(!recvOn)}
          >
            <span class="toggle-thumb"></span>
          </button>
        </div>
        <div class="chat-entries">
          <button class="chat-entry" onclick={() => setView('chat')}>
            消息列表
            {#if chatUnread}<span class="badge">{chatUnread > 99 ? '99+' : chatUnread}</span>{/if}
          </button>
        </div>
      </div>
    </details>
      {:else if c === '安全'}
    <details class="card" data-card="安全" open={isCardOpen('安全', false)} ontoggle={(e) => onCardToggle('安全', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>安全</summary>
      <div class="grid">
        <md-outlined-button onclick={load2FA}>两步验证</md-outlined-button>
        <md-outlined-button onclick={loadPasskeys}>通行密钥</md-outlined-button>
        <md-outlined-button onclick={showEmail}>邮箱登录</md-outlined-button>
        <md-outlined-button onclick={loadDevices}>登录设备</md-outlined-button>
      </div>
    </details>
      {:else if c === '删除'}
    <details class="card" data-card="删除" open={isCardOpen('删除', true)} ontoggle={(e) => onCardToggle('删除', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>删除</summary>
      <div class="grid">
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-contacts')}>删联系人</md-outlined-button>
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-dialogs', { choice: 'users' })}>删对话</md-outlined-button>
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-dialogs', { choice: 'bots' })}>删机器人</md-outlined-button>
        <md-outlined-button onclick={() => postTask('/api/tasks/delete-dialogs', { choice: 'groups' })}>删频道</md-outlined-button>
      </div>
      <div class="speed-row">
        <span class="speed-label">速度</span>
        <div class="speed-seg">
          {#each SPEED_SEG as [label, v]}
            <button class="seg" class:on={speedVal === v} onclick={() => onSpeed(v)}>{label}</button>
          {/each}
        </div>
      </div>
    </details>
      {:else if c === '转换'}
    <details class="card" data-card="转换" open={isCardOpen('转换', false)} ontoggle={(e) => onCardToggle('转换', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>转换</summary>
      <div class="conv-group">
        <md-outlined-button class="full-row" onclick={doOpenTdataToSs}>tdata 转 session+json</md-outlined-button>
        <md-outlined-button class="full-row" onclick={doOpenConvertTdata} disabled={converting}>{converting ? '转换中…' : 'session+json 转 tdata'}</md-outlined-button>
        <md-outlined-button onclick={doRefreshSsBatch}>刷新session（批量修复测活失败）</md-outlined-button>
      </div>
    </details>
      {:else if c === '其他设置'}
    <details class="card" data-card="其他设置" open={isCardOpen('其他设置', false)} ontoggle={(e) => onCardToggle('其他设置', (e.currentTarget as HTMLDetailsElement).open)}>
      <summary>其他设置</summary>
      <div class="grid">
        <md-outlined-button onclick={() => updateTelegram()}>安装升级客户端</md-outlined-button>
        <md-outlined-button onclick={doRefreshAccountInfo}>刷新账号信息</md-outlined-button>
        <md-outlined-button onclick={doPollAccounts}>账号轮询</md-outlined-button>
        <md-outlined-button onclick={openJoinView}>加群频道…</md-outlined-button>
        <md-outlined-button onclick={doExportAccounts} disabled={exporting}>{exporting ? '导出中…' : '导出表格'}</md-outlined-button>
        <md-outlined-button class="danger-btn" onclick={doOpenDeleteAccount}>删除账号</md-outlined-button>
      </div>
    </details>
      {/if}
    {/each}
  </section>

  <div class="splitter" onmousedown={(e) => startDrag(e, 'mid')}></div>

  <section class="right">
    {#if rightView === 'log'}
      <div class="sec-head">
        <h3>日志</h3>
        {#if lastView !== 'log'}
          <button class="back" onclick={() => setView(lastView)}>返回</button>
        {/if}
      </div>
      <div class="prog">
        <span>{progress.label || '无任务'}</span>
        <span>{progress.total ? `${progress.done}/${progress.total}` : ''}</span>
      </div>
      {#if progress.total}
        <div class="prog-bar">
          <div class="prog-fill" style="width:{Math.min(100, Math.round((progress.done / progress.total) * 100))}%"></div>
        </div>
      {/if}
      {#if !logs.length}
        <p class="empty">暂无日志</p>
      {/if}
      <ul class="log">
        {#each logs as l}<li>{l}</li>{/each}
      </ul>
    {:else if rightView === 'chat'}
      {#if !curDialog}
        <div class="sec-head">
          <h3>会话{#if chatUnread} <span class="badge">{chatUnread > 99 ? '99+' : chatUnread}</span>{/if}</h3>
          <span class="head-btns">
            <button class="back" onclick={() => setView('log')}>日志</button>
            <button class="back" onclick={loadDialogs}>{dialogsLoading ? '加载中…' : '⟳ 刷新'}</button>
          </span>
        </div>
        <div class="chat-switch-row">
          <span class="chat-switch-label">
            <span class="status-dot" class:on={recvOn}></span>
            接收新消息
          </span>
          <button
            class="toggle"
            class:on={recvOn}
            role="switch"
            aria-checked={recvOn}
            title={recvOn ? '停止接收' : '开始接收'}
            onclick={() => applyRecv(!recvOn)}
          >
            <span class="toggle-thumb"></span>
          </button>
        </div>
        <div class="recv-rules">
          <button class="rule-chip" class:on={recvRules.exclude_channels} onclick={() => onRecvRuleChange('exclude_channels')}>{recvRules.exclude_channels ? '✓ ' : ''}排除频道</button>
          <button class="rule-chip" class:on={recvRules.exclude_groups} onclick={() => onRecvRuleChange('exclude_groups')}>{recvRules.exclude_groups ? '✓ ' : ''}排除群组</button>
          <button class="rule-chip" class:on={recvRules.exclude_bots} onclick={() => onRecvRuleChange('exclude_bots')}>{recvRules.exclude_bots ? '✓ ' : ''}排除机器人</button>
        </div>
        <div class="start-chat-row">
          <input
            class="chat-input"
            placeholder="用户名（@xxx），回车发起聊天"
            bind:value={startChatName}
            disabled={!current || !onlineNames.has(current.name)}
            onkeydown={(e) => { if (e.key === 'Enter') doStartChat(); }}
          />
          <button class="send-btn" disabled={!startChatName.trim() || startingChat} onclick={doStartChat}>
            {startingChat ? '查找中…' : '聊天'}
          </button>
        </div>
        {#if !current}
          <p class="empty">请先选择账号</p>
        {:else if !onlineNames.has(current.name)}
          <p class="empty">请先连接账号再查看会话</p>
        {:else if !dialogs.length}
          <p class="empty">{dialogsLoading ? '正在加载会话…' : '暂无会话，点右上角「刷新」获取'}</p>
        {/if}
        <ul class="dlg-list">
          {#each dialogs as d (d.id)}
            <li class="dlg" onclick={() => openDialog(d)}>
              <span class="dlg-ava" style="background:{avatarColor(d.name)}">{(d.name || '?')[0]}</span>
              <div class="dlg-body">
                <div class="dlg-row1">
                  <span class="dlg-name">{d.name}</span>
                  <span class="dlg-time">{d.last_date}</span>
                </div>
                <div class="dlg-row2">
                  <span class="dlg-last">{d.last_text || ' '}</span>
                  {#if d.unread}<span class="badge">{d.unread > 99 ? '99+' : d.unread}</span>{/if}
                </div>
              </div>
            </li>
          {/each}
        </ul>
      {:else}
        <div class="sec-head">
          <h3>{curDialog.name}</h3>
          <span class="head-btns">
            <button class="back" onclick={() => setView('log')}>日志</button>
            <button class="back" onclick={() => (curDialog = null)}>会话列表</button>
          </span>
        </div>
        {#if historyHasMore}
          <button class="load-older" disabled={historyLoading} onclick={() => loadHistory(false)}>
            {historyLoading ? '加载中…' : '加载更早消息'}
          </button>
        {/if}
        <ul class="chat-history">
          {#each historyMsgs as m (m.id)}
            <li class="bbl-row" class:out={m.out}>
              <div class="bbl">
                {#if !m.out && curDialog.type === 'group' && m.sender}<span class="bbl-sender">{m.sender}</span>{/if}
                <div class="bbl-text">{m.text || '[媒体消息]'}<span class="bbl-time">{m.date}{m.out ? ' ✓✓' : ''}</span></div>
              </div>
            </li>
          {/each}
          {#if historyError}
            <p class="empty" style="color: var(--md-sys-color-error)">
              历史消息加载失败：{historyError}
              <button class="back" onclick={() => loadHistory(true)}>[重试]</button>
            </p>
          {:else if !historyMsgs.length}
            <p class="empty">{historyLoading ? '正在加载…' : '暂无消息'}</p>
          {/if}
        </ul>
        <div class="chat-input-row">
          <input
            class="chat-input"
            placeholder="输入消息（仅支持文本）"
            bind:value={chatDraft}
            disabled={!onlineNames.has(current?.name || '')}
            onkeydown={(e) => { if (e.key === 'Enter') doSendMsg(); }}
          />
          <button class="send-btn" disabled={sending || !chatDraft.trim()} onclick={doSendMsg}>
            {sending ? '发送中…' : '发送'}
          </button>
        </div>
      {/if}

    {:else if rightView === 'passkey'}
      <div class="sec-head">
        <h3>通行密钥</h3>
        <button class="back" onclick={() => setView('log')}>日志</button>
      </div>
      <md-filled-button onclick={doInitPasskey}>＋ 添加通行密钥</md-filled-button>
      {#if pkQrImg}
        <div class="qr-box">
          <img class="qr-img" src={pkQrImg} alt="通行密钥二维码" />
          <p class="qr-tip">请用<b>手机系统相机 / Google 智能镜头</b>扫描<br />（由手机密码管理器完成通行密钥注册；Telegram 客户端不参与扫码）</p>
        </div>
      {/if}
      <ul class="sec-list">
        {#each passkeys as pk}
          <li class="sec-item">
            <span>{pk.name || '（未命名）'}</span>
            <button class="danger" onclick={() => doDeletePasskey(pk.id)}>删除</button>
          </li>
        {/each}
      </ul>
      {#if !passkeys.length}<p class="empty">暂无通行密钥</p>{/if}
    {:else if rightView === '2fa'}
      <div class="sec-head">
        <h3>两步验证</h3>
        <button class="back" onclick={() => setView('log')}>日志</button>
      </div>
      <p>当前状态：{has2fa ? '已开启' : '未开启'}</p>
      {#if has2fa}
        <input placeholder="当前密码" bind:value={cur2fa} />
      {/if}
      <input placeholder="新密码" bind:value={new2fa} />
      <md-filled-button onclick={doSet2FA}>设置/修改</md-filled-button>
    {:else if rightView === 'email'}
      <div class="sec-head">
        <h3>邮箱登录</h3>
        <button class="back" onclick={() => setView('log')}>日志</button>
      </div>
      {#if boundEmail && !showEmailForm}
        <div class="bound-box">
          <div class="bound-label">已绑定邮箱</div>
          <div class="bound-email">{boundEmail}</div>
        </div>
        <md-outlined-button onclick={() => (showEmailForm = true)}>换绑邮箱</md-outlined-button>
      {:else}
        {#if boundEmail}
          <p class="set-hint">当前绑定：{boundEmail}。填写新邮箱完成换绑。</p>
        {/if}
        {#if emailPresets.length}
          <div class="rename-quick">
            <span class="rename-quick-label">预选邮箱:</span>
            {#each emailPresets as p}
              <button class="rule-chip" onclick={() => (emailInput = p)}>{p}</button>
            {/each}
          </div>
        {/if}
        <input placeholder="邮箱地址" bind:value={emailInput} />
        <md-outlined-button onclick={doSendEmail}>发送验证码</md-outlined-button>
        <input placeholder="验证码" bind:value={codeInput} />
        <md-filled-button onclick={doVerifyEmail}>验证绑定</md-filled-button>
      {/if}
    {:else if rightView === 'devices'}
      <div class="sec-head">
        <h3>登录设备</h3>
        <button class="back" onclick={() => setView('log')}>日志</button>
      </div>
      <ul class="sec-list">
        {#each devices as d}
          <li class="sec-item">
            <span>{d.device_model || '未知设备'}{d.current ? '（本设备）' : ''}</span>
            {#if !d.current}
              <button class="danger" onclick={() => doDeleteDevice(d.hash)}>删除</button>
            {/if}
          </li>
        {/each}
      </ul>
      {#if !devices.length}<p class="empty">暂无设备</p>{/if}
    {:else if rightView === 'profile'}
      <div class="sec-head">
        <h3>编辑资料</h3>
        <button class="back" onclick={() => setView('log')}>日志</button>
      </div>
      <div class="bi">
        {#if current?.avatar && !avatarFailed.has(current.name)}
          <img class="avatar big" src={avatarUrl(current)} alt="" onerror={() => onAvatarError(current.name)} />
        {:else}
          <span class="avatar big" style="background:{avatarColor(current?.name || '-')}">{current?.display?.[0] || current?.name?.[0] || '-'}</span>
        {/if}
        <div class="bi-meta">
          <div class="bi-name">{current?.display || current?.name || '未选择账号'}</div>
          <div class="bi-sub">@{current?.username || '-'}</div>
        </div>
      </div>
      <div class="form">
        <label>名字</label>
        <input bind:value={editFirstName} />
        <label>姓氏</label>
        <input bind:value={editLastName} />
        <label>用户名（不带 @）</label>
        <input bind:value={editUsername} />
        <label>简介</label>
        <textarea
          bind:value={editAbout}
          bind:this={aboutEl}
          rows="1"
        ></textarea>
        <label>生日（月 / 日 / 年）</label>
        <div class="row3">
          <input placeholder="月" bind:value={editMonth} />
          <input placeholder="日" bind:value={editDay} />
          <input placeholder="年" bind:value={editYear} />
        </div>
        <label>头像</label>
        <input type="file" accept="image/*" onchange={doUploadAvatar} />
        <md-filled-button onclick={doSaveProfile}>保存</md-filled-button>
      </div>
    {:else if rightView === 'join'}
      <div class="sec-head">
        <h3>加群频道</h3>
        <button class="back" onclick={() => setView('log')}>日志</button>
      </div>
      <div class="join-toolbar">
        <md-outlined-button onclick={doJoinAddEntry}>＋ 添加链接</md-outlined-button>
      </div>
      {#each [['group', '群'], ['channel', '频道']] as [cat, catLabel]}
        <div class="join-cat">{catLabel}</div>
        <ul class="sec-list">
          {#each joinEntries as e, i (i)}
            {#if e.type === cat}
              <li class="sec-item join-item">
                {#if joinEditIdx === i}
                  <!-- 行内编辑: 类型+备注+链接,确定/取消 -->
                  <div class="join-edit">
                    <div class="join-edit-row">
                      <select class="set-select join-type" bind:value={e.type}>
                        <option value="group">群</option>
                        <option value="channel">频道</option>
                      </select>
                      <input class="set-input join-name" bind:value={e.name} placeholder="备注名" />
                    </div>
                    <input class="set-input join-link" bind:value={e.link} placeholder="https://t.me/xxx 或 @xxx 或邀请链接" />
                    <div class="join-edit-btns">
                      <md-outlined-button onclick={doJoinCancelEdit}>取消</md-outlined-button>
                      <md-filled-button onclick={() => doJoinSaveEdit(i)}>保存</md-filled-button>
                    </div>
                  </div>
                {:else}
                  <span class="join-item-meta">
                    <b>{e.name || '(未命名)'}</b>
                    <small>{e.link}</small>
                  </span>
                  <span class="join-item-ops">
                    <button class="back" onclick={() => doJoinOne(e)}>加入</button>
                    <button class="icon-btn" title="编辑" onclick={() => (joinEditIdx = i)}>✎</button>
                    <button class="icon-btn danger" title="删除" onclick={() => doJoinDelete(i)}>✕</button>
                  </span>
                {/if}
              </li>
            {/if}
          {/each}
          {#if !joinEntries.some((e) => e.type === cat)}
            <li class="empty">暂无{catLabel}链接，点上方「添加链接」</li>
          {/if}
        </ul>
      {/each}
      {#if joinEntries.length}
        <md-outlined-button class="full-row" onclick={doJoinChats}>全部加入（当前账号）</md-outlined-button>
      {/if}
    {/if}
  </section>
</div>

  {#if groupMenu}
    <div class="ctx" style="left:{groupMenu.x}px;top:{groupMenu.y}px" onclick={(e) => e.stopPropagation()}>
      <div class="ctx-title">分组：{groupMenu.name}</div>
      <button onclick={doOpenGroupRename}>重命名…</button>
      <button class="ctx-disconnect" onclick={doOpenGroupDelete}>删除分组（账号回未分组）</button>
    </div>
  {/if}

  {#if groupRenameOpen}
  <div class="modal-mask" onclick={() => (groupRenameOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>分组重命名</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (groupRenameOpen = false)}>✕</button>
      </div>
      <input
        class="rename-input"
        bind:value={groupRenameInput}
        onkeydown={(e) => { if (e.key === 'Enter') doGroupRenameConfirm(); }}
        placeholder="输入新的分组名称"
        maxlength="30"
      />
      <div class="rename-btns">
        <md-outlined-button onclick={() => (groupRenameOpen = false)}>取消</md-outlined-button>
        <md-filled-button disabled={!groupRenameInput.trim()} onclick={doGroupRenameConfirm}>确定</md-filled-button>
      </div>
    </div>
  </div>
{/if}

{#if addAccOpen}
  <div class="modal-mask" onclick={() => closeAddAcc()}>
    <div class="modal rename-modal addacc-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>新建账号</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => closeAddAcc()}>✕</button>
      </div>
      <div class="mode-seg addacc-tabs">
        <button class="mode-item" class:on={addAccTab === 'files'} onclick={() => (addAccTab = 'files')}>拖入文件</button>
        <button class="mode-item" class:on={addAccTab === 'qr'} onclick={() => doStartQrLogin()}>扫码登录</button>
        <button class="mode-item" class:on={addAccTab === 'phone'} onclick={() => (addAccTab = 'phone')}>手机号登录</button>
      </div>
      {#if addAccTab === 'files'}
        <div
          class="addacc-drop"
          class:over={addAccDragging}
          ondragover={onAddAccDragOver}
          ondragleave={() => (addAccDragging = false)}
          ondrop={onAddAccDrop}
        >
          <div class="addacc-drop-icon">⬇</div>
          <div>拖入文件创建账号</div>
          <small>.session / .json / 2fa.txt / .zip（tdata 或 session+json 打包）</small>
          <small>zip 将自动解压；tdata 将自动转换为 session</small>
        </div>
        {#if addAccFiles.length}
          <ul class="addacc-list">
            {#each addAccFiles as f, i}
              <li class="sec-item">
                <span>{f.name}</span>
                <button class="icon-btn" title="移除" onclick={() => addAccRemove(i)}>✕</button>
              </li>
            {/each}
          </ul>
        {/if}
        <div class="rename-btns">
          <md-outlined-button onclick={() => closeAddAcc()}>取消</md-outlined-button>
          <md-filled-button disabled={!addAccFiles.length || addAccBusy} onclick={doAddAccountConfirm}>
            {addAccBusy ? '创建中…' : '创建账号'}
          </md-filled-button>
        </div>
      {:else}
        <div class="qrlogin-box">
          {#if qrImg}
            <img class="qr-img" src={`data:image/png;base64,${qrImg}`} alt="登录二维码" />
            <p class="qr-tip">手机 Telegram → 设置 → 设备 → <b>链接桌面设备</b>，扫描此二维码</p>
            <p class="qr-tip qr-status">
              {#if qrStatus === 'waiting'}等待扫码确认…（{qrRemain}s 后过期）{/if}
              {#if qrStatus === 'expired'}二维码已过期，请关闭后重试{/if}
              {#if qrStatus === 'error'}{qrErr}{/if}
            </p>
          {:else if qrStatus === 'loading'}
            <p class="empty">正在生成二维码…</p>
          {:else}
            <p class="empty">{qrErr || '点击「扫码登录」标签页生成二维码'}</p>
          {/if}
        </div>
        <div class="rename-btns">
          <md-outlined-button onclick={() => closeAddAcc(true)}>取消登录</md-outlined-button>
        </div>
      {:else if addAccTab === 'phone'}
        <div class="phonelogin-box">
          {#if phoneStage === 'phone'}
            <div class="set-row set-row-col">
              <span class="set-label">手机号码（含国家区号，如 6281234567890）</span>
              <input class="set-input" inputmode="numeric" placeholder="6281234567890"
                bind:value={phoneInput} onkeydown={(e) => { if (e.key === 'Enter') doPhoneLoginStart(); }} />
            </div>
            {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
            <div class="rename-btns">
              <md-filled-button disabled={!phoneInput.trim() || phoneBusy} onclick={doPhoneLoginStart}>
                {phoneBusy ? '发送中…' : '发送验证码'}
              </md-filled-button>
            </div>
          {:else if phoneStage === 'code'}
            <p class="set-hint">验证码已发送至 +{phoneInput}，请查收短信/TG 官方消息</p>
            <div class="set-row set-row-col">
              <span class="set-label">验证码</span>
              <input class="set-input" inputmode="numeric" placeholder="登录验证码"
                bind:value={phoneCode} onkeydown={(e) => { if (e.key === 'Enter') doPhoneLoginSubmit(); }} />
            </div>
            {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
            <div class="rename-btns">
              <md-outlined-button onclick={() => phoneReset()}>重填手机号</md-outlined-button>
              <md-filled-button disabled={!phoneCode.trim() || phoneBusy} onclick={doPhoneLoginSubmit}>
                {phoneBusy ? '验证中…' : '登录'}
              </md-filled-button>
            </div>
          {:else if phoneStage === 'password'}
            <p class="set-hint">该账号开启了两步验证，请输入 2FA 密码</p>
            <div class="set-row set-row-col">
              <span class="set-label">两步验证密码</span>
              <input class="set-input" type="password" autocomplete="new-password" placeholder="2FA 密码"
                bind:value={phonePwd} onkeydown={(e) => { if (e.key === 'Enter') doPhoneLoginSubmit(); }} />
            </div>
            {#if phoneErr}<p class="set-hint" style="color: var(--md-sys-color-error)">{phoneErr}</p>{/if}
            <div class="rename-btns">
              <md-filled-button disabled={!phonePwd || phoneBusy} onclick={doPhoneLoginSubmit}>
                {phoneBusy ? '验证中…' : '登录'}
              </md-filled-button>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if groupDelOpen}
  <div class="modal-mask" onclick={() => (groupDelOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>删除分组</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (groupDelOpen = false)}>✕</button>
      </div>
      <p class="set-hint">
        删除分组「<b>{groupDelTarget}</b>」？组内账号不受影响，将归入「未分组」。
      </p>
      <div class="rename-btns">
        <md-outlined-button onclick={() => (groupDelOpen = false)}>取消</md-outlined-button>
        <md-filled-button class="danger-btn" disabled={groupDeleting} onclick={doGroupDeleteConfirm}>
          {groupDeleting ? '删除中…' : '删除'}
        </md-filled-button>
      </div>
    </div>
  </div>
{/if}

{#if t2sOpen && current}
  <div class="modal-mask" onclick={() => (t2sOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>tdata 转 session+json（覆盖刷新会话）</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (t2sOpen = false)}>✕</button>
      </div>
      <p class="set-hint">
        使用账号 <b>{current.display || current.name}</b> 的 <b>tdata</b> 重新生成 session+json，覆盖现有会话数据。适用于 session 过期导致测活失败的账号。
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
          bind:value={convTwofa} placeholder="开启两步验证的账号必填；留空使用 json 中保存的密码" />
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
  <div class="modal-mask" onclick={() => (delOpen = false)}>
    <div class="modal rename-modal del-modal" onclick={(e) => e.stopPropagation()}>
      <div class="del-icon">
        <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor" aria-hidden="true">
          <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
        </svg>
      </div>
      <div class="del-title">删除账号</div>
      <p class="del-sub">此操作<b>不可恢复</b>。将永久删除该账号的 session、tdata、登录凭据等全部文件，删除后只能重新登录。</p>
      <div class="set-group">
        <div class="set-row">
          <span class="set-label">账号</span>
          <span class="del-val">{delTarget.display || delTarget.name}</span>
        </div>
        {#if delTarget.uid}<div class="set-row">
          <span class="set-label">UID</span>
          <span class="del-val mono">{delTarget.uid}</span>
        </div>{/if}
        <div class="set-row set-row-col">
          <span class="set-label">将删除的文件夹</span>
          <code class="del-path">{delTarget.path}</code>
        </div>
      </div>
      <label class="del-check">
        <input type="checkbox" bind:checked={delConfirm} />
        <span>我已了解该操作不可恢复，确认删除该账号的全部文件</span>
      </label>
      <div class="rename-btns">
        <md-outlined-button onclick={() => (delOpen = false)}>取消</md-outlined-button>
        <md-filled-button class="danger-btn" disabled={deleting || !delConfirm} onclick={doDeleteAccount}>
          {deleting ? '删除中…' : '永久删除'}
        </md-filled-button>
      </div>
    </div>
  </div>
{/if}

{#if groupModalOpen}
  <div class="modal-mask" onclick={() => (groupModalOpen = false)}>
    <div class="modal rename-modal" onclick={(e) => e.stopPropagation()}>
      <div class="rename-head">
        <span>新建分组</span>
        <button class="back set-close rename-x" title="关闭" onclick={() => (groupModalOpen = false)}>✕</button>
      </div>
      <input
        class="rename-input"
        bind:value={groupInput}
        onkeydown={(e) => { if (e.key === 'Enter') doCreateGroupConfirm(); }}
        placeholder="输入分组名称"
        maxlength="30"
      />
      <div class="rename-btns">
        <md-outlined-button onclick={() => (groupModalOpen = false)}>取消</md-outlined-button>
        <md-filled-button disabled={groupCreating || !groupInput.trim()} onclick={doCreateGroupConfirm}>
          {groupCreating ? '处理中…' : '确定'}
        </md-filled-button>
      </div>
    </div>
  </div>
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
          <span class="rename-quick-label">快捷填充:</span>
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
  <div class="modal-mask" onclick={() => (settingsOpen = false)}>
    <div class="modal settings-modal" onclick={(e) => e.stopPropagation()}>
      <div class="set-nav">
        <div class="set-title">设置</div>
        <button class="set-nav-item" class:on={settingsSection === 'general'} onclick={() => (settingsSection = 'general')}><span class="set-nav-icon">⚙️</span>通用</button>
        <button class="set-nav-item" class:on={settingsSection === 'appearance'} onclick={() => (settingsSection = 'appearance')}><span class="set-nav-icon">🎨</span>外观</button>
        <button class="set-nav-item" class:on={settingsSection === 'proxy'} onclick={() => (settingsSection = 'proxy')}><span class="set-nav-icon">🌐</span>代理</button>
        <button class="set-nav-item" class:on={settingsSection === 'join'} onclick={() => (settingsSection = 'join')}><span class="set-nav-icon">📨</span>加群频道</button>
        <button class="set-nav-item" class:on={settingsSection === 'whitelist'} onclick={() => { settingsSection = 'whitelist'; loadWhitelist(); }}><span class="set-nav-icon">🛡️</span>白名单</button>
        <button class="set-nav-item" class:on={settingsSection === 'bot'} onclick={() => { settingsSection = 'bot'; refreshBotStatus(); }}><span class="set-nav-icon">🤖</span>Bot收件箱</button>
        <button class="set-nav-item" class:on={settingsSection === 'about'} onclick={() => (settingsSection = 'about')}><span class="set-nav-icon">ℹ️</span>关于</button>
      </div>
      <div class="set-content">
        {#if settingsSection === 'general'}
          <div class="set-sec-title">通用</div>
          <div class="set-group">
            <div class="set-row">
              <span class="set-label">打包文件命名格式</span>
              <input class="set-input" bind:value={settings.pack_naming} placeholder="{name}_账号包" />
            </div>
            <div class="set-row">
              <span class="set-label">默认压缩密码（AES-256）</span>
              <input class="set-input" type="password" autocomplete="new-password" bind:value={settings.pack_password} placeholder="留空则不加密" />
            </div>
            <div class="set-row">
              <span class="set-label">日志等级</span>
              <select class="set-select" bind:value={settings.log_level}>
                <option value="info">常规（info）</option>
                <option value="debug">调试（debug，含蓝牙诊断等原始日志）</option>
              </select>
            </div>
            <div class="set-row set-row-col">
              <span class="set-label">文件夹重命名快捷项（勾选在弹窗中显示）</span>
              <div class="check-row">
                {#each RENAME_QUICK_DEFS as [k, label]}
                  <label class="check-item">
                    <input
                      type="checkbox"
                      checked={((settings.rename_quick as string[]) || []).includes(k)}
                      onchange={() => toggleRenameQuick(k)}
                    />
                    <span>{label}</span>
                  </label>
                {/each}
              </div>
            </div>
            <div class="set-row">
              <span class="set-label">快捷项自定义前缀</span>
              <input class="set-input" bind:value={settings.rename_prefix} placeholder="例如 tg_（点快捷项时自动加在前面）" />
            </div>
          </div>
        {:else if settingsSection === 'appearance'}
          <div class="set-sec-title">外观</div>
          <div class="set-group">
            <div class="mode-seg">
              <button class="mode-item" class:on={themeMode === 'light'} title="浅色" onclick={() => setThemeMode('light')}>
                {#if themeMode === 'light'}✓{/if} ☀️ 浅色
              </button>
              <button class="mode-item" class:on={themeMode === 'dark'} title="深色" onclick={() => setThemeMode('dark')}>
                {#if themeMode === 'dark'}✓{/if} 🌙 深色
              </button>
            </div>
          </div>
          <div class="set-group-title">色彩主题</div>
          <div class="set-group">
            <div class="swatch-grid">
              {#each PRESET_COLORS as c (c)}
                <button
                  class="swatch"
                  class:on={((settings.theme_seed as string) || '').toLowerCase() === c.toLowerCase()}
                  style="--sw:{c};--sw-light:color-mix(in srgb, {c} 55%, white)"
                  title={c}
                  onclick={() => applyPreset(c)}
                ></button>
              {/each}
              <label class="swatch custom" class:on={!isPreset()} title="自定义颜色">
                🖌️
                <input type="color" bind:value={settings.theme_seed} onchange={() => applyTheme()} />
              </label>
            </div>
          </div>
          <div class="set-group-title">详细调整</div>
          <div class="set-group">
            <div class="set-row">
              <span class="set-label">背景浅色</span>
              <input class="set-color" type="color" bind:value={settings.theme_bg} onchange={() => applyTheme()} />
            </div>
            <div class="set-row">
              <span class="set-label">背景深色（卡片）</span>
              <input class="set-color" type="color" bind:value={settings.theme_dark} onchange={() => applyTheme()} />
            </div>
            <div class="set-row">
              <span class="set-label">顶栏颜色</span>
              <input class="set-color" type="color" bind:value={settings.theme_topbar} onchange={() => applyTheme()} />
            </div>
          </div>
          <div class="set-group-title">功能区排序</div>
          <div class="set-group">
            {#each cardOrder as c, i (c)}
              <div class="set-row">
                <span class="set-label">{c}</span>
                <span class="order-btns">
                  <button class="order-btn" disabled={i === 0} title="上移" onclick={() => moveCard(i, -1)}>↑</button>
                  <button class="order-btn" disabled={i === cardOrder.length - 1} title="下移" onclick={() => moveCard(i, 1)}>↓</button>
                </span>
              </div>
            {/each}
          </div>
        {:else if settingsSection === 'proxy'}
          <div class="set-sec-title">代理</div>
          <div class="set-group">
            <div class="set-row">
              <span class="set-label">代理模式</span>
              <select class="set-select" bind:value={settings.proxy_mode}>
                <option value="none">不使用代理</option>
                <option value="system">使用系统代理</option>
                <option value="manual">手动设置</option>
              </select>
            </div>
            {#if settings.proxy_mode === 'manual'}
              <div class="set-row">
                <span class="set-label">代理类型</span>
                <select class="set-select" bind:value={settings.proxy_scheme}>
                  <option value="socks5">SOCKS5</option>
                  <option value="socks4">SOCKS4</option>
                  <option value="http">HTTP</option>
                </select>
              </div>
              <div class="set-row">
                <span class="set-label">IP 地址</span>
                <input class="set-input" bind:value={settings.proxy_host} placeholder="127.0.0.1" />
              </div>
              <div class="set-row">
                <span class="set-label">端口</span>
                <input class="set-input" bind:value={settings.proxy_port} placeholder="7890" />
              </div>
            {/if}
          </div>
        {:else if settingsSection === 'join'}
          <div class="set-sec-title">加群频道 · 预选</div>
          <p class="set-hint">
            群/频道链接的添加、编辑、加入已移至「其他设置 → 加群频道…」页面，本页仅维护预选数据。
          </p>
          <div class="set-group-title">预选邮箱（绑定登录邮箱时一键填入）</div>
          <div class="set-group">
            {#each emailPresets as p, i}
              <div class="join-edit-row">
                <input class="set-input join-link" bind:value={emailPresets[i]} placeholder="邮箱地址" />
                <button class="order-btn" title="删除此条" onclick={() => emailPresets.splice(i, 1)}>✕</button>
              </div>
            {/each}
            {#if !emailPresets.length}
              <p class="empty">还没有预选邮箱，点下方「添加邮箱」</p>
            {/if}
            <md-outlined-button onclick={() => emailPresets = [...emailPresets, '']}>＋ 添加邮箱</md-outlined-button>
          </div>
          <div class="set-footer-btn">
            <md-outlined-button onclick={() => { settingsOpen = false; openJoinView(); }}>前往加群频道页面 →</md-outlined-button>
          </div>
        {:else if settingsSection === 'whitelist'}
          <div class="set-sec-title">白名单</div>
          <p class="set-hint">白名单内的用户/群永久受删除任务保护。</p>
          <div class="set-group-title">用户白名单</div>
          <div class="set-group">
            <div class="join-edit-row">
              <input class="set-input join-link" placeholder="用户 ID" bind:value={wlUserInput} />
              <md-outlined-button onclick={doAddUser}>添加</md-outlined-button>
            </div>
            <ul class="sec-list">
              {#each wlUsers as u}
                <li class="sec-item"><span>{u}</span><button class="danger" onclick={() => doRemoveUser(u)}>移除</button></li>
              {/each}
            </ul>
          </div>
          <div class="set-group-title">群/频道白名单</div>
          <div class="set-group">
            <div class="join-edit-row">
              <input class="set-input join-link" placeholder="群 ID" bind:value={wlGroupInput} />
              <md-outlined-button onclick={doAddGroup}>添加</md-outlined-button>
            </div>
            <ul class="sec-list">
              {#each wlGroups as g}
                <li class="sec-item"><span>{g}</span><button class="danger" onclick={() => doRemoveGroup(g)}>移除</button></li>
              {/each}
            </ul>
          </div>
        {:else if settingsSection === 'bot'}
          <div class="set-sec-title">Bot 收件箱</div>
          <p class="set-hint">
            本地运行一个 TG Bot 接收器：把账号文件（.session / 凭据 .json / zip 包 / 2fa.txt）从任意设备转发给它，自动识别并归档进账号列表。先在 @BotFather 免费创建 bot 拿到 token。
          </p>
          <div class="set-group">
            <div class="set-row">
              <span class="set-label">运行状态</span>
              <span>
                {botStatus.running ? `✅ 运行中 @${botStatus.username || botStatus.id}` : '⏹ 未运行'}
                {#if botStatus.error && !botStatus.running}<span class="bot-err">（{botStatus.error}）</span>{/if}
              </span>
            </div>
            <div class="set-row">
              <span class="set-label">Bot Token</span>
              <input class="set-input" type="password" autocomplete="new-password" bind:value={settings.bot_token} placeholder="123456789:AAE…（改动后需重新启动）" />
            </div>
            <div class="set-row set-row-col">
              <span class="set-label">允许的用户 ID（逗号分隔，只接收这些人的文件）</span>
              <input class="set-input" bind:value={botAllowedInput} placeholder="例如 123456789, 987654321" />
            </div>
            <div class="set-row">
              <span class="set-label">启动程序时自动运行</span>
              <label class="check-item">
                <input type="checkbox" bind:checked={settings.bot_on} />
                <span>开启</span>
              </label>
            </div>
          </div>
          <div class="set-footer-btn">
            {#if botStatus.running}
              <md-outlined-button disabled={botBusy} onclick={doStopBot}>{botBusy ? '处理中…' : '停止 Bot'}</md-outlined-button>
            {:else}
              <md-filled-button disabled={botBusy} onclick={doStartBot}>{botBusy ? '启动中…' : '保存并启动 Bot'}</md-filled-button>
            {/if}
          </div>
          <p class="set-hint">
            使用：在任意设备上把账号文件转发给你的 bot（可多选一起发，同一批自动合并成一个账号；每个 zip 单独成一个账号）。加密账号包把密码写在转发的文字说明里，或提前填好「通用 → 默认压缩密码」。不知道自己的用户 ID？先启动 bot，给它发任意消息，它会回复你的 ID；允许列表保存后即时生效，不用重启 bot。
          </p>
        {:else if settingsSection === 'about'}
          <div class="set-sec-title">关于</div>
          <div class="about-list">
            <div class="about-row"><span class="set-label">程序名</span><span>TG小号工具箱（Web版）</span></div>
            <div class="about-row"><span class="set-label">版本</span><span class="about-ver">v{appVersion || '…'}</span></div>
            <div class="about-row"><span class="set-label">仓库</span><span>github.com/Gutouoff/TG-tools</span></div>
          </div>
        {:else}
          <div class="set-sec-title">通用</div>
        {/if}
        <div class="set-footer">
          <md-filled-button onclick={doSaveSettings}>保存设置</md-filled-button>
        </div>
      </div>
      <button class="back set-close" title="关闭" onclick={() => (settingsOpen = false)}>✕</button>
    </div>
  </div>
{/if}

<style>
  .topbar {
    display: flex;
    align-items: center;
    height: 64px;
    padding: 0 24px;
    background: var(--topbar-color, #00796B);
    color: #FFFFFF;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
    position: relative;
    z-index: 10;
  }
  .title {
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 0.5px;
    white-space: nowrap;
  }
  .conn {
    margin-left: auto;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.75);
    white-space: nowrap;
    flex-shrink: 0;
  }
  .conn.on {
    color: #A5D6A7;
  }
  .layout {
    display: flex;
    gap: 6px;
    padding: 12px;
    height: calc(100% - 64px);
  }
  .splitter {
    width: 6px;
    cursor: col-resize;
    flex-shrink: 0;
    border-radius: 3px;
    transition: background 0.15s;
  }
  .splitter:hover,
  .splitter:active {
    background: var(--md-sys-color-primary-container);
  }
  .left,
  .mid,
  .right {
    background: var(--md-sys-color-surface-container);
    border-radius: var(--md-sys-shape-corner-large);
    padding: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  .left,
  .mid {
    overflow-y: auto;
  }
  .right {
    flex: 1;
  }
  .search {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
    margin-bottom: 8px;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .groups {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }
  .grp {
    background: none;
    border: 1px solid var(--md-sys-color-outline);
    color: var(--md-sys-color-on-surface);
    border-radius: var(--md-sys-shape-corner-medium);
    padding: 4px 12px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }
  .grp[draggable='true'] {
    cursor: grab;
  }
  .grp.drag-over {
    outline: 2px dashed var(--md-sys-color-primary);
    outline-offset: -2px;
  }
  .grp.dragging {
    opacity: 0.45;
  }
  .groups {
    user-select: none;
  }
  .grp:hover:not(.on) {
    background: var(--hover-overlay);
    border-color: var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
  }
  .grp.on {
    background: var(--md-sys-color-secondary-container);
    color: var(--md-sys-color-on-secondary-container);
    border-color: var(--md-sys-color-secondary-container);
  }
  .grp.add {
    font-weight: 600;
  }
  .conv {
    background: none;
    border: 1px solid var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
    border-radius: var(--md-sys-shape-corner-small);
    padding: 2px 10px;
    cursor: pointer;
    font-size: 11px;
    flex-shrink: 0;
    transition: background 0.15s, color 0.15s;
  }
  .conv:hover {
    background: var(--md-sys-color-primary);
    color: var(--md-sys-color-on-primary);
  }
  .ctx {
    position: fixed;
    z-index: 999;
    background: var(--md-sys-color-surface-container-high);
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    padding: 4px;
    min-width: 140px;
    max-width: 240px;
    max-height: min(70vh, 420px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .ctx-title {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    padding: 4px 8px;
  }
  .ctx button {
    background: none;
    border: none;
    text-align: left;
    padding: 6px 8px;
    cursor: pointer;
    font-size: 13px;
    color: var(--md-sys-color-on-surface);
    border-radius: 6px;
  }
  .ctx button:hover {
    background: var(--md-sys-color-primary-container);
  }
  .ctx-disconnect {
    color: var(--md-sys-color-error) !important;
  }
  .ctx-disconnect:hover {
    background: rgba(183, 28, 28, 0.12) !important;
  }
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: var(--md-sys-shape-corner-medium);
    cursor: pointer;
    transition: background 0.15s;
  }
  .item:hover {
    background: var(--md-sys-color-surface-container-high);
  }
  .item.cur {
    background: var(--md-sys-color-primary-container);
  }
  .avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    color: #fff;
    font-weight: 600;
    flex-shrink: 0;
    font-size: 18px;
  }
  img.avatar {
    object-fit: cover;
  }
  .avatar-wrap {
    position: relative;
    flex-shrink: 0;
  }
  .online-dot {
    position: absolute;
    right: -1px;
    bottom: -1px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--status-online);
    border: 2px solid var(--md-sys-color-surface-container);
  }
  .avatar.big {
    width: 64px;
    height: 64px;
    font-size: 24px;
  }
  .meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .nm {
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .uname {
    font-size: 12px;
    font-weight: 400;
    color: var(--md-sys-color-on-surface-variant);
    margin-left: 4px;
  }
  .dead-tag {
    font-size: 10px;
    color: #fff;
    background: var(--md-sys-color-error, #b3261e);
    border-radius: 4px;
    padding: 0 4px;
    margin-left: 4px;
    cursor: default;
  }
  .unk-tag {
    font-size: 10px;
    color: var(--md-sys-color-on-surface);
    background: var(--status-warning);
    border-radius: 4px;
    padding: 0 4px;
    margin-left: 4px;
    cursor: default;
  }
  .sub {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card {
    background: var(--md-sys-color-surface);
    border: 1px solid var(--divider);
    border-radius: var(--md-sys-shape-corner-large);
    margin-bottom: 8px;
    overflow: hidden;
  }
  /* flex 子项 + overflow:hidden 会把 min-height:auto 清零,
     卡片全开时被压缩穿模;禁止收缩让 .mid 正常滚动 */
  .mid > .card {
    flex: none;
  }
  .card summary {
    padding: 12px 16px;
    cursor: pointer;
    font-weight: 600;
    font-size: 15px;
    list-style: none;
    display: flex;
    align-items: center;
    transition: background 0.15s;
  }
  .card summary:hover {
    background: var(--hover-overlay);
  }
  .card summary::before {
    content: '▸';
    margin-right: 8px;
    transition: transform 0.15s;
    font-size: 12px;
  }
  .card[open] summary::before {
    content: '▾';
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 0 16px 12px;
  }
  /* 中栏过窄: 双列按钮塌成单列 */
  .mid.narrow .grid {
    grid-template-columns: 1fr;
  }
  /* 转换组: 长按钮独占一行 */
  .conv-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 0 16px 12px;
  }
  .conv-group md-filled-button,
  .conv-group md-outlined-button {
    width: 100%;
  }
  .grid md-filled-button,
  .grid md-outlined-button {
    width: 100%;
  }
  .speed-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 16px 12px;
    flex-wrap: wrap;
  }
  .speed-label {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
  }
  .speed-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    cursor: pointer;
  }
  .bi {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 16px 12px;
  }
  .bi-meta {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
  }
  .bi-name {
    font-size: 16px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bi-sub {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
  }
  .prog {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--divider);
  }
  .prog-bar {
    height: 4px;
    border-radius: 2px;
    background: var(--divider);
    overflow: hidden;
    margin: 8px 0 0;
  }
  .prog-fill {
    height: 100%;
    background: var(--md-sys-color-primary);
    border-radius: 2px;
    transition: width 0.3s;
  }
  .log {
    list-style: none;
    margin: 8px 0 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.6;
    user-select: text;
    cursor: text;
  }
  .log li {
    padding: 2px 0;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .sec-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .head-btns {
    display: inline-flex;
    gap: 6px;
    flex-shrink: 0;
  }
  /* 聊天输入行 */
  .chat-input-row {
    display: flex;
    gap: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--divider);
  }
  /* 用户名发起聊天行 */
  .start-chat-row {
    display: flex;
    gap: 8px;
    margin: 8px 0;
  }
  .chat-input {
    flex: 1;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
  }
  .chat-input:focus {
    border-color: var(--md-sys-color-primary);
  }
  .send-btn {
    padding: 8px 20px;
    border: none;
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-primary);
    color: #fff;
    font-size: 14px;
    cursor: pointer;
  }
  .send-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  /* 加群频道 */
  .join-cat {
    font-weight: 600;
    font-size: 14px;
    margin: 8px 0 4px;
  }
  .join-item-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .join-item-meta small {
    color: var(--md-sys-color-on-surface-variant);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .join-edit-row {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-bottom: 6px;
  }
  /* 加群频道页一体化 */
  .join-toolbar {
    display: flex;
    margin-bottom: 4px;
  }
  .join-item-ops {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    flex-shrink: 0;
  }
  .join-item-ops .icon-btn {
    background: none;
    border: 1px solid var(--md-sys-color-outline);
    color: var(--md-sys-color-on-surface-variant);
    width: 26px;
    height: 26px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .join-item-ops .icon-btn:hover {
    border-color: var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
  }
  .join-item-ops .icon-btn.danger:hover {
    border-color: var(--md-sys-color-error, #b3261e);
    color: var(--md-sys-color-error, #b3261e);
  }
  .join-edit-btns {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    margin-top: 6px;
  }
  .join-edit {
    flex: 1;
    min-width: 0;
  }
  /* 新建账号拖放弹窗 */
  .addacc-tabs {
    margin-bottom: 10px;
  }
  .qrlogin-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 8px 0 4px;
  }
  .qr-status {
    color: var(--md-sys-color-primary);
  }
  .addacc-drop {
    border: 2px dashed var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    padding: 26px 16px;
    text-align: center;
    color: var(--md-sys-color-on-surface-variant);
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: border-color 0.15s, background 0.15s;
  }
  .addacc-drop.over {
    border-color: var(--md-sys-color-primary);
    background: var(--hover-overlay);
  }
  .addacc-drop-icon {
    font-size: 22px;
    color: var(--md-sys-color-primary);
  }
  .addacc-drop small {
    font-size: 11px;
    opacity: 0.8;
  }
  .addacc-list {
    list-style: none;
    margin: 10px 0 0;
    padding: 0;
    max-height: 160px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .addacc-list .icon-btn {
    background: none;
    border: 1px solid var(--md-sys-color-outline);
    color: var(--md-sys-color-on-surface-variant);
    width: 24px;
    height: 24px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .set-footer-btn {
    margin-top: 14px;
  }
  /* 加群条目: 两行布局(类型+备注+删除 / 链接独占整行),避免单行挤出弹窗 */
  .join-edit {
    margin-bottom: 8px;
  }
  .join-edit .join-edit-row {
    margin-bottom: 4px;
  }
  .join-edit .join-name {
    flex: 1;
    width: auto;
  }
  .join-edit .join-link {
    width: 100%;
    box-sizing: border-box;
  }
  .join-type {
    width: 76px;
    flex-shrink: 0;
  }
  .join-name {
    width: 110px;
    flex-shrink: 0;
  }
  .join-link {
    flex: 1;
    min-width: 0;
  }
  .set-hint {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    margin: 4px 0 10px;
  }
  .bot-err {
    font-size: 12px;
    color: var(--md-sys-color-error, #b3261e);
  }
  .about-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0;
    font-size: 13px;
  }
  .about-row .set-label {
    width: 60px;
    flex-shrink: 0;
  }
  .about-ver {
    font-weight: 600;
    color: var(--md-sys-color-primary);
  }
  /* 文件夹重命名弹窗 */
  .rename-modal {
    width: 400px;
    max-width: calc(100vw - 32px);
  }
  .rename-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
  }
  .rename-x {
    font-size: 16px;
    padding: 4px 8px;
  }
  .rename-input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
  }
  .rename-input:focus {
    border-color: var(--md-sys-color-primary);
  }
  .rename-btns {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 14px;
  }
  /* 删除账号弹窗 (M3 破坏性确认) */
  .del-modal {
    width: 440px;
  }
  .del-icon {
    width: 52px;
    height: 52px;
    margin: 0 auto 12px;
    border-radius: 50%;
    background: var(--md-sys-color-error-container, #F9DEDC);
    color: var(--md-sys-color-error, #B3261E);
    display: grid;
    place-items: center;
  }
  .del-title {
    text-align: center;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .del-sub {
    text-align: center;
    font-size: 13px;
    line-height: 1.6;
    color: var(--md-sys-color-on-surface-variant);
    margin: 0 0 14px;
  }
  .del-sub b {
    color: var(--md-sys-color-error, #B3261E);
  }
  .del-row .set-label {
    flex-shrink: 0;
  }
  .del-val {
    font-weight: 600;
    color: var(--md-sys-color-on-surface);
  }
  .del-val.mono {
    font-family: Consolas, monospace;
    font-weight: 500;
  }
  .del-path {
    font-family: Consolas, monospace;
    font-size: 12px;
    color: var(--md-sys-color-error, #B3261E);
    background: color-mix(in srgb, var(--md-sys-color-error) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--md-sys-color-error) 35%, transparent);
    border-radius: 8px;
    padding: 8px 10px;
    word-break: break-all;
    margin: 0;
  }
  .del-check {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
    font-size: 13px;
    cursor: pointer;
    padding: 12px 2px;
  }
  .del-check input {
    width: 16px;
    height: 16px;
    min-width: 16px;
    margin: 0;
    padding: 0;
    accent-color: var(--md-sys-color-error, #B3261E);
    cursor: pointer;
  }
  .danger-btn {
    --md-outlined-button-color: var(--md-sys-color-error, #b3261e);
    --md-outlined-button-outline-color: var(--md-sys-color-error, #b3261e);
    --md-filled-button-container-color: #B3261E;
    --md-filled-button-label-color: #FFFFFF;
    color: var(--md-sys-color-error, #b3261e);
  }
  .del-modal md-outlined-button {
    --md-outlined-button-color: var(--md-sys-color-on-surface-variant);
    --md-outlined-button-outline-color: var(--md-sys-color-outline);
  }
  .sec-head h3 {
    margin: 0;
    font-size: 17px;
  }
  .back {
    background: none;
    border: none;
    color: var(--md-sys-color-primary);
    cursor: pointer;
    font-size: 13px;
    padding: 4px 10px;
    border-radius: var(--md-sys-shape-corner-small);
    transition: background 0.15s;
  }
  .back:hover {
    background: var(--hover-overlay);
  }
  .sec-list {
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }
  .sec-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 8px;
    border-bottom: 1px solid var(--divider);
    font-size: 14px;
  }
  .danger {
    background: none;
    border: 1px solid var(--md-sys-color-error);
    color: var(--md-sys-color-error);
    border-radius: var(--md-sys-shape-corner-medium);
    padding: 4px 14px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.15s, color 0.15s;
  }
  .danger:hover {
    background: var(--md-sys-color-error);
    color: var(--md-sys-color-on-error);
  }
  .empty {
    color: var(--md-sys-color-on-surface-variant);
    font-size: 13px;
    text-align: center;
    padding: 24px 0;
    margin: 0;
  }
  input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
    margin-bottom: 8px;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  input:focus,
  select:focus,
  textarea:focus,
  .search:focus {
    border-color: var(--md-sys-color-primary);
    box-shadow: var(--focus-ring);
  }
  .right md-filled-button,
  .right md-outlined-button {
    margin-bottom: 8px;
  }
  .form md-filled-button {
    width: 100%;
    margin-top: 8px;
  }
  .topbtn {
    background: none;
    border: 1px solid rgba(255, 255, 255, 0.4);
    color: #FFFFFF;
    border-radius: var(--md-sys-shape-corner-medium);
    padding: 5px 14px;
    cursor: pointer;
    font-size: 13px;
    margin-left: 8px;
    white-space: nowrap;
    flex-shrink: 0;
    transition: background 0.15s, border-color 0.15s;
  }
  .topbtn:hover {
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(255, 255, 255, 0.7);
  }
  .iconbtn {
    padding: 5px 10px;
    font-size: 14px;
    line-height: 1;
  }
  .conn {
    margin-right: 12px;
  }
  .edit-btn {
    margin-left: auto;
    flex-shrink: 0;
    background: none;
    border: 1px solid var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
    border-radius: var(--md-sys-shape-corner-medium);
    padding: 5px 14px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.15s, color 0.15s;
  }
  .edit-btn:hover {
    background: var(--hover-overlay);
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    flex: 1;
  }
  .form select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
    margin-bottom: 8px;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .modal-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal {
    width: 440px;
    max-width: calc(100vw - 32px);
    max-height: 86vh;
    background: var(--md-sys-color-surface-container);
    border-radius: var(--md-sys-shape-corner-large);
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
  }
  .settings-modal {
    position: relative;
    width: 680px;
    height: 540px;
    max-height: 86vh;
    padding: 0;
    flex-direction: row;
    border-radius: 28px;
    overflow: hidden;
  }
  .set-nav {
    width: 170px;
    flex-shrink: 0;
    padding: 14px 10px;
    border-right: 1px solid var(--divider);
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .set-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0 8px 12px;
  }
  .set-nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    height: 48px;
    padding: 0 16px;
    border: none;
    background: none;
    cursor: pointer;
    border-radius: 999px;
    font-size: 13px;
    font-family: inherit;
    color: var(--md-sys-color-on-surface);
    text-align: left;
    width: 100%;
    transition: background 0.15s;
  }
  .set-nav-item:hover:not(.on) {
    background: var(--state-layer);
  }
  .set-nav-item.on {
    background: var(--md-sys-color-secondary-container);
    color: var(--md-sys-color-on-secondary-container);
    font-weight: 500;
  }
  .set-nav-icon {
    font-size: 16px;
    width: 22px;
    text-align: center;
    flex-shrink: 0;
  }
  .set-content {
    flex: 1;
    min-width: 0;
    padding: 18px 22px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .set-sec-title {
    flex-shrink: 0;
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 14px;
  }
  .set-group {
    flex-shrink: 0;
    background: var(--md-sys-color-surface-container-low);
    border: 1px solid var(--divider);
    border-radius: 12px;
    margin-bottom: 16px;
    overflow: hidden;
  }
  .mode-seg {
    display: flex;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 999px;
    padding: 4px;
    gap: 6px;
  }
  .mode-item {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border: none;
    background: none;
    padding: 9px 0;
    border-radius: 999px;
    font-size: 13px;
    font-family: inherit;
    color: var(--md-sys-color-on-surface);
    cursor: pointer;
    transition: background 0.15s;
  }
  .mode-item:hover:not(.on) {
    background: var(--state-layer);
  }
  .mode-item.on {
    background: var(--md-sys-color-secondary-container);
    color: var(--md-sys-color-on-secondary-container);
    font-weight: 500;
  }
  .swatch-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    padding: 16px;
  }
  .swatch {
    position: relative;
    width: 56px;
    height: 56px;
    margin: 0 auto;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    background: linear-gradient(to bottom, var(--sw) 50%, var(--sw-light) 50%);
    transition: transform 0.15s, box-shadow 0.15s;
  }
  .swatch:hover {
    transform: scale(1.08);
  }
  .swatch.on {
    box-shadow: 0 0 0 2px var(--md-sys-color-surface-container), 0 0 0 4px var(--sw);
  }
  .swatch.on::after {
    content: '✓';
    position: absolute;
    top: -2px;
    right: -2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--sw);
    color: #ffffff;
    font-size: 11px;
    display: grid;
    place-items: center;
  }
  .swatch.custom {
    display: grid;
    place-items: center;
    background: var(--md-sys-color-surface-container-high);
    border: 1px dashed var(--md-sys-color-outline);
    font-size: 18px;
  }
  .swatch.custom.on {
    box-shadow: 0 0 0 2px var(--md-sys-color-surface-container), 0 0 0 4px var(--md-sys-color-primary);
  }
  .swatch.custom input {
    display: none;
  }
  .about-list {
    display: flex;
    flex-direction: column;
  }
  .about-list .about-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 4px;
    min-height: 40px;
  }
  .about-list .about-row + .about-row {
    border-top: 1px solid var(--divider);
  }
  .about-list .set-label {
    color: var(--md-sys-color-on-surface-variant);
  }
  .about-ver {
    font-weight: 600;
    color: var(--md-sys-color-primary);
  }
  .set-group-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--md-sys-color-on-surface-variant);
    margin: 8px 2px 8px;
  }
  .set-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 16px;
    min-height: 48px;
  }
  .set-row + .set-row {
    border-top: 1px solid var(--divider);
  }
  .set-row-col {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .set-label {
    font-size: 14px;
    color: var(--md-sys-color-on-surface);
  }
  .set-input,
  .set-select {
    width: 220px;
    flex-shrink: 0;
    padding: 8px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 8px;
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    font-family: inherit;
    outline: none;
    margin: 0;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .set-input:focus,
  .set-select:focus {
    border-color: var(--md-sys-color-primary);
    box-shadow: var(--focus-ring);
  }
  .set-color {
    width: 44px;
    height: 32px;
    padding: 2px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 8px;
    background: none;
    cursor: pointer;
    margin: 0;
    flex-shrink: 0;
  }
  .set-row-col .join-links {
    margin-bottom: 0;
  }
  .set-footer {
    flex-shrink: 0;
    margin-top: auto;
    padding-top: 12px;
    display: flex;
    justify-content: flex-end;
  }
  .set-footer md-filled-button {
    width: auto;
    min-width: 120px;
  }
  .set-close {
    position: absolute;
    top: 14px;
    right: 16px;
    width: 36px;
    height: 36px;
    padding: 0;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 14px;
  }
  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .modal-head h3 {
    margin: 0;
    font-size: 18px;
  }
  .order-btns {
    display: flex;
    gap: 4px;
  }
  .order-btn {
    width: 26px;
    height: 24px;
    border: 1px solid var(--md-sys-color-outline);
    background: none;
    color: var(--md-sys-color-on-surface);
    border-radius: var(--md-sys-shape-corner-small);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }
  .order-btn:hover:not(:disabled) {
    background: var(--hover-overlay);
    border-color: var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
  }
  .order-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .join-links.flash {
    border-color: var(--md-sys-color-primary);
    box-shadow: var(--focus-ring);
  }
  .form label {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-top: 6px;
  }
  .form textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    outline: none;
    font-family: inherit;
    resize: vertical;
    box-sizing: border-box;
    margin-bottom: 8px;
    overflow-y: auto;
    max-height: 300px;
    min-height: 43px;
    field-sizing: content;  /* 换行自动加长(Chromium 123+/WebView2) */
  }
  .row2 {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 8px;
    align-items: center;
  }
  .row2 input {
    margin-bottom: 0;
  }
  .row3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
  }
  .speed-seg {
    display: flex;
    flex: 1;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    overflow: hidden;
  }
  .seg {
    background: none;
    border: none;
    padding: 6px 0;
    cursor: pointer;
    font-size: 12px;
    color: var(--md-sys-color-on-surface);
    flex: 1;
    transition: background 0.15s, color 0.15s;
  }
  .seg:hover:not(.on) {
    background: var(--hover-overlay);
  }
  .seg + .seg {
    border-left: 1px solid var(--md-sys-color-outline);
  }
  .seg.on {
    background: var(--md-sys-color-secondary-container);
    color: var(--md-sys-color-on-secondary-container);
  }
  .ctx-check {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    cursor: pointer;
    font-size: 13px;
    color: var(--md-sys-color-on-surface);
    border-radius: 6px;
  }
  .ctx-check:hover {
    background: var(--hover-overlay);
  }
  /* 隐藏原生勾选框,用 M3 风格自绘 */
  .ctx-check-native {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }
  .ctx-check-box {
    width: 18px;
    height: 18px;
    border: 2px solid var(--md-sys-color-outline);
    border-radius: 5px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: transparent;
    flex-shrink: 0;
    transition: background 0.12s, border-color 0.12s;
  }
  .ctx-check-box.on {
    background: var(--md-sys-color-primary);
    border-color: var(--md-sys-color-primary);
    color: #fff;
  }
  .ctx-check-native:focus-visible + .ctx-check-box {
    outline: 2px solid var(--md-sys-color-primary);
    outline-offset: 2px;
  }
  .check-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-top: 6px;
    flex-wrap: wrap;
  }
  .check-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
  }
  /* 重命名弹窗快捷填充 chips */
  .rename-quick {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }
  .rename-quick-label {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
  }
  /* 已绑定邮箱展示 */
  .bound-box {
    background: var(--md-sys-color-surface);
    border: 1px solid var(--divider);
    border-radius: var(--md-sys-shape-corner-medium);
    padding: 12px 14px;
    margin-bottom: 12px;
  }
  .bound-label {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    margin-bottom: 4px;
  }
  .bound-email {
    font-size: 16px;
    font-weight: 600;
    color: var(--md-sys-color-primary);
    word-break: break-all;
  }
  .check-row input {
    width: auto;
    margin: 0;
  }
  .qr-box {
    display: flex;
    justify-content: center;
    padding: 12px 0;
  }
  .qr-img {
    width: 200px;
    height: 200px;
    border-radius: var(--md-sys-shape-corner-medium);
  }
  .qr-tip {
    margin: 8px 0 0;
    font-size: 12px;
    line-height: 1.6;
    text-align: center;
    color: var(--md-sys-color-on-surface-variant);
  }
  .qr-uri {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    margin-top: 4px;
    background: var(--md-sys-color-surface);
    border-radius: var(--md-sys-shape-corner-medium);
  }
  .qr-uri-text {
    font-size: 11px;
    font-family: 'Consolas', monospace;
    word-break: break-all;
    flex: 1;
    color: var(--md-sys-color-on-surface-variant);
  }
  input[type='color'] {
    height: 40px;
    padding: 2px;
    cursor: pointer;
  }
  /* ---------- 聊天: 消息接收 ---------- */
  .chat-ctl {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 0 16px 12px;
  }
  .chat-switch-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--divider);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface-container-low);
  }
  .chat-switch-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--md-sys-color-on-surface);
  }
  .chat-state {
    font-style: normal;
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--md-sys-color-outline);
    flex-shrink: 0;
    transition: background 0.2s;
  }
  .status-dot.on {
    background: var(--status-success);
  }
  .toggle {
    position: relative;
    width: 40px;
    height: 22px;
    flex-shrink: 0;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 999px;
    background: var(--md-sys-color-surface-variant);
    cursor: pointer;
    padding: 0;
    transition: background 0.2s, border-color 0.2s;
  }
  .toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--md-sys-color-outline);
    transition: transform 0.2s, background 0.2s;
  }
  .toggle.on {
    background: var(--md-sys-color-primary);
    border-color: var(--md-sys-color-primary);
  }
  .toggle.on .toggle-thumb {
    transform: translateX(18px);
    background: var(--md-sys-color-on-primary);
  }
  .chat-entries {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .chat-entry {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 10px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: none;
    color: var(--md-sys-color-primary);
    font-size: 13px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .chat-entry:hover {
    background: var(--hover-overlay);
    border-color: var(--md-sys-color-primary);
  }
  .badge {
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: 8px;
    background: var(--md-sys-color-error);
    color: var(--md-sys-color-on-error);
    font-size: 11px;
    line-height: 16px;
    font-weight: 500;
    flex-shrink: 0;
  }
  .recv-rules {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .rule-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: none;
    color: var(--md-sys-color-on-surface-variant);
    font-size: 12px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }
  .rule-chip:hover:not(.on) {
    border-color: var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
  }
  .rule-chip.on {
    background: var(--md-sys-color-secondary-container);
    border-color: var(--md-sys-color-secondary-container);
    color: var(--md-sys-color-on-secondary-container);
  }
  /* ---------- 会话列表 (M3 List 两行样式) ---------- */
  .dlg-list {
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .dlg {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 16px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .dlg:hover {
    background: var(--state-layer);
  }
  .dlg-ava {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    color: #ffffff;
    font-size: 16px;
    font-weight: 500;
    display: grid;
    place-items: center;
    flex-shrink: 0;
  }
  .dlg-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .dlg-row1 {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
  }
  .dlg-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--md-sys-color-on-surface);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .dlg-time {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--md-sys-color-on-surface-variant);
  }
  .dlg-row2 {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dlg-last {
    flex: 1;
    font-size: 12px;
    line-height: 1.4;
    color: var(--md-sys-color-on-surface-variant);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  /* ---------- 聊天记录 (M3 气泡: 20dp 圆角尾角 4dp) ---------- */
  .chat-history {
    list-style: none;
    margin: 8px 0 0;
    padding: 8px 4px;
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .bbl-row {
    display: flex;
  }
  .bbl-row.out {
    justify-content: flex-end;
  }
  .bbl {
    max-width: 80%;
    padding: 8px 12px;
    border-radius: 20px;
    background: var(--md-sys-color-surface-container-high);
    color: var(--md-sys-color-on-surface);
    font-size: 14px;
    overflow-wrap: break-word;
  }
  .bbl-row:not(.out) .bbl {
    border-bottom-left-radius: 4px;
  }
  .bbl-row.out .bbl {
    background: var(--md-sys-color-primary);
    color: var(--md-sys-color-on-primary);
    border-bottom-right-radius: 4px;
  }
  .bbl-sender {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--md-sys-color-primary);
    margin-bottom: 2px;
  }
  .bbl-time {
    display: inline-block;
    margin-left: 8px;
    font-size: 11px;
    opacity: 0.6;
    vertical-align: bottom;
    white-space: nowrap;
  }
  .load-older {
    display: block;
    width: 100%;
    margin-top: 8px;
    padding: 6px 0;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-small);
    background: none;
    color: var(--md-sys-color-on-surface-variant);
    font-size: 12px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }
  .load-older:hover:not(:disabled) {
    background: var(--state-layer);
    border-color: var(--md-sys-color-primary);
    color: var(--md-sys-color-primary);
  }
  .load-older:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .chat-empty {
    text-align: center;
    padding: 48px 16px;
  }
  .chat-empty-icon {
    font-size: 40px;
    display: block;
    margin-bottom: 10px;
    opacity: 0.75;
  }
  .chat-empty-title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 4px;
  }
  .chat-empty-sub {
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
    margin: 0;
  }
  label.sect {
    font-size: 14px;
    font-weight: 600;
    color: var(--md-sys-color-on-surface);
    margin-top: 12px;
  }
  .join-links {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--md-sys-color-outline);
    border-radius: var(--md-sys-shape-corner-medium);
    background: var(--md-sys-color-surface);
    color: var(--md-sys-color-on-surface);
    font-size: 13px;
    font-family: 'Consolas', monospace;
    outline: none;
    resize: vertical;
    box-sizing: border-box;
    margin-bottom: 8px;
  }
</style>
