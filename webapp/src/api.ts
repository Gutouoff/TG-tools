export interface Account {
  name: string;
  path: string;
  state: string;
  phone: string;
  username: string;
  uid: string;
  display: string;
  avatar: string;
  country: string;
}

export interface LogEvent {
  type: 'log' | 'progress' | 'state' | 'avatars_done';
  line?: string;
  done?: number;
  total?: number;
  label?: string;
  status?: string;
  data?: unknown;
}

// 本地 API 鉴权 token（优先 url query,其次后端注入到 index.html 的 window.__TG_TOKEN__）
export const TOKEN =
  new URLSearchParams(location.search).get('token') ||
  (typeof window !== 'undefined' ? (window as any).__TG_TOKEN__ : '') ||
  '';

async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (TOKEN) headers.set('X-TG-Token', TOKEN);
  return fetch(url, { ...init, headers });
}

function jsonHeaders(extra?: Record<string, string>): Headers {
  const h = new Headers(extra);
  h.set('Content-Type', 'application/json');
  if (TOKEN) h.set('X-TG-Token', TOKEN);
  return h;
}

export async function getAccounts(): Promise<Account[]> {
  const r = await apiFetch('/api/accounts');
  return r.json();
}

export async function connectAccount(path: string) {
  const r = await apiFetch('/api/connect', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ path }),
  });
  return r.json();
}

export async function disconnect(name?: string) {
  const r = await apiFetch('/api/disconnect', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(name ? { name } : {}),
  });
  return r.json();
}

export async function switchAccount(name: string) {
  const r = await apiFetch('/api/switch', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ name }),
  });
  return r.json();
}

export async function getOnline() {
  const r = await apiFetch('/api/online');
  return r.json() as Promise<{ ok: boolean; online: Array<{ name: string }> }>;
}

export async function postTask(url: string, body?: object) {
  const r = await apiFetch(url, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(body ?? {}),
  });
  return r.json();
}

export function connectWS(onMessage: (e: LogEvent) => void): WebSocket {
  const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${wsScheme}://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {}
  };
  return ws;
}

export async function setSpeed(speed: number) {
  await apiFetch('/api/speed', {
    method: 'PUT',
    headers: jsonHeaders(),
    body: JSON.stringify({ speed }),
  });
}

export async function updateTelegram() {
  return postTask('/api/update-telegram');
}

export async function getWhitelist(): Promise<{ users: number[]; groups: number[] }> {
  const r = await apiFetch('/api/whitelist');
  return r.json();
}

async function whitelistWrite(url: string, id: number) {
  const r = await apiFetch(url, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ id }),
  });
  return r.json();
}

export const addWhitelistUser = (id: number) => whitelistWrite('/api/whitelist/user', id);
export const addWhitelistGroup = (id: number) => whitelistWrite('/api/whitelist/group', id);

async function whitelistDelete(url: string, id: number) {
  const r = await apiFetch(url, {
    method: 'DELETE',
    headers: jsonHeaders(),
    body: JSON.stringify({ id }),
  });
  return r.json();
}
export const removeWhitelistUser = (id: number) => whitelistDelete('/api/whitelist/user', id);
export const removeWhitelistGroup = (id: number) => whitelistDelete('/api/whitelist/group', id);

// ---------- 安全功能 ----------
async function getJson(url: string) {
  const r = await apiFetch(url);
  return r.json();
}
async function postJson(url: string, body: object = {}) {
  const r = await apiFetch(url, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  return r.json();
}

export const getPing = () => getJson('/api/ping');

export const getPasskeys = () => getJson('/api/passkeys');
export const deletePasskey = (id: string) => postJson('/api/passkeys/delete', { id });
export const initPasskey = () => postJson('/api/passkeys/init');
export const registerPasskey = (cred: {
  id: string;
  raw_id: string;
  client_data: string;
  attestation: string;
}) => postJson('/api/passkeys/register', cred);

export const get2FA = () => getJson('/api/2fa');
export const set2FA = (current: string, newPwd: string) => postJson('/api/2fa/set', { current, new: newPwd });

export const sendEmailCode = (email: string) => postJson('/api/email/send', { email });
export const verifyEmailCode = (code: string) => postJson('/api/email/verify', { code });

export const getDevices = () => getJson('/api/devices');
export const deleteDevice = (hash: number) => postJson('/api/devices/delete', { hash });

// ---------- 资料编辑 ----------
export const getProfile = () => getJson('/api/profile');
export const updateProfile = (first_name: string, last_name: string, about: string) =>
  postJson('/api/profile/update', { first_name, last_name, about });
export const updateUsername = (username: string) => postJson('/api/profile/username', { username });
export const updateBirthday = (day: number, month: number, year: number | null) =>
  postJson('/api/profile/birthday', { day, month, year });
export const uploadAvatar = (data: string) => postJson('/api/avatar', { data });

// ---------- 账号分组 ----------
export const getGroups = (): Promise<Record<string, string[]>> => getJson('/api/groups');
export const createGroup = (name: string) => postJson('/api/groups', { name });
export const deleteGroup = (name: string) =>
  apiFetch(`/api/groups/${encodeURIComponent(name)}`, { method: 'DELETE' }).then((r) => r.json());
export const moveAccount = (name: string, group: string) => postJson('/api/groups/move', { name, group });

// ---------- 聊天: 消息接收 / 加群频道 ----------
export interface RecvState { on: boolean; rules: Record<string, boolean>; }
export const getRecv = (): Promise<RecvState> => getJson('/api/recv');
export const setRecv = (on: boolean, rules?: Record<string, boolean>) =>
  postJson('/api/recv', { on, rules });
export const joinChats = (links: string[]) => postJson('/api/join-channels', { links });

export interface DialogItem {
  id: number; name: string; type: 'private' | 'group' | 'channel';
  unread: number; pinned: boolean; last_text: string; last_date: string;
}
export interface HistoryMsg {
  id: number; out: boolean; sender: string; sender_id: number | null;
  sender_username: string | null; text: string; date: string;
}
export const getDialogs = (account: string): Promise<{ ok: boolean; dialogs?: DialogItem[]; msg?: string }> =>
  getJson(`/api/dialogs?account=${encodeURIComponent(account)}`);
export const getHistory = (
  account: string, dialogId: number, limit = 20, offsetId = 0,
): Promise<{ ok: boolean; msgs?: HistoryMsg[]; msg?: string }> =>
  postJson('/api/history', { account, dialog_id: dialogId, limit, offset_id: offsetId });

// ---------- tdata 转换 / 导入 ----------
export const convertTdata = (path: string) => postJson('/api/convert-tdata', { path });
export const importArchive = (data: string, name: string) => postJson('/api/import', { data, name });

// ---------- 打包 / 设置 / 我 ----------
export const packAccount = (path: string, name: string) => postJson('/api/pack', { path, name });
export const fetchAvatars = () => postJson('/api/fetch-avatars');
export const refreshAvatar = (name: string) => postJson('/api/refresh-avatar', { name });
export const getSettings = () => getJson('/api/settings');
export const saveSettings = (s: object) => postJson('/api/settings', s);
export const getMe = () => getJson('/api/me');

// ---------- 启动客户端 / 发送消息 ----------
export async function launchClient(path: string) {
  const r = await apiFetch('/api/launch-client', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ path }),
  });
  return r.json() as Promise<{ ok: boolean; msg?: string }>;
}

export async function renameAccount(path: string, newName: string) {
  const r = await apiFetch('/api/rename-account', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ path, new_name: newName }),
  });
  return r.json() as Promise<{ ok: boolean; msg?: string; new_path?: string }>;
}

export const pollAccounts = () => postJson('/api/poll-accounts');

export async function deleteAccount(path: string) {
  const r = await apiFetch('/api/delete-account', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ path }),
  });
  return r.json() as Promise<{ ok: boolean; msg?: string; deleted_path?: string }>;
}

export async function sendChatMsg(account: string, dialogId: number, text: string) {
  const r = await apiFetch('/api/chat/send', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ account, dialog_id: dialogId, text }),
  });
  return r.json() as Promise<{ ok: boolean; msg?: HistoryMsg; } | { ok: boolean; msg: string }>;
}
