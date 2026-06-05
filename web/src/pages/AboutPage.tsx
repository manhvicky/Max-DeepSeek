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
          <div className="badge ok" style={{ marginBottom: 12 }}>About / Maintainer</div>
          <h2 style={{ fontSize: 28, marginBottom: 8 }}>{info?.name || 'Max-DeepSeek'}</h2>
          <p style={{ color: 'var(--text-dim)', maxWidth: 760, lineHeight: 1.7 }}>
            Cong API self-hosted tuong thich OpenAI, quan ly pool tai khoan DeepSeek, API key, proxy, logs va cap nhat.
          </p>
        </div>
        <div className="hero-actions">
          <button className="btn" onClick={() => copy(info?.repository || '', 'Da sao chep link GitHub')}><IconGithub width={15} height={15} /> GitHub</button>
          <button className="btn" onClick={() => copy(info?.author.email || '', 'Da sao chep email')}><IconMail width={15} height={15} /> Email</button>
        </div>
      </div>

      <div className="grid-2 mb-24" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title"><IconSparkles width={16} height={16} /> Thong tin phat hanh</div>
          <Info label="Ung dung" value={info?.name || 'Max-DeepSeek'} />
          <Info label="Version" value={info?.version || '1.0.0'} />
          <Info label="Channel" value={info?.channel || 'stable'} />
          <Info label="Tac gia" value={info?.author.name || 'Vu Duy Manh'} />
          <Info label="Email" value={info?.author.email || 'manhq7@gmail.com'} />
          <Info label="Repository" value={info?.repository || 'https://github.com/manhvicky/Max-DeepSeek'} />
        </div>

        <div className="card">
          <div className="card-title"><IconBookOpen width={16} height={16} /> Ho tro nguoi dung</div>
          <ul style={{ paddingLeft: 18, color: 'var(--text-dim)', lineHeight: 1.9 }}>
            <li>Neu muon cap nhat, vao muc Cap nhat de xem version moi va changelog.</li>
            <li>Neu tu host bang Docker, uu tien cap nhat qua script de co backup va rollback.</li>
            <li>Khong commit API key, database, file runtime len GitHub.</li>
            <li>Khi public repo, nen tao GitHub Release va gan tag khop voi file VERSION.</li>
          </ul>
        </div>
      </div>

      <div className="card">
        <div className="spread mb-20" style={{ gap: 12, flexWrap: 'wrap' }}>
          <div className="card-title" style={{ marginBottom: 0 }}><IconCopy width={16} height={16} /> Metadata de copy</div>
          <button className="btn btn-sm" onClick={() => copy(`Tac gia: ${info?.author.name || 'Vu Duy Manh'}\nEmail: ${info?.author.email || 'manhq7@gmail.com'}\nRepository: ${info?.repository || 'https://github.com/manhvicky/Max-DeepSeek'}`, 'Da sao chep metadata')}><IconCopy width={14} height={14} /> Sao chep</button>
        </div>
        <pre className="code-block">{`Tac gia: ${info?.author.name || 'Vu Duy Manh'}
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
