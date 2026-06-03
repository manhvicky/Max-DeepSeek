import { useEffect, useState } from 'react';
import { api, type Account } from '../api';
import { useToast } from '../toast';
import { IconPlus, IconTrash, IconRefresh, IconZap } from '../icons';

const STATE_LABEL: Record<string, string> = {
  idle: 'Sẵn sàng', busy: 'Đang bận', error: 'Lỗi', invalid: 'Không hợp lệ',
  cooling: 'Nghỉ tạm',
};

function fmtCooldown(secs?: number): string {
  if (!secs || secs <= 0) return '';
  if (secs >= 3600) return `${Math.floor(secs / 3600)}h${Math.floor((secs % 3600) / 60)}p`;
  if (secs >= 60) return `${Math.floor(secs / 60)} phút`;
  return `${secs}s`;
}

const COLS_KEY = 'mds_accounts_view';
const SORT_KEY = 'mds_accounts_sort';
type ViewMode = 'list' | '2' | '3';
type SortState = 'none' | 'active' | 'inactive' | 'email-asc' | 'email-desc' | 'label-asc' | 'label-desc';

const STATE_ORDER: Record<string, number> = { idle: 0, busy: 1, cooling: 2, error: 3, invalid: 4 };

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [testing, setTesting] = useState<number | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [reloginAll, setReloginAll] = useState(false);
  const [testingBlocked, setTestingBlocked] = useState(false);
  const [toggling, setToggling] = useState<number | null>(null);
  const [view, setView] = useState<ViewMode>(() => (localStorage.getItem(COLS_KEY) as ViewMode) || 'list');
  const [sort, setSort] = useState<SortState>(() => (localStorage.getItem(SORT_KEY) as SortState) || 'none');
  const toast = useToast();

  const setViewP = (v: ViewMode) => { setView(v); localStorage.setItem(COLS_KEY, v); };
  const setSortP = (s: SortState) => { setSort(s); localStorage.setItem(SORT_KEY, s); };

  const load = async () => {
    try { setAccounts(await api.accounts()); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lỗi tải', 'err'); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, []);

  // sort logic
  const cycleColSort = (col: "email" | "label") => {
    setSortP(sort === `${col}-asc` ? `${col}-desc` as SortState : sort === `${col}-desc` ? "none" : `${col}-asc` as SortState);
  };
  const colSortIcon = (col: "email" | "label") => {
    if (sort === `${col}-asc`) return " ↑";
    if (sort === `${col}-desc`) return " ↓";
    return "";
  };
  const sorted = [...accounts].sort((a, b) => {
    if (sort === "none") return 0;
    if (sort === "active" || sort === "inactive") {
      const oa = STATE_ORDER[a.state] ?? 9;
      const ob = STATE_ORDER[b.state] ?? 9;
      return sort === "active" ? oa - ob : ob - oa;
    }
    if (sort === "email-asc" || sort === "email-desc") {
      const ea = (a.email || a.mobile || "").toLowerCase();
      const eb = (b.email || b.mobile || "").toLowerCase();
      return sort === "email-asc" ? ea.localeCompare(eb) : eb.localeCompare(ea);
    }
    if (sort === "label-asc" || sort === "label-desc") {
      const la = (a.label || "").toLowerCase();
      const lb = (b.label || "").toLowerCase();
      return sort === "label-asc" ? la.localeCompare(lb) : lb.localeCompare(la);
    }
    return 0;
  });

  // allEnabled: true nếu tất cả đang bật, false nếu tất cả tắt, null nếu hỗn hợp
  const allEnabled = accounts.length === 0 ? true
    : accounts.every(a => a.enabled ?? true) ? true
    : accounts.every(a => !(a.enabled ?? true)) ? false : null;
  const blockedAccounts = accounts.filter(a => a.state === 'cooling');
  const enabledCount = accounts.filter(a => a.enabled ?? true).length;
  const disabledCount = accounts.length - enabledCount;
  const readyCount = accounts.filter(a => a.state === 'idle' && (a.enabled ?? true)).length;
  const busyCount = accounts.filter(a => a.state === 'busy').length;
  const errorCount = accounts.filter(a => a.state === 'error').length;
  const invalidCount = accounts.filter(a => a.state === 'invalid').length;
  const healthPercent = accounts.length ? Math.round((readyCount / accounts.length) * 100) : 0;
  const cooldownLongest = Math.max(0, ...accounts.map(a => a.cooldown_remaining || 0));
  const totalErrors = accounts.reduce((sum, a) => sum + (a.error_count || 0), 0);

  const del = async (id: number) => {
    if (!confirm('Xóa tài khoản này khỏi pool?')) return;
    try { await api.delAccount(id); toast('Đã xóa tài khoản', 'ok'); load(); }
    catch (e) { toast(e instanceof Error ? e.message : 'Lỗi xóa', 'err'); }
  };
  const relogin = async (id: number) => {
    toast('Đang đăng nhập lại...', 'info');
    try {
      const r = await api.reloginAccount(id);
      toast(r.ok ? 'Đăng nhập lại thành công' : 'Đăng nhập lại thất bại', r.ok ? 'ok' : 'err');
      load();
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi', 'err'); }
  };
  const test = async (id: number) => {
    setTesting(id);
    try {
      const r = await api.testAccount(id);
      toast(r.ok ? `✓ ${a_email(id)} OK (${r.latency_ms}ms)` : `✗ ${a_email(id)}: ${r.error}`, r.ok ? 'ok' : 'err');
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Lỗi kiểm tra', 'err');
    } finally { setTesting(null); }
  };
  const a_email = (id: number) => accounts.find(a => a.id === id)?.email || `#${id}`;

  const toggle = async (a: Account) => {
    const next = !(a.enabled ?? true);
    setToggling(a.id);
    setAccounts((prev: Account[]) => prev.map((x: Account) => x.id === a.id ? { ...x, enabled: next } : x));
    try {
      await api.enableAccount(a.id, next);
      toast(next ? 'Đã bật tài khoản' : 'Đã tắt tài khoản', 'ok');
      load();
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Lỗi', 'err');
      load();
    } finally { setToggling(null); }
  };

  // Bulk actions
  const toggleAll = async () => {
    const next = !(allEnabled === true);
    toast(next ? 'Đang bật tất cả...' : 'Đang tắt tất cả...', 'info');
    await Promise.all(accounts.map(a => api.enableAccount(a.id, next).catch(() => {})));
    toast(next ? 'Đã bật tất cả' : 'Đã tắt tất cả', 'ok');
    load();
  };

  const testBlocked = async () => {
    if (blockedAccounts.length === 0) { toast('Không có tài khoản đang bị chặn', 'info'); return; }
    if (!confirm('Kiểm tra ' + blockedAccounts.length + ' tài khoản đang bị chặn?')) return;
    setTestingBlocked(true);
    toast('Đang kiểm tra ' + blockedAccounts.length + ' tài khoản bị chặn...', 'info');
    const results = await Promise.allSettled(blockedAccounts.map(a => api.testAccount(a.id)));
    const ok = results.filter(r => r.status === 'fulfilled' && (r.value as {ok:boolean}).ok).length;
    toast('Kiểm tra tài khoản bị chặn xong: ' + ok + '/' + blockedAccounts.length + ' hoạt động', ok === blockedAccounts.length ? 'ok' : 'err');
    setTestingBlocked(false);
    load();
  };

  const testAll = async () => {
    if (!confirm(`Kiểm tra ${accounts.length} tài khoản? Có thể mất vài phút.`)) return;
    setTestingAll(true);
    toast(`Đang kiểm tra ${accounts.length} tài khoản...`, 'info');
    const results = await Promise.allSettled(accounts.map(a => api.testAccount(a.id)));
    const ok = results.filter(r => r.status === 'fulfilled' && (r.value as {ok:boolean}).ok).length;
    toast(`Kiểm tra xong: ${ok}/${accounts.length} hoạt động`, ok === accounts.length ? 'ok' : 'err');
    setTestingAll(false);
    load();
  };
  const reloginAllFn = async () => {
    if (!confirm(`Đăng nhập lại ${accounts.length} tài khoản?`)) return;
    setReloginAll(true);
    toast(`Đang đăng nhập lại ${accounts.length} tài khoản...`, 'info');
    await Promise.allSettled(accounts.map(a => api.reloginAccount(a.id).catch(() => {})));
    toast('Đã đăng nhập lại tất cả', 'ok');
    setReloginAll(false);
    load();
  };
  const delAll = async () => {
    if (!confirm(`Xóa TẤT CẢ ${accounts.length} tài khoản khỏi pool? Không thể hoàn tác!`)) return;
    await Promise.allSettled(accounts.map(a => api.delAccount(a.id).catch(() => {})));
    toast('Đã xóa tất cả tài khoản', 'ok');
    load();
  };

  const cycleSort = () => setSortP((sort === "active" || sort === "inactive") ? (sort === "active" ? "inactive" : "none") : "active");
  const sortIcon = sort === "active" ? " ↑" : sort === "inactive" ? " ↓" : "";

  const renderSwitch = (a: Account) => {
    const on = a.enabled ?? true;
    return (
      <button
        className={`switch ${on ? 'on' : ''}`}
        onClick={() => toggle(a)}
        disabled={toggling === a.id}
        title={on ? 'Đang bật — bấm để tắt' : 'Đang tắt — bấm để bật'}
      >
        <span className="switch-knob" />
      </button>
    );
  };

  const renderActions = (a: Account) => (
    <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
      <button className="btn btn-sm" onClick={() => test(a.id)} disabled={testing === a.id} title="Kiểm tra">
        {testing === a.id ? <span className="spinner" /> : <><IconZap width={14} height={14} /> Kiểm tra</>}
      </button>
      <button className="btn btn-sm" onClick={() => relogin(a.id)} title="Đăng nhập lại">
        <IconRefresh width={14} height={14} />
      </button>
      <button className="btn btn-sm btn-danger" onClick={() => del(a.id)} title="Xóa">
        <IconTrash width={14} height={14} />
      </button>
    </div>
  );

  return (
    <div>
      <div className="spread mb-20">
        <p style={{ color: 'var(--text-dim)' }}>
          Quản lý pool tài khoản DeepSeek. Hệ thống tự đăng nhập và xoay vòng khi có yêu cầu.
        </p>
        <div className="row" style={{ gap: 12 }}>
          <div className="col-switch">
            <button className={`col-btn ${view === 'list' ? 'active' : ''}`} onClick={() => setViewP('list')} title="Danh sách">☰</button>
            <button className={`col-btn ${view === '2' ? 'active' : ''}`} onClick={() => setViewP('2')} title="2 cột">▥</button>
            <button className={`col-btn ${view === '3' ? 'active' : ''}`} onClick={() => setViewP('3')} title="3 cột">▦</button>
          </div>
          <button className="btn" onClick={testBlocked} disabled={testingBlocked} title="Kiểm tra tài khoản đang bị chặn">
            {testingBlocked ? <span className="spinner" /> : `Kiểm tra bị chặn (${blockedAccounts.length})`}
          </button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <IconPlus width={16} height={16} /> Thêm tài khoản
          </button>
        </div>
      </div>


      <div className="card mb-24" style={{ border: '1px solid rgba(245, 158, 11, 0.28)', background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.10), rgba(34, 197, 94, 0.06))' }}>
        <div className="card-title">Hướng dẫn dùng nhiều tài khoản DeepSeek</div>
        <p style={{ color: 'var(--text-dim)', marginBottom: 12 }}>
          Nên dùng nhiều tài khoản DeepSeek phụ/rác để chia tải. Mỗi request chỉ dùng 1 tài khoản; sau khi trả lời xong, tài khoản đó sẽ nghỉ một khoảng thời gian trước khi được dùng lại để giảm nguy cơ bị mute/rate-limit.
        </p>
        <div className="grid-2" style={{ alignItems: 'center' }}>
          <div>
            <div className="hint">Mặc định hiện tại: khoảng <b>45 giây</b> giữa 2 request trên cùng 1 tài khoản.</div>
            <div className="hint">Ví dụ: 10 tài khoản chạy an toàn hơn khoảng 10-13 request/phút; muốn nhanh hơn thì tăng số tài khoản hoặc giảm giây trong Cài đặt.</div>
          </div>
          <div className="row" style={{ justifyContent: 'flex-end', gap: 10 }}>
            <a className="btn" href="https://chat.deepseek.com/sign_up" target="_blank" rel="noreferrer">Đăng ký tài khoản DeepSeek</a>
            <a className="btn btn-primary" href="/admin/config">Chỉnh giãn cách request</a>
          </div>
        </div>
      </div>

      <div className="stat-grid mb-24 account-stat-grid">
        <div className="stat-card">
          <div className="label">Tổng tài khoản</div>
          <div className="value">{accounts.length}</div>
          <div className="hint">Bật {enabledCount} · Tắt {disabledCount}</div>
        </div>
        <div className="stat-card">
          <div className="label">Sẵn sàng dùng</div>
          <div className="value">{readyCount}</div>
          <div className="hint">Độ khỏe pool {healthPercent}%</div>
        </div>
        <div className="stat-card">
          <div className="label">Đang bận</div>
          <div className="value">{busyCount}</div>
          <div className="hint">Request đang chạy hoặc vừa được cấp account</div>
        </div>
        <div className="stat-card">
          <div className="label">Bị chặn / nghỉ tạm</div>
          <div className="value">{blockedAccounts.length}</div>
          <div className="hint">Lâu nhất còn {fmtCooldown(cooldownLongest) || '0s'}</div>
        </div>
        <div className="stat-card">
          <div className="label">Lỗi cần xem</div>
          <div className="value">{errorCount + invalidCount}</div>
          <div className="hint">Lỗi {errorCount} · Không hợp lệ {invalidCount}</div>
        </div>
        <div className="stat-card">
          <div className="label">Tổng lượt lỗi</div>
          <div className="value">{totalErrors}</div>
          <div className="hint">Cộng error_count của toàn bộ tài khoản</div>
        </div>
      </div>

      {loading ? (
        <div className="loading-full"><div className="spinner" /></div>
      ) : accounts.length === 0 ? (
        <div className="card"><div className="empty">
          Chưa có tài khoản nào.<br />Thêm tài khoản DeepSeek để bắt đầu nhận yêu cầu.
        </div></div>
      ) : view === 'list' ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 52 }}>
                  <button
                    className={`switch ${allEnabled === true ? 'on' : ''}`}
                    onClick={toggleAll}
                    title={allEnabled === true ? 'Tắt tất cả' : 'Bật tất cả'}
                    style={{ opacity: allEnabled === null ? 0.6 : 1 }}
                  >
                    <span className="switch-knob" />
                  </button>
                </th>
                <th
                  style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                  onClick={() => cycleColSort("email")}
                  title="Bấm để sắp xếp theo tài khoản"
                >
                  Tài khoản{colSortIcon("email")}
                </th>
                <th
                  style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                  onClick={() => cycleColSort("label")}
                  title="Bấm để sắp xếp theo nhãn"
                >
                  Nhãn{colSortIcon("label")}
                </th>
                <th
                  style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}
                  onClick={cycleSort}
                  title="Bấm để sắp xếp theo trạng thái"
                >
                  Trạng thái{sortIcon}
                </th>
                <th>Lỗi</th>
                <th style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
                    <button className="btn btn-sm" onClick={testAll} disabled={testingAll} title="Kiểm tra tất cả">
                      {testingAll ? <span className="spinner" /> : <><IconZap width={13} height={13} /> Tất cả</>}
                    </button>
                    <button className="btn btn-sm" onClick={reloginAllFn} disabled={reloginAll} title="Đăng nhập lại tất cả">
                      {reloginAll ? <span className="spinner" /> : <IconRefresh width={13} height={13} />}
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={delAll} title="Xóa tất cả">
                      <IconTrash width={13} height={13} />
                    </button>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((a) => {
                const on = a.enabled ?? true;
                return (
                  <tr key={a.id} style={{ opacity: on ? 1 : 0.5 }}>
                    <td>{renderSwitch(a)}</td>
                    <td><span className="code-pill">{a.email || a.mobile || `#${a.id}`}</span></td>
                    <td style={{ color: 'var(--text-dim)' }}>{a.label || '—'}</td>
                    <td>
                      <span className={`badge ${a.state}`}>{STATE_LABEL[a.state] || a.state}</span>
                    </td>
                    <td style={{ color: 'var(--text-muted)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.last_error || '—'}
                    </td>
                    <td>{renderActions(a)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="acc-grid" style={{ gridTemplateColumns: `repeat(${view}, minmax(0, 1fr))` }}>
          {accounts.map((a) => {
            const on = a.enabled ?? true;
            return (
              <div key={a.id} className={`acc-card ${on ? '' : 'off'}`}>
                <div className="acc-card-head">
                  {renderSwitch(a)}
                  <span className="code-pill">{a.email || a.mobile || `#${a.id}`}</span>
                </div>
                <div className="acc-card-row">
                  <span className={`badge ${a.state}`}>{STATE_LABEL[a.state] || a.state}</span>
                  {!on ? <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>· đã tắt</span> : null}
                </div>
                {a.label ? <div className="acc-card-label">{a.label}</div> : null}
                {a.last_error ? (
                  <div className="acc-card-err" title={a.last_error}>{a.last_error}</div>
                ) : null}
                <div className="acc-card-actions">{renderActions(a)}</div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && <AddModal onClose={() => setShowModal(false)} onAdded={load} />}
    </div>
  );
}

function AddModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [tab, setTab] = useState<'email' | 'mobile'>('email');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [areaCode, setAreaCode] = useState('+84');
  const [password, setPassword] = useState('');
  const [label, setLabel] = useState('');
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) { toast('Nhập mật khẩu', 'err'); return; }
    if (tab === 'email' && !email) { toast('Nhập email', 'err'); return; }
    if (tab === 'mobile' && !mobile) { toast('Nhập số điện thoại', 'err'); return; }
    setLoading(true);
    try {
      await api.addAccount({
        email: tab === 'email' ? email : '',
        mobile: tab === 'mobile' ? mobile : '',
        area_code: tab === 'mobile' ? areaCode : '',
        password, label,
      });
      toast('Đã thêm tài khoản, đang đăng nhập nền...', 'ok');
      onAdded(); onClose();
    } catch (e) { toast(e instanceof Error ? e.message : 'Lỗi thêm', 'err'); }
    finally { setLoading(false); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3>Thêm tài khoản DeepSeek</h3>
        <div className="row mb-20" style={{ gap: 8 }}>
          <button type="button" className={`btn btn-sm ${tab === 'email' ? 'btn-primary' : ''}`} onClick={() => setTab('email')}>Email</button>
          <button type="button" className={`btn btn-sm ${tab === 'mobile' ? 'btn-primary' : ''}`} onClick={() => setTab('mobile')}>Số điện thoại</button>
        </div>
        {tab === 'email' ? (
          <div className="field">
            <label>Email</label>
            <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" autoFocus />
          </div>
        ) : (
          <div className="grid-2" style={{ gridTemplateColumns: '90px 1fr' }}>
            <div className="field">
              <label>Mã vùng</label>
              <input className="input" value={areaCode} onChange={(e) => setAreaCode(e.target.value)} placeholder="+84" />
            </div>
            <div className="field">
              <label>Số điện thoại</label>
              <input className="input" value={mobile} onChange={(e) => setMobile(e.target.value)} placeholder="912345678" autoFocus />
            </div>
          </div>
        )}
        <div className="field">
          <label>Mật khẩu</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Mật khẩu DeepSeek" />
        </div>
        <div className="field">
          <label>Nhãn (tùy chọn)</label>
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="VD: tài khoản 1" />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>Hủy</button>
          <button className="btn btn-primary" disabled={loading}>
            {loading ? <span className="spinner" /> : 'Thêm'}
          </button>
        </div>
      </form>
    </div>
  );
}
