import { useEffect, useState } from 'react';
import { api, type ApiKey } from '../api';
import { useToast } from '../toast';
import { IconPlus, IconTrash, IconCopy } from '../icons';

function getToken() { return localStorage.getItem('mds_token') || ''; }
function fmtNum(n: number): string { return (n || 0).toLocaleString('vi-VN'); }
function fmtTime(ts?: number): string {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const mo = String(d.getMonth() + 1).padStart(2, '0');
  return `${hh}:${mm} · ${dd}/${mo}`;
}
function successRate(k: ApiKey): number {
  const total = k.request_count || 0;
  if (!total) return 0;
  return Math.round(((k.success_count || 0) / total) * 1000) / 10;
}
function shortProxy(url: string, proxyMap: Record<string, string>): string {
  if (!url) return 'direct';
  const key = url.trim().replace(/\/$/, '');
  if (proxyMap[key]) return proxyMap[key];
  try {
    const u = new URL(url);
    const h = u.hostname.replace('.workers.dev', '');
    return h.length > 16 ? h.slice(0, 16) + '…' : h;
  } catch { return url.slice(0, 16); }
}

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [proxyMap, setProxyMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [desc, setDesc] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [newKey, setNewKey] = useState('');
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
    try { setKeys(await api.keys()); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadProxies(); load(); }, []);

  const create = async () => {
    try {
      const r = await api.addKey(desc);
      setNewKey(r.key);
      setDesc('');
      load();
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi tạo key', 'err'); }
  };
  const del = async (id: number) => {
    if (!confirm('Xóa API key này? Ứng dụng dùng key sẽ ngừng hoạt động.')) return;
    try { await api.delKey(id); toast('Đã xóa key', 'ok'); load(); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
  };
  const copy = (k: string) => {
    navigator.clipboard.writeText(k);
    toast('Đã sao chép', 'ok');
  };

  return (
    <div>
      <div className="spread mb-20">
        <p style={{ color: 'var(--text-dim)' }}>
          API key để ứng dụng ngoài gọi vào gateway theo chuẩn OpenAI. Bảng này có thống kê usage theo từng key.
        </p>
        <button className="btn btn-primary" onClick={() => { setNewKey(''); setShowModal(true); }}>
          <IconPlus width={16} height={16} /> Tạo API Key
        </button>
      </div>

      {loading ? (
        <div className="loading-full"><div className="spinner" /></div>
      ) : keys.length === 0 ? (
        <div className="card"><div className="empty">Chưa có API key nào.</div></div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>API Key</th>
                <th>Mô tả</th>
                <th>Requests</th>
                <th>Tokens</th>
                <th>Success</th>
                <th>Avg latency</th>
                <th>Last used</th>
                <th>Proxy cuối</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td>
                    <div className="row">
                      <span className="code-pill">{k.key.slice(0, 12)}...{k.key.slice(-4)}</span>
                      <button className="btn btn-sm" onClick={() => copy(k.key)}><IconCopy width={13} height={13} /></button>
                    </div>
                  </td>
                  <td>{k.description || '—'}</td>
                  <td style={{ fontWeight: 600 }}>{fmtNum(k.request_count || 0)}</td>
                  <td title={`Prompt: ${fmtNum(k.prompt_tokens_used || 0)} · Completion: ${fmtNum(k.completion_tokens_used || 0)}`}>
                    {fmtNum(k.total_tokens || 0)}
                  </td>
                  <td>
                    {(k.request_count || 0) > 0
                      ? <span className={`badge ${successRate(k) >= 90 ? 'ok' : successRate(k) >= 70 ? 'busy' : 'fail'}`}>{successRate(k)}%</span>
                      : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                  </td>
                  <td>{k.avg_latency_ms ? `${fmtNum(k.avg_latency_ms)} ms` : '—'}</td>
                  <td style={{ whiteSpace: 'nowrap', color: 'var(--text-dim)' }}>{fmtTime(k.last_used_at)}</td>
                  <td style={{ whiteSpace: 'nowrap', color: 'var(--text-dim)' }} title={k.last_proxy_url || 'direct'}>
                    {k.last_proxy_name || shortProxy(k.last_proxy_url || '', proxyMap)}
                  </td>
                  <td><span className={`badge ${k.is_active ? 'ok' : 'fail'}`}>{k.is_active ? 'Hoạt động' : 'Tắt'}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-sm btn-danger" onClick={() => del(k.id)}><IconTrash width={14} height={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Tạo API Key mới</h3>
            {newKey ? (
              <div>
                <p style={{ color: 'var(--text-dim)', marginBottom: 12 }}>
                  Sao chép key ngay, key chỉ hiển thị đầy đủ một lần.
                </p>
                <div className="row" style={{ background: 'var(--bg-soft)', padding: 12, borderRadius: 8 }}>
                  <code style={{ flex: 1, wordBreak: 'break-all', fontSize: 13 }}>{newKey}</code>
                  <button className="btn btn-sm btn-primary" onClick={() => copy(newKey)}><IconCopy width={14} height={14} /> Sao chép</button>
                </div>
                <div className="modal-actions">
                  <button className="btn btn-primary" onClick={() => setShowModal(false)}>Xong</button>
                </div>
              </div>
            ) : (
              <div>
                <div className="field">
                  <label>Mô tả (tùy chọn)</label>
                  <input className="input" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="VD: App chatbot" autoFocus />
                </div>
                <div className="modal-actions">
                  <button className="btn" onClick={() => setShowModal(false)}>Hủy</button>
                  <button className="btn btn-primary" onClick={create}>Tạo</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
