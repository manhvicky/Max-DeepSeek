import { useEffect, useState } from 'react';
import { api } from '../api';
import { IconBox } from '../icons';

const DESC: Record<string, string> = {
  'deepseek-default': 'Mô hình trò chuyện tiêu chuẩn, cân bằng tốc độ và chất lượng.',
  'deepseek-expert': 'Chế độ suy luận sâu (thinking), phù hợp bài toán phức tạp.',
  'deepseek-vision': 'Hỗ trợ đầu vào hình ảnh (đa phương thức).',
};

export default function ModelsPage() {
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.models()
      .then((r) => setModels(r.data.map((m) => m.id)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <p style={{ color: 'var(--text-dim)' }} className="mb-20">
        Các mô hình khả dụng qua endpoint <span className="code-pill">/v1/chat/completions</span>.
      </p>
      {loading ? (
        <div className="loading-full"><div className="spinner" /></div>
      ) : (
        <div className="stat-grid">
          {models.map((m) => (
            <div className="card" key={m}>
              <div className="row mb-20" style={{ gap: 10 }}>
                <div className="icon-box" style={{ position: 'static', width: 36, height: 36 }}>
                  <IconBox width={18} height={18} />
                </div>
                <div>
                  <div style={{ fontWeight: 650, fontSize: 15 }}>{m}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>DeepSeek</div>
                </div>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                {DESC[m] || 'Mô hình DeepSeek.'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
