import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken, getToken } from '../api';
import { useToast } from '../toast';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    if (getToken()) {
      navigate('/admin');
    }
  }, [navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) {
      toast('Mật khẩu tối thiểu 6 ký tự', 'err');
      return;
    }
    setLoading(true);
    try {
      const res = await api.login(password);
      setToken(res.token);
      toast('Đăng nhập thành công', 'ok');
      navigate('/admin');
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Lỗi đăng nhập', 'err');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">M</div>
        <h2>Max<span style={{ color: 'var(--accent)' }}>DeepSeek</span></h2>
        <p className="subtitle">Đăng nhập vào bảng điều khiển</p>
        <div className="login-hint">
          Mật khẩu mặc định lần đầu: <strong>123456</strong>. Sau khi đăng nhập, anh nên đổi sang mật khẩu mạnh hơn.
        </div>
        <div className="field">
          <label>Mật khẩu quản trị</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Nhập mật khẩu, mặc định 123456"
            autoFocus
          />
        </div>
        <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
          {loading ? <span className="spinner" /> : 'Đăng nhập'}
        </button>
      </form>
    </div>
  );
}
