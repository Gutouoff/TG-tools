export interface Account {
  name: string;
  path: string;
  state: string;
  phone: string;
  username: string;
  uid: string;
  display: string;
  avatar: string;
}

export interface LogEvent {
  type: 'log' | 'progress' | 'state';
  line?: string;
  done?: number;
  total?: number;
  label?: string;
  status?: string;
  data?: unknown;
}

export async function getAccounts(): Promise<Account[]> {
  const r = await fetch('/api/accounts');
  return r.json();
}

export async function connectAccount(path: string) {
  const r = await fetch('/api/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  return r.json();
}

export async function disconnect() {
  const r = await fetch('/api/disconnect', { method: 'POST' });
  return r.json();
}

export async function postTask(url: string, body?: object) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  return r.json();
}

export function connectWS(onMessage: (e: LogEvent) => void): WebSocket {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {}
  };
  return ws;
}

export async function setSpeed(speed: number) {
  await fetch('/api/speed', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speed }),
  });
}

export async function updateTelegram() {
  return postTask('/api/update-telegram');
}

export async function getWhitelist(): Promise<{ users: number[]; groups: number[] }> {
  const r = await fetch('/api/whitelist');
  return r.json();
}

async function whitelistWrite(url: string, id: number) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });
  return r.json();
}

export const addWhitelistUser = (id: number) => whitelistWrite('/api/whitelist/user', id);
export const addWhitelistGroup = (id: number) => whitelistWrite('/api/whitelist/group', id);

async function whitelistDelete(url: string, id: number) {
  const r = await fetch(url, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });
  return r.json();
}
export const removeWhitelistUser = (id: number) => whitelistDelete('/api/whitelist/user', id);
export const removeWhitelistGroup = (id: number) => whitelistDelete('/api/whitelist/group', id);

// ---------- 安全功能 ----------
async function getJson(url: string) {
  const r = await fetch(url);
  return r.json();
}
async function postJson(url: string, body: object = {}) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

export const getPasskeys = () => getJson('/api/passkeys');
export const deletePasskey = (id: string) => postJson('/api/passkeys/delete', { id });
export const initPasskey = () => postJson('/api/passkeys/init');

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
