import { useEffect, useState } from 'react';
import { api, type StatsResp, type StatusResp } from '../api';
import { IconActivity, IconCheck, IconClock, IconZap, IconUsers } from '../icons';

function fmtUptime(s: number): string {
  if (s < 60) return `${s} giây`;
  if (s < 3600) return `${Math.floor(s / 60)} phút`;
  if (s < 86400) return `${Math.floor(s / 3600)} giờ`;
  return `${Math.floor(s / 86400)} ngày`;
}
function fmtNum(n: number): string {
  return n.toLocaleString('vi-VN');
}

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResp | null>(null);
  const [status, setStatus] = useState<StatusResp | null>(null);

  const load = async () => {
    try {
      const [s, st] = await Promise.all([api.stats(), api.status()]);
      setStats(s); setStatus(st);
    } catch { /* ignore */ }
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const successRate = stats && stats.total_requests > 0
    ? ((stats.success_requests / stats.total_requests) * 100).toFixed(1)
    : '100';
  const poolIssue = status && status.health && status.health !== 'ok';
  const poolMessage = status
    ? status.health === 'empty'
      ? 'Pool chưa có tài khoản khả dụng.'
      : status.idle === 0
        ? `Không có tài khoản sẵn sàng${status.next_ready_in ? ` · thử lại sau ${status.next_ready_in}s` : ''}.`
        : `${status.cooling || 0} tài khoản đang nghỉ, ${status.error + status.invalid} tài khoản lỗi.`
    : '';

  return (
    <div>
      <div className="stat-grid mb-24">
        <div className="stat-card">
          <div className="icon-box"><IconActivity width={18} height={18} /></div>
          <div className="label">Tổng yêu cầu</div>
          <div className="value">{stats ? fmtNum(stats.total_requests) : '—'}</div>
          <div className="hint">{stats ? `${fmtNum(stats.failed_requests)} thất bại` : ''}</div>
        </div>
        <div className="stat-card">
          <div className="icon-box"><IconCheck width={18} height={18} /></div>
          <div className="label">Tỷ lệ thành công</div>
          <div className="value">{successRate}%</div>
          <div className="hint">{stats ? `${fmtNum(stats.success_requests)} thành công` : ''}</div>
        </div>
        <div className="stat-card">
          <div className="icon-box"><IconClock width={18} height={18} /></div>
          <div className="label">Độ trễ trung bình</div>
          <div className="value">{stats ? fmtNum(stats.avg_latency_ms) : '—'}<span style={{ fontSize: 15, color: 'var(--text-muted)' }}> ms</span></div>
          <div className="hint">Thời gian đáp ứng</div>
        </div>
        <div className="stat-card">
          <div className="icon-box"><IconZap width={18} height={18} /></div>
          <div className="label">Tokens đã dùng</div>
          <div className="value">{stats ? fmtNum(stats.total_prompt_tokens + stats.total_completion_tokens) : '—'}</div>
          <div className="hint">{stats ? `${fmtNum(stats.total_completion_tokens)} sinh ra` : ''}</div>
        </div>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: '1.4fr 1fr', alignItems: 'start' }}>
        <div className="card">
          <div className="card-title"><IconUsers width={16} height={16} /> Pool tài khoản DeepSeek</div>
          {poolIssue && (
            <div style={{ marginBottom: 12, padding: 12, borderRadius: 10, background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.3)', color: 'var(--text)' }}>
              <b>Pool cần chú ý:</b> {poolMessage}
            </div>
          )}
          {status && (
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
              <PoolStat label="Tổng" value={status.total} color="var(--text)" />
              <PoolStat label="Sẵn sàng" value={status.idle} color="var(--green)" />
              <PoolStat label="Đang bận" value={status.busy} color="var(--accent-hover)" />
              <PoolStat label="Nghỉ" value={status.cooling || 0} color="#f59e0b" />
              <PoolStat label="Lỗi" value={status.error + status.invalid} color="var(--red)" />
            </div>
          )}
          {status && status.total === 0 && (
            <div className="empty">Chưa có tài khoản nào. Thêm tài khoản DeepSeek để bắt đầu.</div>
          )}
        </div>
        <div className="card">
          <div className="card-title"><IconClock width={16} height={16} /> Thông tin hệ thống</div>
          <InfoRow label="Thời gian hoạt động" value={stats ? fmtUptime(stats.uptime_secs) : '—'} />
          <InfoRow label="Tài khoản hoạt động" value={status ? `${status.idle + status.busy}/${status.total}` : '—'} />
          <InfoRow label="Đang bật" value={status ? `${status.enabled ?? status.total}/${status.total}` : '—'} />
          <InfoRow label="Trạng thái pool" value={status?.health === 'ok' ? 'Ổn định' : 'Cần chú ý'} badge={status?.health === 'ok'} />
        </div>
      </div>
    </div>
  );
}

function PoolStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '14px 8px', background: 'var(--bg-soft)', borderRadius: 8 }}>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
    </div>
  );
}
function InfoRow({ label, value, badge }: { label: string; value: string; badge?: boolean }) {
  return (
    <div className="spread" style={{ padding: '10px 0', borderBottom: '1px solid var(--border-soft)' }}>
      <span style={{ color: 'var(--text-dim)' }}>{label}</span>
      {badge ? <span className="badge ok">{value}</span> : <span style={{ fontWeight: 600 }}>{value}</span>}
    </div>
  );
}
