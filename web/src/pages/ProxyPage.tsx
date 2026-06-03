import { useEffect, useState } from 'react';
import { useToast } from '../toast';

interface ProxyItem {
  id: number;
  name: string;
  url: string;
  enabled: boolean;
  is_active: boolean;
  created_at: number;
  usage_today: number;
  usage_limit: number;
}
interface ProxyInfo {
  url: string;
  default: string;
  is_custom: boolean;
  source: string;
}
interface TestResult {
  ok: boolean;
  status?: number;
  latency_ms?: number;
  error?: string;
}
interface UsageToday {
  date: string;
  url_key: string;
  hits: number;
  limit: number;
  remaining: number;
  percent_used: number;
}
interface UsageHistory {
  date: string;
  hits: number;
  limit: number;
  remaining: number;
  percent_used: number;
}
interface UsageResp {
  url_key: string;
  today: UsageToday;
  history: UsageHistory[];
  is_custom_proxy: boolean;
}

function getToken() {
  return localStorage.getItem('mds_token') || '';
}
function authHeader() {
  return { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' };
}
function fmtNum(n: number): string {
  return n.toLocaleString('vi-VN');
}
function fmtDate(d: string): string {
  const parts = d.split('-');
  return `${parts[2]}/${parts[1]}`;
}
function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname.replace('.workers.dev', '').replace('.cloudflare.com', '');
  } catch { return url.slice(0, 30); }
}

function UsageBar({ percent, hits, limit }: { percent: number; hits: number; limit: number }) {
  const color = percent >= 90 ? 'var(--red)' : percent >= 70 ? 'var(--yellow)' : 'var(--green)';
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13 }}>
        <span style={{ color: 'var(--text-dim)' }}>
          <span style={{ fontWeight: 700, color }}>{fmtNum(hits)}</span>
          <span style={{ color: 'var(--text-muted)' }}> / {fmtNum(limit)} request</span>
        </span>
        <span style={{ fontWeight: 700, color }}>{percent}%</span>
      </div>
      <div style={{ height: 8, background: 'var(--bg-soft)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(percent, 100)}%`, background: color, borderRadius: 99, transition: 'width 0.4s ease' }} />
      </div>
      <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
        Còn lại: <span style={{ color: 'var(--text)', fontWeight: 600 }}>{fmtNum(limit - hits)}</span> request hôm nay
      </div>
    </div>
  );
}

export default function ProxyPage() {
  const [proxies, setProxies] = useState<ProxyItem[]>([]);
  const [info, setInfo] = useState<ProxyInfo | null>(null);
  const [usage, setUsage] = useState<UsageResp | null>(null);
  const [testResults, setTestResults] = useState<Record<number, TestResult>>({});
  const [testing, setTesting] = useState<Record<number, boolean>>({});
  const [activating, setActivating] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  // form thêm mới
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');
  const [newUrl, setNewUrl] = useState('');
  const [adding, setAdding] = useState(false);
  // edit inline
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editUrl, setEditUrl] = useState('');
  const [saving, setSaving] = useState(false);

  const toast = useToast();

  const load = async () => {
    try {
      const [r1, r2, r3] = await Promise.all([
        fetch('/admin/api/proxies', { headers: authHeader() }),
        fetch('/admin/api/proxy', { headers: authHeader() }),
        fetch('/admin/api/proxy/usage', { headers: authHeader() }),
      ]);
      if (r1.ok) setProxies(await r1.json());
      if (r2.ok) setInfo(await r2.json());
      if (r3.ok) setUsage(await r3.json());
    } catch { toast('Lỗi tải dữ liệu', 'err'); }
  };

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  const addProxy = async () => {
    if (!newName.trim()) { toast('Nhập tên proxy', 'err'); return; }
    if (!newUrl.trim()) { toast('Nhập URL proxy', 'err'); return; }
    setAdding(true);
    try {
      const r = await fetch('/admin/api/proxies', {
        method: 'POST', headers: authHeader(),
        body: JSON.stringify({ name: newName.trim(), url: newUrl.trim() }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Lỗi thêm');
      toast('Đã thêm proxy', 'ok');
      setNewName(''); setNewUrl(''); setShowAdd(false);
      load();
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setAdding(false); }
  };

  const deleteProxy = async (id: number) => {
    setDeleting(id);
    try {
      await fetch(`/admin/api/proxies/${id}`, { method: 'DELETE', headers: authHeader() });
      toast('Đã xóa proxy', 'ok');
      load();
    } catch { toast('Lỗi xóa', 'err'); }
    finally { setDeleting(null); }
  };

  const activateProxy = async (id: number) => {
    setActivating(id);
    try {
      const r = await fetch(`/admin/api/proxies/${id}/activate`, { method: 'POST', headers: authHeader() });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Lỗi');
      toast('Đã kích hoạt proxy', 'ok');
      load();
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setActivating(null); }
  };

  const deactivateProxy = async () => {
    setActivating(-1);
    try {
      await fetch('/admin/api/proxies/deactivate', { method: 'POST', headers: authHeader() });
      toast('Đã chuyển về Direct', 'ok');
      load();
    } catch { toast('Lỗi', 'err'); }
    finally { setActivating(null); }
  };

  const testProxy = async (id: number) => {
    setTesting(t => ({ ...t, [id]: true }));
    try {
      const r = await fetch(`/admin/api/proxies/${id}/test`, { method: 'POST', headers: authHeader() });
      const d = await r.json();
      setTestResults(tr => ({ ...tr, [id]: d }));
    } catch (e) {
      setTestResults(tr => ({ ...tr, [id]: { ok: false, error: e instanceof Error ? e.message : 'Lỗi' } }));
    } finally { setTesting(t => ({ ...t, [id]: false })); }
  };

  const saveEdit = async (id: number) => {
    setSaving(true);
    try {
      const r = await fetch(`/admin/api/proxies/${id}`, {
        method: 'PATCH', headers: authHeader(),
        body: JSON.stringify({ name: editName.trim(), url: editUrl.trim() }),
      });
      if (!r.ok) throw new Error('Lỗi lưu');
      toast('Đã cập nhật', 'ok');
      setEditId(null);
      load();
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
    finally { setSaving(false); }
  };

  const maxHistory = usage ? Math.max(...usage.history.map(h => h.hits), 1) : 1;
  const activeProxy = proxies.find(p => p.is_active);

  return (
    <div style={{ maxWidth: 800 }}>

      {/* Usage hôm nay */}
      <div className="card mb-24">
        <div className="card-title" style={{ marginBottom: 16 }}>
          📊 Lượng request hôm nay
          {usage && (
            <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 8 }}>
              {usage.today.date} · {activeProxy ? activeProxy.name : 'Direct (không proxy)'}
            </span>
          )}
        </div>
        {usage ? (
          <UsageBar percent={usage.today.percent_used} hits={usage.today.hits} limit={usage.today.limit} />
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Đang tải...</div>
        )}
      </div>

      {/* Biểu đồ 7 ngày */}
      {usage && usage.history.length > 0 && (
        <div className="card mb-24">
          <div className="card-title" style={{ marginBottom: 16 }}>📈 7 ngày gần đây</div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end', height: 80 }}>
            {usage.history.map((h) => {
              const pct = Math.round((h.hits / maxHistory) * 100);
              const color = h.percent_used >= 90 ? 'var(--red)' : h.percent_used >= 70 ? 'var(--yellow)' : 'var(--accent)';
              const isToday = h.date === usage.today.date;
              return (
                <div key={h.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{fmtNum(h.hits)}</div>
                  <div style={{ width: '100%', height: `${Math.max(pct, 4)}%`, background: color, borderRadius: '4px 4px 0 0', opacity: isToday ? 1 : 0.5, minHeight: 4, transition: 'height 0.3s ease' }} title={`${h.date}: ${fmtNum(h.hits)} requests`} />
                  <div style={{ fontSize: 10, color: isToday ? 'var(--text)' : 'var(--text-muted)', fontWeight: isToday ? 700 : 400 }}>{fmtDate(h.date)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Danh sách proxy pool */}
      <div className="card mb-24">
        <div className="spread" style={{ marginBottom: 16 }}>
          <div className="card-title" style={{ marginBottom: 0 }}>
            🔀 Pool Proxy ({proxies.length})
            {activeProxy && (
              <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--green)', marginLeft: 8 }}>
                · Đang dùng: {activeProxy.name}
              </span>
            )}
            {!activeProxy && (
              <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 8 }}>
                · Đang dùng: Direct
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {activeProxy && (
              <button className="btn btn-sm" onClick={deactivateProxy} disabled={activating === -1}>
                {activating === -1 ? <span className="spinner" /> : '⏹ Direct'}
              </button>
            )}
            <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>
              {showAdd ? 'Huỷ' : '+ Thêm Proxy'}
            </button>
          </div>
        </div>

        {/* Form thêm mới */}
        {showAdd && (
          <div style={{ background: 'var(--bg-soft)', borderRadius: 10, padding: 16, marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <input
                className="input" style={{ flex: '1 1 160px', minWidth: 140 }}
                placeholder="Tên (VD: Worker VN 1)"
                value={newName} onChange={e => setNewName(e.target.value)}
              />
              <input
                className="input" style={{ flex: '2 1 280px', minWidth: 200 }}
                placeholder="https://your-worker.workers.dev/api/v0"
                value={newUrl} onChange={e => setNewUrl(e.target.value)}
              />
              <button className="btn btn-primary btn-sm" onClick={addProxy} disabled={adding}>
                {adding ? <span className="spinner" /> : 'Thêm'}
              </button>
            </div>
          </div>
        )}

        {/* Bảng proxy */}
        {proxies.length === 0 ? (
          <div className="empty">Chưa có proxy nào. Bấm "+ Thêm Proxy" để bắt đầu.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tên</th>
                  <th>URL</th>
                  <th>Usage hôm nay</th>
                  <th>Trạng thái</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {proxies.map(p => (
                  <tr key={p.id}>
                    <td>
                      {editId === p.id ? (
                        <input className="input" style={{ width: 140, padding: '4px 8px', fontSize: 13 }}
                          value={editName} onChange={e => setEditName(e.target.value)} />
                      ) : (
                        <span style={{ fontWeight: 600 }}>{p.name}</span>
                      )}
                    </td>
                    <td>
                      {editId === p.id ? (
                        <input className="input" style={{ width: 260, padding: '4px 8px', fontSize: 12 }}
                          value={editUrl} onChange={e => setEditUrl(e.target.value)} />
                      ) : (
                        <code style={{ fontSize: 12, color: 'var(--text-muted)' }} title={p.url}>
                          {shortUrl(p.url)}
                        </code>
                      )}
                    </td>
                    <td style={{ whiteSpace: 'nowrap', fontSize: 13 }}>
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{fmtNum(p.usage_today)}</span>
                      <span style={{ color: 'var(--text-muted)' }}> / {fmtNum(p.usage_limit)}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {p.is_active && <span className="badge ok">Đang dùng</span>}
                        {!p.enabled && <span className="badge fail">Tắt</span>}
                        {testResults[p.id] && (
                          <span className={`badge ${testResults[p.id].ok ? 'ok' : 'fail'}`}>
                            {testResults[p.id].ok ? `✓ ${testResults[p.id].latency_ms}ms` : '✗ Lỗi'}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      {editId === p.id ? (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn-primary btn-sm" onClick={() => saveEdit(p.id)} disabled={saving}>
                            {saving ? <span className="spinner" /> : 'Lưu'}
                          </button>
                          <button className="btn btn-sm" onClick={() => setEditId(null)}>Huỷ</button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {!p.is_active && (
                            <button className="btn btn-primary btn-sm" onClick={() => activateProxy(p.id)} disabled={activating === p.id}>
                              {activating === p.id ? <span className="spinner" /> : '▶ Dùng'}
                            </button>
                          )}
                          <button className="btn btn-sm" onClick={() => testProxy(p.id)} disabled={testing[p.id]}>
                            {testing[p.id] ? <span className="spinner" /> : 'Test'}
                          </button>
                          <button className="btn btn-sm" onClick={() => { setEditId(p.id); setEditName(p.name); setEditUrl(p.url); }}>
                            ✏️
                          </button>
                          <button className="btn btn-danger btn-sm" onClick={() => deleteProxy(p.id)} disabled={deleting === p.id}>
                            {deleting === p.id ? <span className="spinner" /> : '🗑'}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Trạng thái API Base hiện tại */}
      <div className="card mb-24">
        <div className="card-title">Trạng thái API Base</div>
        <div className="spread" style={{ padding: '10px 0', borderBottom: '1px solid var(--border-soft)' }}>
          <span style={{ color: 'var(--text-dim)' }}>URL đang dùng</span>
          <code style={{ fontSize: 13, color: 'var(--accent-hover)', background: 'var(--bg-soft)', padding: '3px 8px', borderRadius: 6 }}>
            {info?.url || '—'}
          </code>
        </div>
        <div className="spread" style={{ padding: '10px 0' }}>
          <span style={{ color: 'var(--text-dim)' }}>Nguồn</span>
          <span className={`badge ${info?.is_custom ? 'busy' : 'idle'}`}>
            {activeProxy ? `Pool: ${activeProxy.name}` : info?.is_custom ? 'Tuỳ chỉnh (DB)' : 'Mặc định (env)'}
          </span>
        </div>
      </div>

      {/* Hướng dẫn */}
      <div className="card">
        <div className="card-title">Hướng dẫn sử dụng Proxy</div>
        <div style={{ lineHeight: 1.8, color: 'var(--text-dim)', fontSize: 14 }}>
          <p style={{ marginBottom: 12 }}>
            Thêm nhiều Cloudflare Worker vào Pool, đặt tên dễ nhớ (VD: "Worker VN 1", "Worker US 2").
            Mỗi Worker miễn phí có <strong>100,000 request/ngày</strong>. Khi một Worker gần hết quota, chuyển sang Worker khác.
          </p>
          <p style={{ fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>Code Cloudflare Worker:</p>
          <div style={{ background: 'var(--bg-soft)', borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontFamily: 'monospace', fontSize: 13, whiteSpace: 'pre' }}>
{`export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = "chat.deepseek.com";
    return fetch(new Request(url, request));
  }
}`}
          </div>
          <ol style={{ paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <li>Tạo Worker trên <strong>dash.cloudflare.com</strong>, paste code trên vào</li>
            <li>Deploy và copy URL Worker (VD: <code style={{ background: 'var(--bg)', padding: '1px 6px', borderRadius: 4 }}>https://xxx.workers.dev</code>)</li>
            <li>Dán URL vào form "+ Thêm Proxy", đặt tên dễ nhớ</li>
            <li>Bấm <strong>Test</strong> để kiểm tra, rồi bấm <strong>▶ Dùng</strong> để kích hoạt</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
