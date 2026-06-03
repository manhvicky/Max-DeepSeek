import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken, getToken } from '../api';
import { useToast } from '../toast';

export default function LoginPage() {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [isSetup, setIsSetup] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    if (getToken()) { navigate('/admin'); return; }
    // kiểm tra đã đặt mật khẩu chưa
    fetch('/admin/api/config').then((r) => {
      // 401 = đã đặt mật khẩu (cần auth); khác = chưa
      setIsSetup(r.status !== 401);
      setChecking(false);
    }).catch(() => setChecking(false));
  }, [navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSetup && password !== confirm) {
      toast('Mật khẩu nhập lại không khớp', 'err');
      return;
    }
    if (password.length < 6) {
      toast('Mật khẩu tối thiểu 6 ký tự', 'err');
      return;
    }
    setLoading(true);
    try {
      const res = isSetup ? await api.setup(password) : await api.login(password);
      setToken(res.token);
      toast(isSetup ? 'Đã tạo mật khẩu admin' : 'Đăng nhập thành công', 'ok');
      navigate('/admin');
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Lỗi đăng nhập', 'err');
    } finally {
      setLoading(false);
    }
  };

  if (checking) {
    return <div className="login-shell"><div className="spinner" /></div>;
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">M</div>
        <h2>Max<span style={{ color: 'var(--accent)' }}>DeepSeek</span></h2>
        <p className="subtitle">
          {isSetup ? 'Tạo mật khẩu quản trị lần đầu' : 'Đăng nhập vào bảng điều khiển'}
        </p>
        <div className="field">
          <label>Mật khẩu quản trị</label>
          <input
            className="input" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Nhập mật khẩu" autoFocus
          />
        </div>
        {isSetup && (
          <div className="field">
            <label>Nhập lại mật khẩu</label>
            <input
              className="input" type="password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Nhập lại mật khẩu"
            />
          </div>
        )}
        <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
          {loading ? <span className="spinner" /> : (isSetup ? 'Tạo & đăng nhập' : 'Đăng nhập')}
        </button>
      </form>
    </div>
  );
}
