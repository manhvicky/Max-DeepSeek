const TOKEN_KEY = 'mds_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

const BASE = '/admin/api';

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    if (!path.includes('/login') && !path.includes('/setup')) {
      window.location.href = '/admin/login';
    }
  }

  const text = await res.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }

  if (!res.ok) {
    const detail = (data && typeof data === 'object' && 'detail' in data)
      ? (data as { detail: string }).detail : `Lỗi ${res.status}`;
    throw new Error(typeof detail === 'string' ? detail : `Lỗi ${res.status}`);
  }
  return data as T;
}

export const api = {
  // auth
  login: (password: string) => req<{ token: string }>('POST', '/login', { password }),
  setup: (password: string) => req<{ token: string }>('POST', '/setup', { password }),
  // status & stats
  status: () => req<StatusResp>('GET', '/status'),
  stats: () => req<StatsResp>('GET', '/stats'),
  // accounts
  accounts: () => req<Account[]>('GET', '/accounts'),
  addAccount: (a: AccountInput) => req<{ id: number }>('POST', '/accounts', a),
  delAccount: (id: number) => req<{ ok: boolean }>('DELETE', `/accounts/${id}`),
  reloginAccount: (id: number) => req<{ ok: boolean }>('POST', `/accounts/${id}/relogin`),
  testAccount: (id: number) => req<{ ok: boolean; latency_ms?: number; reply?: string; error?: string }>('POST', `/accounts/${id}/test`),
  enableAccount: (id: number, enabled: boolean) => req<{ ok: boolean; enabled: boolean }>('POST', `/accounts/${id}/enable`, { enabled }),
  disableBusyAccounts: () => req<{ ok: boolean; count: number; ids: number[] }>('POST', '/accounts/disable-busy'),
  disableBlockedAccounts: () => req<{ ok: boolean; count: number; ids: number[] }>('POST', '/accounts/disable-blocked'),
  // keys
  keys: () => req<ApiKey[]>('GET', '/keys'),
  addKey: (description: string) => req<{ id: number; key: string }>('POST', '/keys', { description }),
  delKey: (id: number) => req<{ ok: boolean }>('DELETE', `/keys/${id}`),
  // logs
  logs: (limit = 100) => req<LogEntry[]>('GET', `/logs?limit=${limit}`),
  // config
  getConfig: () => req<ConfigResp>('GET', '/config'),
  saveConfig: (c: ConfigInput) => req<{ ok: boolean }>('POST', '/config', c),
  models: () => req<{ data: { id: string }[] }>('GET', '/models'),
};

// ── Types ─────────────────────────────────────────
export interface StatusResp {
  total: number; idle: number; busy: number; error: number; invalid: number;
  cooling?: number; enabled?: number; disabled?: number; quarantined?: number; next_ready_in?: number; health?: string;
  uptime_secs: number;
  accounts: { email: string; mobile: string; state: string; last_error: string; cooldown_remaining?: number; quarantine_remaining?: number; enabled?: boolean }[];
}
export interface StatsResp {
  total_requests: number; success_requests: number; failed_requests: number;
  total_prompt_tokens: number; total_completion_tokens: number;
  avg_latency_ms: number; uptime_secs: number;
}
export interface Account {
  id: number; email: string; mobile: string; area_code: string;
  label: string; state: string; error_count: number; last_error: string;
  cooldown_remaining?: number;
  request_count?: number;
  enabled?: boolean;
}
export interface AccountInput {
  email?: string; mobile?: string; area_code?: string; password: string; label?: string;
}
export interface ApiKey {
  id: number; key: string; description: string; is_active: boolean;
  created_at?: number;
  request_count?: number;
  total_tokens?: number;
  prompt_tokens_used?: number;
  completion_tokens_used?: number;
  success_count?: number;
  avg_latency_ms?: number;
  last_used_at?: number;
  last_proxy_url?: string;
  last_proxy_name?: string;
}
export interface LogEntry {
  timestamp: number; model: string; api_key: string;
  key_description: string; account_label: string;
  prompt_tokens: number; completion_tokens: number;
  latency_ms: number; success: boolean; error: string;
  proxy_url: string;
  proxy_name?: string;
}
export interface ConfigResp {
  deepseek: {
    api_base: string; wasm_url: string; user_agent: string; client_version: string;
    client_platform: string; client_locale: string; model_types: string[];
    max_input_tokens: Record<string, number>; max_output_tokens: Record<string, number>;
    input_character_limits: Record<string, number>; model_aliases: Record<string, string>;
  };
  tool_call: { extra_starts: string[]; extra_ends: string[] };
  server: {
    host: string; port: number; cors_origins: string[]; healthcheck_on_login: boolean;
    init_concurrency: number; recovery_interval: number; acquire_timeout_ms: number; max_attempts: number; min_account_interval_ms: number;
  };
  proxy_url: string; model_aliases: Record<string, string>; password_set: boolean;
}
export interface ConfigInput {
  proxy_url?: string; old_password?: string; new_password?: string;
  api_base?: string; wasm_url?: string; user_agent?: string; client_version?: string;
  client_platform?: string; client_locale?: string; model_types?: string[];
  max_input_tokens?: Record<string, number>; max_output_tokens?: Record<string, number>;
  input_character_limits?: Record<string, number>; model_aliases?: Record<string, string>;
  tool_call_extra_starts?: string[]; tool_call_extra_ends?: string[]; cors_origins?: string[];
  healthcheck_on_login?: boolean; init_concurrency?: number; recovery_interval?: number;
  acquire_timeout_ms?: number; max_attempts?: number; min_account_interval_ms?: number;
}
