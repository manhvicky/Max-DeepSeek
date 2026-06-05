import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { clearToken, api, type StatusResp } from './api';
import {
  IconDashboard, IconUsers, IconKey, IconBox, IconList, IconSettings, IconLogout, IconBook, IconGlobe, IconRefresh, IconSparkles,
} from './icons';

const NAV = [
  { to: '/admin', end: true, icon: IconDashboard, label: 'Tong quan' },
  { to: '/admin/accounts', icon: IconUsers, label: 'Tai khoan DeepSeek' },
  { to: '/admin/keys', icon: IconKey, label: 'API Key' },
  { to: '/admin/docs', icon: IconBook, label: 'Huong dan' },
  { to: '/admin/update', icon: IconRefresh, label: 'Cap nhat' },
  { to: '/admin/about', icon: IconSparkles, label: 'Tac gia' },
  { to: '/admin/models', icon: IconBox, label: 'Mo hinh' },
  { to: '/admin/logs', icon: IconList, label: 'Nhat ky' },
  { to: '/admin/config', icon: IconSettings, label: 'Cau hinh' },
  { to: '/admin/proxy', icon: IconGlobe, label: 'Proxy' },
];

const BOTTOM_NAV = [
  { to: '/admin', end: true, icon: IconDashboard, label: 'Tong quan' },
  { to: '/admin/accounts', icon: IconUsers, label: 'Tai khoan' },
  { to: '/admin/keys', icon: IconKey, label: 'API Key' },
  { to: '/admin/update', icon: IconRefresh, label: 'Cap nhat' },
  { to: '/admin/about', icon: IconSparkles, label: 'Tac gia' },
  { to: '/admin/config', icon: IconSettings, label: 'Cau hinh' },
];

const TITLES: Record<string, string> = {
  '/admin': 'Tong quan',
  '/admin/accounts': 'Tai khoan DeepSeek',
  '/admin/keys': 'API Key',
  '/admin/docs': 'Huong dan su dung',
  '/admin/update': 'Cap nhat he thong',
  '/admin/about': 'Tac gia va phat hanh',
  '/admin/models': 'Mo hinh',
  '/admin/logs': 'Nhat ky',
  '/admin/config': 'Cau hinh',
  '/admin/proxy': 'Quan ly Proxy',
};

export default function Layout() {
  const navigate = useNavigate();
  const path = window.location.pathname;
  const title = TITLES[path] || 'Bảng điều khiển';
  const [status, setStatus] = useState<StatusResp | null>(null);

  useEffect(() => {
    const load = async () => {
      try { setStatus(await api.status()); } catch { /* ignore */ }
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
      {/* Sidebar desktop */}
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

      {/* Bottom nav mobile */}
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
