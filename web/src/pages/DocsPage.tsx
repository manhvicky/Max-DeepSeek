import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { useToast } from '../toast';
import { IconCheck, IconKey, IconBox, IconZap, IconCopy } from '../icons';

const BASE_URL = 'http://192.168.1.43:22218/v1';
const CHAT_URL = 'http://192.168.1.43:22218/v1/chat/completions';
const MODELS_URL = 'http://192.168.1.43:22218/v1/models';
const FALLBACK_KEY = 'HÃY_TẠO_API_KEY_TRƯỚC';
const MASK_NOTE = 'Nếu key bị ẩn một phần, vào trang API Key tạo key mới rồi sao chép key đầy đủ.';

function CodeBlock({ children }: { children: string }) {
  return (
    <pre style={{
      background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10,
      padding: 14, overflowX: 'auto', color: 'var(--text-dim)', fontSize: 13,
      lineHeight: 1.6, marginTop: 10,
    }}><code>{children}</code></pre>
  );
}

function Step({ n, title, text }: { n: number; title: string; text: string }) {
  return (
    <div className="card">
      <div className="row mb-20" style={{ alignItems: 'flex-start' }}>
        <div className="icon-box" style={{ position: 'static', width: 34, height: 34 }}>{n}</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
          <p style={{ color: 'var(--text-dim)', marginTop: 4 }}>{text}</p>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="spread" style={{ padding: '11px 0', borderBottom: '1px solid var(--border-soft)', gap: 14 }}>
      <span style={{ color: 'var(--text-dim)' }}>{label}</span>
      <span className="code-pill" style={{ wordBreak: 'break-all', textAlign: 'right' }}>{value}</span>
    </div>
  );
}

export default function DocsPage() {
  const [apiKey, setApiKey] = useState(FALLBACK_KEY);
  const [hasKey, setHasKey] = useState(false);
  const toast = useToast();

  useEffect(() => {
    api.keys()
      .then((keys) => {
        const first = keys.find((k) => k.is_active) || keys[0];
        if (first?.key) {
          setApiKey(first.key);
          setHasKey(true);
        }
      })
      .catch(() => {});
  }, []);

  const aiPrompt = useMemo(() => `Hãy cấu hình ứng dụng AI của tôi dùng OpenAI-compatible API với thông tin sau:

Base URL: ${BASE_URL}
API Key: ${apiKey}
Model chat nhanh: deepseek-default
Model suy luận sâu/thinking: deepseek-expert
Model vision: deepseek-vision
Chat endpoint đầy đủ: ${CHAT_URL}
Models endpoint: ${MODELS_URL}
Header: Authorization: Bearer ${apiKey}

Yêu cầu:
1. Nếu ứng dụng có mục Provider, chọn OpenAI hoặc OpenAI-compatible.
2. Điền Base URL đúng là ${BASE_URL}, không tự thêm /chat/completions nếu ô đó chỉ hỏi Base URL.
3. Điền API Key ở trên.
4. Thêm model deepseek-default và deepseek-expert nếu ứng dụng không tự tải danh sách model.
5. Bật streaming nếu ứng dụng hỗ trợ.
6. Kiểm tra bằng một câu chat ngắn sau khi cấu hình xong.

${hasKey ? '' : MASK_NOTE}`.trim(), [apiKey, hasKey]);

  const copy = (text: string, message = 'Đã sao chép') => {
    navigator.clipboard.writeText(text);
    toast(message, 'ok');
  };

  return (
    <div>
      <div className="card mb-24" style={{
        background: 'linear-gradient(135deg, rgba(234,88,12,.18), var(--card))',
        borderColor: 'rgba(249,115,22,.35)',
      }}>
        <div className="row" style={{ alignItems: 'flex-start', justifyContent: 'space-between', gap: 18, flexWrap: 'wrap' }}>
          <div style={{ maxWidth: 760 }}>
            <div className="badge ok" style={{ marginBottom: 12 }}>OpenAI-compatible</div>
            <h2 style={{ fontSize: 26, letterSpacing: '-0.02em', marginBottom: 8 }}>Hướng dẫn kết nối Max-DeepSeek</h2>
            <p style={{ color: 'var(--text-dim)', fontSize: 15, lineHeight: 1.7 }}>
              Dùng API key tạo trong trang này để kết nối Cursor, Cherry Studio, Open WebUI hoặc code riêng.
              Endpoint tương thích chuẩn OpenAI, chỉ cần đổi Base URL và API Key.
            </p>
          </div>
          <div className="icon-box" style={{ position: 'static', width: 54, height: 54 }}><IconZap width={24} height={24} /></div>
        </div>
      </div>

      <div className="stat-grid mb-24">
        <Step n={1} title="Thêm tài khoản DeepSeek" text="Vào Tài khoản DeepSeek, thêm email/số điện thoại + mật khẩu. Hệ thống tự đăng nhập và đưa account vào pool." />
        <Step n={2} title="Tạo API Key" text="Vào API Key, bấm Tạo API Key. Sao chép key ngay vì key đầy đủ chỉ hiện một lần." />
        <Step n={3} title="Kết nối ứng dụng" text="Trong app cần dùng AI, chọn OpenAI-compatible rồi nhập Base URL, API Key và model bên dưới." />
      </div>

      <div className="grid-2 mb-24" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title"><IconKey width={16} height={16} /> Thông tin kết nối</div>
          <Info label="Base URL" value={BASE_URL} />
          <Info label="Chat endpoint" value={CHAT_URL} />
          <Info label="Models endpoint" value={MODELS_URL} />
          <Info label="API Key đang dùng" value={apiKey} />
          <Info label="Header" value={`Authorization: Bearer ${apiKey}`} />
          <Info label="Định dạng" value="OpenAI Chat Completions" />
        </div>
        <div className="card">
          <div className="card-title"><IconBox width={16} height={16} /> Model nên dùng</div>
          <Info label="Chat nhanh" value="deepseek-default" />
          <Info label="Suy luận sâu" value="deepseek-expert" />
          <Info label="Đa phương thức" value="deepseek-vision" />
          <p style={{ color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.7, marginTop: 12 }}>
            Nếu app chỉ cho nhập một model, dùng <span className="code-pill">deepseek-default</span> trước. Khi cần thinking, đổi sang <span className="code-pill">deepseek-expert</span>.
          </p>
        </div>
      </div>

      <div className="card mb-24">
        <div className="card-title"><IconCheck width={16} height={16} /> Cấu hình Cursor / Cherry Studio / Open WebUI</div>
        <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
          <div>
            <div style={{ fontWeight: 650, marginBottom: 8 }}>Cursor</div>
            <p style={{ color: 'var(--text-dim)', lineHeight: 1.7 }}>
              Settings → Models → Add OpenAI-compatible provider. Điền Base URL <span className="code-pill">{BASE_URL}</span>, API key đã tạo, model <span className="code-pill">deepseek-default</span>.
            </p>
          </div>
          <div>
            <div style={{ fontWeight: 650, marginBottom: 8 }}>Cherry Studio</div>
            <p style={{ color: 'var(--text-dim)', lineHeight: 1.7 }}>
              Providers → Add Provider → OpenAI. API Host nhập <span className="code-pill">{BASE_URL}</span>, API Key nhập key, model nhập thủ công nếu chưa tự hiện.
            </p>
          </div>
          <div>
            <div style={{ fontWeight: 650, marginBottom: 8 }}>Open WebUI / LibreChat</div>
            <p style={{ color: 'var(--text-dim)', lineHeight: 1.7 }}>
              Thêm connection OpenAI-compatible. Base URL dùng <span className="code-pill">{BASE_URL}</span>. Nếu app yêu cầu endpoint gốc, không thêm <span className="code-pill">/chat/completions</span>.
            </p>
          </div>
        </div>
      </div>

      <div className="grid-2 mb-24" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title">Ví dụ curl</div>
          <CodeBlock>{`curl ${CHAT_URL} \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "deepseek-default",
    "messages": [
      {"role": "user", "content": "Xin chào"}
    ],
    "stream": false
  }'`}</CodeBlock>
        </div>
        <div className="card">
          <div className="card-title">Ví dụ Python</div>
          <CodeBlock>{`from openai import OpenAI

client = OpenAI(
    api_key="${apiKey}",
    base_url="${BASE_URL}",
)

resp = client.chat.completions.create(
    model="deepseek-default",
    messages=[{"role": "user", "content": "Xin chào"}],
)
print(resp.choices[0].message.content)`}</CodeBlock>
        </div>
      </div>

      <div className="card mb-24">
        <div className="spread mb-20" style={{ gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <div className="card-title" style={{ marginBottom: 6 }}><IconCopy width={16} height={16} /> Prompt đưa cho AI cài nhanh</div>
            <p style={{ color: 'var(--text-dim)', lineHeight: 1.7 }}>
              Sao chép ô này rồi gửi cho AI/Copilot/Cursor để nó tự cấu hình provider cho anh.
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => copy(aiPrompt, 'Đã sao chép prompt cài nhanh')}>
            <IconCopy width={15} height={15} /> Sao chép prompt
          </button>
        </div>
        <CodeBlock>{aiPrompt}</CodeBlock>
        {!hasKey && (
          <p style={{ color: 'var(--yellow)', fontSize: 13, marginTop: 10 }}>
            Chưa tìm thấy API key hoạt động. Vào trang API Key tạo key trước, rồi quay lại đây.
          </p>
        )}
      </div>

      <div className="card">
        <div className="card-title">Lưu ý vận hành</div>
        <ul style={{ color: 'var(--text-dim)', lineHeight: 1.9, paddingLeft: 18 }}>
          <li>Nên thêm nhiều tài khoản DeepSeek để pool xoay vòng, giảm lỗi quá tải/rate-limit.</li>
          <li>API key là bí mật. Không gửi key cho người khác, không commit lên GitHub.</li>
          <li>Nếu gặp 401, kiểm tra API key còn hoạt động. Nếu gặp 429/overloaded, thêm account hoặc chờ cooldown.</li>
          <li>Streaming được hỗ trợ. App như Cursor/Cherry Studio có thể bật stream bình thường.</li>
        </ul>
      </div>
    </div>
  );
}
