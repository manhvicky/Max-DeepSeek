import { useEffect, useMemo, useState } from 'react';
import { api, type AppInfoResp, type UpdateHistoryItem, type UpdateStatusResp } from '../api';
import { useToast } from '../toast';
import { IconCheck, IconClock, IconCopy, IconRefresh, IconRotateCcw, IconUpload } from '../icons';

function fmtTs(ts: number): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString('vi-VN');
}

function copy(text: string, toast: (msg: string, kind?: 'ok' | 'err') => void, msg = 'Da sao chep') {
  navigator.clipboard.writeText(text);
  toast(msg, 'ok');
}

export default function UpdatePage() {
  const toast = useToast();
  const [info, setInfo] = useState<AppInfoResp | null>(null);
  const [status, setStatus] = useState<UpdateStatusResp | null>(null);
  const [history, setHistory] = useState<UpdateHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [appInfo, updateStatus, updateHistory] = await Promise.all([
        api.appInfo(), api.updateStatus(), api.updateHistory(),
      ]);
      setInfo(appInfo);
      setStatus(updateStatus);
      setHistory(updateHistory);
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Khong tai duoc thong tin cap nhat', 'err');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const changelog = useMemo(() => status?.changelog?.filter(Boolean) ?? [], [status]);

  const action = async (kind: 'check' | 'apply' | 'rollback') => {
    setBusy(true);
    try {
      if (kind === 'check') {
        await api.checkUpdate();
        toast('Da kiem tra phien ban moi', 'ok');
      } else if (kind === 'apply') {
        const actionRes = await api.applyUpdate(status?.latest_version);
        toast(actionRes.message || 'Da thuc hien lenh', actionRes.ok ? 'ok' : 'err');
      } else {
        const actionRes = await api.rollbackUpdate() as import('../api').UpdateActionResp;
        toast(actionRes.message || 'Da thuc hien lenh', actionRes.ok ? 'ok' : 'err');
      }
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Tac vu that bai', 'err');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="hero-card mb-24">
        <div>
          <div className={`badge ${status?.update_available ? 'busy' : 'ok'}`} style={{ marginBottom: 12 }}>
            {status?.update_available ? 'Co ban cap nhat moi' : 'Dang o ban moi nhat'}
          </div>
          <h2 style={{ fontSize: 28, marginBottom: 8 }}>Cap nhat Max-DeepSeek</h2>
          <p style={{ color: 'var(--text-dim)', maxWidth: 760, lineHeight: 1.7 }}>
            Theo doi phien ban, changelog, thong tin tac gia va cap nhat he thong theo kieu one-click.
            Neu self-update dang tat, trang nay van hien lenh de copy va cap nhat thu cong giong 9router.
          </p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => action('check')} disabled={busy || loading}><IconRefresh width={15} height={15} /> Kiem tra</button>
          <button className="btn btn-primary" onClick={() => action('apply')} disabled={busy || loading}><IconUpload width={15} height={15} /> Cap nhat ngay</button>
          <button className="btn" onClick={() => action('rollback')} disabled={busy || loading}><IconRotateCcw width={15} height={15} /> Rollback</button>
        </div>
      </div>

      <div className="stat-grid mb-24">
        <Stat title="Hien tai" value={status?.current_version || info?.version || '—'} hint="Phien ban dang chay" />
        <Stat title="Moi nhat" value={status?.latest_version || '—'} hint={status?.published_at || 'Manifest / GitHub'} />
        <Stat title="Kenh" value={status?.channel || info?.channel || 'stable'} hint="Stable / release" />
        <Stat title="Tac gia" value={info?.author.name || 'Vu Duy Manh'} hint={info?.author.email || 'manhq7@gmail.com'} />
      </div>

      <div className="grid-2 mb-24" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title"><IconCheck width={16} height={16} /> Trang thai cap nhat</div>
          <Info label="Ung dung" value={info?.name || 'Max-DeepSeek'} />
          <Info label="Version hien tai" value={status?.current_version || info?.version || '—'} />
          <Info label="Version moi" value={status?.latest_version || '—'} />
          <Info label="GitHub / Release" value={status?.release_url || info?.repository || '—'} />
          <Info label="Tac gia" value={`${info?.author.name || 'Vu Duy Manh'} <${info?.author.email || 'manhq7@gmail.com'}>`} />
          {status?.notes && <p className="soft-note" style={{ marginTop: 14 }}>{status.notes}</p>}
        </div>

        <div className="card">
          <div className="spread mb-20" style={{ gap: 12, flexWrap: 'wrap' }}>
            <div className="card-title" style={{ marginBottom: 0 }}><IconClock width={16} height={16} /> Lenh cap nhat</div>
            <button className="btn btn-sm" onClick={() => copy(status?.update_command || '', toast, 'Da sao chep lenh cap nhat')}><IconCopy width={14} height={14} /> Copy lenh</button>
          </div>
          <pre className="code-block">{status?.update_command || 'bash /app/scripts/update.sh'}</pre>
          <div className="spread" style={{ marginTop: 12, gap: 12, flexWrap: 'wrap' }}>
            <div className="card-title" style={{ marginBottom: 0 }}>Lenh rollback</div>
            <button className="btn btn-sm" onClick={() => copy(status?.rollback_command || '', toast, 'Da sao chep lenh rollback')}><IconCopy width={14} height={14} /> Copy lenh</button>
          </div>
          <pre className="code-block">{status?.rollback_command || 'bash /app/scripts/rollback.sh'}</pre>
          {!status?.allow_self_update && (
            <p className="soft-note" style={{ marginTop: 12 }}>
              Self-update dang tat de an toan. Anh van co the bam copy lenh va chay tren server, hoac bat bien moi truong <span className="code-pill">MAX_DEEPSEEK_ALLOW_SELF_UPDATE=1</span>.
            </p>
          )}
        </div>
      </div>

      <div className="card mb-24">
        <div className="card-title"><IconRefresh width={16} height={16} /> Changelog</div>
        {changelog.length === 0 ? (
          <div className="empty">Chua co changelog tu manifest.</div>
        ) : (
          <div className="timeline">
            {changelog.map((item, idx) => (
              <div key={`${idx}-${item}`} className="timeline-item">{item}</div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title"><IconClock width={16} height={16} /> Lich su cap nhat</div>
        {history.length === 0 ? (
          <div className="empty">Chua co lich su.</div>
        ) : (
          <div className="table-wrap" style={{ border: 'none', background: 'transparent' }}>
            <table>
              <thead>
                <tr>
                  <th>Thoi gian</th>
                  <th>Hanh dong</th>
                  <th>Version</th>
                  <th>Trang thai</th>
                  <th>Ghi chu</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}>
                    <td>{fmtTs(item.created_at)}</td>
                    <td>{item.action}</td>
                    <td>{item.from_version || '—'} → {item.to_version || '—'}</td>
                    <td><span className={`badge ${item.status === 'success' || item.status === 'up-to-date' ? 'ok' : item.status === 'failed' ? 'fail' : 'busy'}`}>{item.status}</span></td>
                    <td style={{ maxWidth: 380 }}>{item.notes || item.output || item.command || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ title, value, hint }: { title: string; value: string; hint: string }) {
  return (
    <div className="stat-card">
      <div className="label">{title}</div>
      <div className="value" style={{ fontSize: 24 }}>{value}</div>
      <div className="hint">{hint}</div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="spread info-row" style={{ gap: 16 }}>
      <span style={{ color: 'var(--text-dim)' }}>{label}</span>
      <span className="code-pill" style={{ maxWidth: '65%', whiteSpace: 'normal', textAlign: 'right' }}>{value}</span>
    </div>
  );
}
