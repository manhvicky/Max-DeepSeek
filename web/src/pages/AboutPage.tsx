import { useEffect, useState } from 'react';
import { api, type AppInfoResp } from '../api';
import { IconBookOpen, IconCopy, IconGithub, IconMail, IconSparkles } from '../icons';
import { useToast } from '../toast';

export default function AboutPage() {
  const toast = useToast();
  const [info, setInfo] = useState<AppInfoResp | null>(null);

  useEffect(() => {
    api.appInfo().then(setInfo).catch(() => {});
  }, []);

  const copy = (text: string, message: string) => {
    navigator.clipboard.writeText(text);
    toast(message, 'ok');
  };

  return (
    <div>
      <div className="hero-card mb-24">
        <div>
          <div className="badge ok" style={{ marginBottom: 12 }}>Tác giả / Người duy trì</div>
          <h2 style={{ fontSize: 28, marginBottom: 8 }}>{info?.name || 'Max-DeepSeek'}</h2>
          <p style={{ color: 'var(--text-dim)', maxWidth: 760, lineHeight: 1.7 }}>
            Cổng API self-hosted tương thích OpenAI, quản lý pool tài khoản DeepSeek, API key, proxy, logs và cập nhật.
          </p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => copy(info?.repository || '', 'Đã sao chép link GitHub')}><IconGithub width={15} height={15} /> GitHub</button>
          <button className="btn" onClick={() => copy(info?.author.email || '', 'Đã sao chép email')}><IconMail width={15} height={15} /> Email</button>
        </div>
      </div>

      <div className="grid-2 mb-24" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title"><IconSparkles width={16} height={16} /> Thông tin phát hành</div>
          <Info label="Ứng dụng" value={info?.name || 'Max-DeepSeek'} />
          <Info label="Phiên bản" value={info?.version || '1.0.0'} />
          <Info label="Kênh" value={info?.channel || 'stable'} />
          <Info label="Tác giả" value={info?.author.name || 'Vũ Duy Mạnh'} />
          <Info label="Email" value={info?.author.email || 'manhq7@gmail.com'} />
          <Info label="Repository" value={info?.repository || 'https://github.com/manhvicky/Max-DeepSeek'} />
        </div>

        <div className="card">
          <div className="card-title"><IconBookOpen width={16} height={16} /> Hỗ trợ người dùng</div>
          <ul style={{ paddingLeft: 18, color: 'var(--text-dim)', lineHeight: 1.9 }}>
            <li>Nếu muốn cập nhật, vào mục Hướng dẫn để xem thông tin phiên bản và thao tác kiểm tra cập nhật.</li>
            <li>Nếu tự host bằng Docker, ưu tiên cập nhật qua script để có backup và rollback.</li>
            <li>Không commit API key, database hoặc file runtime lên GitHub.</li>
            <li>Khi public repo, nên tạo GitHub Release và gắn tag khớp với file VERSION.</li>
          </ul>
        </div>
      </div>

      <div className="card">
        <div className="spread mb-20" style={{ gap: 12, flexWrap: 'wrap' }}>
          <div className="card-title" style={{ marginBottom: 0 }}><IconCopy width={16} height={16} /> Metadata để sao chép</div>
          <button className="btn btn-sm" onClick={() => copy(`Tác giả: ${info?.author.name || 'Vũ Duy Mạnh'}\nEmail: ${info?.author.email || 'manhq7@gmail.com'}\nRepository: ${info?.repository || 'https://github.com/manhvicky/Max-DeepSeek'}`, 'Đã sao chép metadata')}><IconCopy width={14} height={14} /> Sao chép</button>
        </div>
        <pre className="code-block">{`Tác giả: ${info?.author.name || 'Vũ Duy Mạnh'}
Email: ${info?.author.email || 'manhq7@gmail.com'}
Repository: ${info?.repository || 'https://github.com/manhvicky/Max-DeepSeek'}`}</pre>
      </div>
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
