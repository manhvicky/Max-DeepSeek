import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './toast';
import { getToken } from './api';
import Layout from './Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AccountsPage from './pages/AccountsPage';
import KeysPage from './pages/KeysPage';
import ModelsPage from './pages/ModelsPage';
import LogsPage from './pages/LogsPage';
import ConfigPage from './pages/ConfigPage';
import DocsPage from './pages/DocsPage';
import ProxyPage from './pages/ProxyPage';
import './styles.css';

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/admin/login" replace />;
  return <>{children}</>;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/admin/login" element={<LoginPage />} />
          <Route
            path="/admin"
            element={<RequireAuth><Layout /></RequireAuth>}
          >
            <Route index element={<DashboardPage />} />
            <Route path="accounts" element={<AccountsPage />} />
            <Route path="keys" element={<KeysPage />} />
            <Route path="docs" element={<DocsPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="config" element={<ConfigPage />} />
            <Route path="proxy" element={<ProxyPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </StrictMode>
);
