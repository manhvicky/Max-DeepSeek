import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { clearToken, api, type StatusResp } from './api';
import {
  IconDashboard, IconUsers, IconKey, IconBox, IconList, IconSettings, IconLogout, IconBook, IconGlobe,
} from './icons';

const NAV = [
  { to: '/admin', end: true, icon: IconDashboard, label: 'Tổng quan' },
  { to: '/admin/accounts', icon: IconUsers, label: 'Tài khoản DeepSeek' },
  { to: '/admin/keys', icon: IconKey, label: 'API Key' },
  { to: '/admin/docs', icon: IconBook, label: 'Hướng dẫn' },
  { to: '/admin/models', icon: IconBox, label: 'Mô hình' },
  { to: '/admin/logs', icon: IconList, label: 'Nhật ký' },
  { to: '/admin/config', icon: IconSettings, label: 'Cấu hình' },
  { to: '/admin/proxy', icon: IconGlobe, label: 'Proxy' },
];

const BOTTOM_NAV = [
  { to: '/admin', end: true, icon: IconDashboard, label: 'Tổng quan' },
  { to: '/admin/accounts', icon: IconUsers, label: 'Tài khoản' },
  { to: '/admin/keys', icon: IconKey, label: 'API Key' },
  { to: '/admin/docs', icon: IconBook, label: 'Hướng dẫn' },
  { to: '/admin/config', icon: IconSettings, label: 'Cấu hình' },
];

const TITLES: Record<string, string> = {
  '/admin': 'Tổng quan',
  '/admin/accounts': 'Tài khoản DeepSeek',
  '/admin/keys': 'API Key',
  '/admin/docs': 'Hướng dẫn sử dụng',
  '/admin/update': 'Cập nhật hệ thống',
  '/admin/about': 'Tác giả và phát hành',
  '/admin/models': 'Mô hình',
  '/admin/logs': 'Nhật ký',
  '/admin/config': 'Cấu hình',
  '/admin/proxy': 'Quản lý Proxy',
};

export default function Layout() {
  const navigate = useNavigate();
  const path = window.location.pathname;
  const title = TITLES[path] || 'Bảng điều khiển';
  const [status, setStatus] = useState<StatusResp | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setStatus(await api.status());
      } catch {
        /* ignore */
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const logout = () => {
    clearToken();
    navigate('/admin/login');
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="logo">M</div>
          <div>
            <div className="name">Max<span>DeepSeek</span></div>
            <div className="sub">Cổng API miễn phí</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-label">Quản lý</div>
          {NAV.map((n) => {
            const Icon = n.icon;
            return (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon className="icon" />
                {n.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="nav-item" onClick={logout}>
            <IconLogout className="icon" />
            Đăng xuất
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <h1>{title}</h1>
          <div className="row" style={{ gap: 10, alignItems: 'center' }}>
            <span className="badge ok">Hệ thống hoạt động</span>
            {status && (
              <span style={{ fontSize: 13 }}>
                <span style={{ color: 'var(--green)', fontWeight: 700 }}>{status.idle + status.busy}</span>
                <span style={{ color: 'var(--text-muted)' }}>/{status.total}</span>
              </span>
            )}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>

      <nav className="bottom-nav">
        {BOTTOM_NAV.map((n) => {
          const Icon = n.icon;
          return (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon width={22} height={22} />
              <span>{n.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
