import { useEffect, useState } from 'react';
import { api, type ConfigResp } from '../api';
import { useToast } from '../toast';

const lines = (v?: string[]) => (v || []).join('\n');
const splitLines = (v: string) => v.split('\n').map((x) => x.trim()).filter(Boolean);
const mapText = (m?: Record<string, number | string>) => Object.entries(m || {}).map(([k, v]) => `${k}=${v}`).join('\n');
function parseNumMap(text: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const raw of splitLines(text)) {
    const [k, v] = raw.split('=').map((x) => x.trim());
    const n = Number(v);
    if (!k || !Number.isFinite(n) || n <= 0) throw new Error(`Dòng không hợp lệ: ${raw}`);
    out[k] = n;
  }
  return out;
}
function parseStrMap(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of splitLines(text)) {
    const [k, ...rest] = raw.split('=');
    const v = rest.join('=').trim();
    if (!k.trim() || !v) throw new Error(`Dòng không hợp lệ: ${raw}`);
    out[k.trim()] = v;
  }
  return out;
}

export default function ConfigPage() {
  const [cfg, setCfg] = useState<ConfigResp | null>(null);
  const [form, setForm] = useState({
    api_base: '', wasm_url: '', user_agent: '', client_version: '', client_platform: '', client_locale: '',
    model_types: '', max_input_tokens: '', max_output_tokens: '', input_character_limits: '', model_aliases: '',
    tool_call_extra_starts: '', tool_call_extra_ends: '', cors_origins: '', healthcheck_on_login: false,
    init_concurrency: 2, recovery_interval: 60, acquire_timeout_ms: 30000, max_attempts: 3,
  });
  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  useEffect(() => {
    api.getConfig().then((c) => {
      setCfg(c);
      setForm({
        api_base: c.deepseek.api_base || '', wasm_url: c.deepseek.wasm_url || '',
        user_agent: c.deepseek.user_agent || '', client_version: c.deepseek.client_version || '',
        client_platform: c.deepseek.client_platform || '', client_locale: c.deepseek.client_locale || '',
        model_types: lines(c.deepseek.model_types), max_input_tokens: mapText(c.deepseek.max_input_tokens),
        max_output_tokens: mapText(c.deepseek.max_output_tokens), input_character_limits: mapText(c.deepseek.input_character_limits),
        model_aliases: mapText(c.deepseek.model_aliases), tool_call_extra_starts: lines(c.tool_call.extra_starts),
        tool_call_extra_ends: lines(c.tool_call.extra_ends), cors_origins: lines(c.server.cors_origins),
        healthcheck_on_login: c.server.healthcheck_on_login, init_concurrency: c.server.init_concurrency,
        recovery_interval: c.server.recovery_interval, acquire_timeout_ms: c.server.acquire_timeout_ms, max_attempts: c.server.max_attempts,
      });
    }).catch((e) => toast(e instanceof Error ? e.message : 'Không tải được cấu hình', 'err'));
  }, []);

  const set = (k: keyof typeof form, v: string | number | boolean) => setForm((f) => ({ ...f, [k]: v }));
  const saveAll = async () => {
    setLoading(true);
    try {
      await api.saveConfig({
        api_base: form.api_base, wasm_url: form.wasm_url, user_agent: form.user_agent,
        client_version: form.client_version, client_platform: form.client_platform, client_locale: form.client_locale,
        model_types: splitLines(form.model_types), max_input_tokens: parseNumMap(form.max_input_tokens),
        max_output_tokens: parseNumMap(form.max_output_tokens), input_character_limits: parseNumMap(form.input_character_limits),
        model_aliases: parseStrMap(form.model_aliases), tool_call_extra_starts: splitLines(form.tool_call_extra_starts),
        tool_call_extra_ends: splitLines(form.tool_call_extra_ends), cors_origins: splitLines(form.cors_origins),
        healthcheck_on_login: form.healthcheck_on_login, init_concurrency: Number(form.init_concurrency),
        recovery_interval: Number(form.recovery_interval), acquire_timeout_ms: Number(form.acquire_timeout_ms), max_attempts: Number(form.max_attempts),
      });
      toast('Đã lưu cấu hình', 'ok');
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setLoading(false); }
  };
  const changePw = async () => {
    if (newPw.length < 6) { toast('Mật khẩu mới tối thiểu 6 ký tự', 'err'); return; }
    setLoading(true);
    try { await api.saveConfig({ old_password: oldPw, new_password: newPw }); toast('Đã đổi mật khẩu', 'ok'); setOldPw(''); setNewPw(''); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setLoading(false); }
  };
  if (!cfg) return <div className="card">Đang tải cấu hình...</div>;

  return <div style={{ maxWidth: 980 }}>
    <div className="card mb-24"><div className="card-title">Configuration giống DS Free API</div>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 14 }}>Các giá trị tương ứng deepseek, tool_call và server trong config.toml của DS Free API.</p>
      <div className="grid-2">
        <div className="field"><label>DeepSeek API Base</label><input className="input" value={form.api_base} onChange={(e) => set('api_base', e.target.value)} /></div>
        <div className="field"><label>WASM URL</label><input className="input" value={form.wasm_url} onChange={(e) => set('wasm_url', e.target.value)} /></div>
        <div className="field"><label>User Agent</label><input className="input" value={form.user_agent} onChange={(e) => set('user_agent', e.target.value)} /></div>
        <div className="field"><label>Client Version</label><input className="input" value={form.client_version} onChange={(e) => set('client_version', e.target.value)} /></div>
        <div className="field"><label>Client Platform</label><input className="input" value={form.client_platform} onChange={(e) => set('client_platform', e.target.value)} /></div>
        <div className="field"><label>Client Locale</label><input className="input" value={form.client_locale} onChange={(e) => set('client_locale', e.target.value)} /></div>
      </div>
      <div className="grid-2">
        <div className="field"><label>Model Types, mỗi dòng 1 model_type</label><textarea className="input" rows={4} value={form.model_types} onChange={(e) => set('model_types', e.target.value)} /></div>
        <div className="field"><label>Model Aliases, dạng alias=model_type</label><textarea className="input" rows={4} value={form.model_aliases} onChange={(e) => set('model_aliases', e.target.value)} placeholder="deepseek-chat=default" /></div>
        <div className="field"><label>Max Input Tokens, dạng model=value</label><textarea className="input" rows={4} value={form.max_input_tokens} onChange={(e) => set('max_input_tokens', e.target.value)} /></div>
        <div className="field"><label>Max Output Tokens, dạng model=value</label><textarea className="input" rows={4} value={form.max_output_tokens} onChange={(e) => set('max_output_tokens', e.target.value)} /></div>
        <div className="field"><label>Input Character Limits, dạng model=value</label><textarea className="input" rows={4} value={form.input_character_limits} onChange={(e) => set('input_character_limits', e.target.value)} /></div>
      </div>
      <button className="btn btn-primary" onClick={saveAll} disabled={loading}>Lưu cấu hình</button>
    </div>
    <div className="card mb-24"><div className="card-title">Tool Call & Server</div>
      <div className="grid-2">
        <div className="field"><label>Tool Call Extra Starts</label><textarea className="input" rows={4} value={form.tool_call_extra_starts} onChange={(e) => set('tool_call_extra_starts', e.target.value)} /></div>
        <div className="field"><label>Tool Call Extra Ends</label><textarea className="input" rows={4} value={form.tool_call_extra_ends} onChange={(e) => set('tool_call_extra_ends', e.target.value)} /></div>
        <div className="field"><label>CORS Origins</label><textarea className="input" rows={3} value={form.cors_origins} onChange={(e) => set('cors_origins', e.target.value)} /></div>
        <div className="field"><label>Init Concurrency</label><input className="input" type="number" value={form.init_concurrency} onChange={(e) => set('init_concurrency', Number(e.target.value))} /></div>
        <div className="field"><label>Recovery Interval giây</label><input className="input" type="number" value={form.recovery_interval} onChange={(e) => set('recovery_interval', Number(e.target.value))} /></div>
        <div className="field"><label>Acquire Timeout ms</label><input className="input" type="number" value={form.acquire_timeout_ms} onChange={(e) => set('acquire_timeout_ms', Number(e.target.value))} /></div>
        <div className="field"><label>Max Attempts</label><input className="input" type="number" value={form.max_attempts} onChange={(e) => set('max_attempts', Number(e.target.value))} /></div>
        <label className="checkline"><input type="checkbox" checked={form.healthcheck_on_login} onChange={(e) => set('healthcheck_on_login', e.target.checked)} /> Health check bằng chat thật khi login/recovery</label>
      </div>
      <button className="btn btn-primary" onClick={saveAll} disabled={loading}>Lưu server/tool call</button>
    </div>
    <div className="card"><div className="card-title">Đổi mật khẩu quản trị</div>
      <div className="field"><label>Mật khẩu hiện tại</label><input className="input" type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} /></div>
      <div className="field"><label>Mật khẩu mới</label><input className="input" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} /></div>
      <button className="btn btn-primary" onClick={changePw} disabled={loading}>Đổi mật khẩu</button>
    </div>
  </div>;
}
