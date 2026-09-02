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
