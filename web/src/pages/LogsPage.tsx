import { useEffect, useState } from 'react';
import { api, type LogEntry } from '../api';
import { useToast } from '../toast';
import { IconActivity, IconCheck, IconClock, IconRefresh, IconZap } from '../icons';

function getToken() { return localStorage.getItem('mds_token') || ''; }

function fmtProxy(url: string, proxyMap: Record<string, string>): string {
  if (!url) return 'direct';
  // Map URL → tên từ proxy pool
  const name = proxyMap[url.trim().replace(/\/$/, '')];
  if (name) return name;
  // Fallback: rút gọn URL
  try {
    const u = new URL(url);
    const host = u.hostname.replace('.workers.dev', '').replace('.cloudflare.com', '');
    return host.length > 20 ? host.slice(0, 20) + '…' : host;
  } catch {
    return url.slice(0, 20);
  }
}

function fmtNum(n: number): string { return (n || 0).toLocaleString('vi-VN'); }

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  return `${hh}:${mm}:${ss} — ${dd}/${mo}`;
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [proxyMap, setProxyMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const loadProxies = async () => {
    try {
      const r = await fetch('/admin/api/proxies', { headers: { Authorization: `Bearer ${getToken()}` } });
      if (r.ok) {
        const list = await r.json();
        const map: Record<string, string> = {};
        for (const p of list) map[p.url.trim().replace(/\/$/, '')] = p.name;
        setProxyMap(map);
      }
    } catch { /* ignore */ }
  };

  const load = async () => {
    try { setLogs(await api.logs(150)); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    loadProxies();
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const totalRequests = logs.length;
  const successCount = logs.filter(l => l.success).length;
  const failedCount = totalRequests - successCount;
  const totalTokens = logs.reduce((sum, l) => sum + l.prompt_tokens + l.completion_tokens, 0);
  const avgLatency = totalRequests ? Math.round(logs.reduce((sum, l) => sum + l.latency_ms, 0) / totalRequests) : 0;
  const successRate = totalRequests ? ((successCount / totalRequests) * 100).toFixed(1) : '100';
  const proxyCount = logs.filter(l => l.proxy_url).length;
  const directCount = totalRequests - proxyCount;
  const uniqueKeys = new Set(logs.map(l => l.key_description || l.api_key || '—')).size;

  return (
    <div>
      <div className="spread mb-20">
        <p style={{ color: 'var(--text-dim)' }}>150 yêu cầu gần nhất.</p>
        <button className="btn" onClick={load}><IconRefresh width={15} height={15} /> Làm mới</button>
      </div>
      {!loading && logs.length > 0 && (
        <div className="stat-grid mb-24">
          <div className="stat-card">
            <div className="icon-box"><IconActivity width={18} height={18} /></div>
            <div className="label">Yêu cầu gần nhất</div>
            <div className="value">{fmtNum(totalRequests)}</div>
            <div className="hint">{fmtNum(failedCount)} thất bại · {fmtNum(uniqueKeys)} API key</div>
          </div>
          <div className="stat-card">
            <div className="icon-box"><IconCheck width={18} height={18} /></div>
            <div className="label">Tỷ lệ thành công</div>
            <div className="value">{successRate}%</div>
            <div className="hint">{fmtNum(successCount)} thành công</div>
          </div>
          <div className="stat-card">
            <div className="icon-box"><IconZap width={18} height={18} /></div>
            <div className="label">Tokens trong log</div>
            <div className="value">{fmtNum(totalTokens)}</div>
            <div className="hint">Prompt + completion</div>
          </div>
          <div className="stat-card">
            <div className="icon-box"><IconClock width={18} height={18} /></div>
            <div className="label">Độ trễ TB</div>
            <div className="value">{fmtNum(avgLatency)}<span style={{ fontSize: 15, color: 'var(--text-muted)' }}> ms</span></div>
            <div className="hint">Proxy: {fmtNum(proxyCount)} · Direct: {fmtNum(directCount)}</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-full"><div className="spinner" /></div>
      ) : logs.length === 0 ? (
        <div className="card"><div className="empty">Chưa có yêu cầu nào.</div></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Thời gian</th><th>Mô hình</th><th>API Key</th><th>Tài khoản</th><th>Tokens</th><th>Độ trễ</th><th>Proxy</th><th>Trạng thái</th></tr>
            </thead>
            <tbody>
              {logs.map((l, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{fmtTime(l.timestamp)}</td>
                  <td><span className="code-pill">{l.model}</span></td>
                  <td style={{ color: 'var(--text-muted)' }}>{l.key_description || '—'}</td>
                  <td style={{ color: 'var(--text-dim)' }}>{l.account_label || '—'}</td>
                  <td>{l.prompt_tokens + l.completion_tokens}</td>
                  <td>{l.latency_ms} ms</td>
                  <td style={{ color: 'var(--text-dim)', fontSize: '0.8em', whiteSpace: 'nowrap' }} title={l.proxy_url || 'direct'}>
                    {l.proxy_name || fmtProxy(l.proxy_url, proxyMap)}
                  </td>
                  <td>
                    {l.success
                      ? <span className="badge ok">Thành công</span>
                      : <span className="badge fail" title={l.error}>Thất bại</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
