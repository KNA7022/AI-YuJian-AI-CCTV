import { Link, NavLink } from "react-router-dom";
import { ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          <span className="brand-mark">GB</span>
          <span>
            <span className="brand-kicker">Good Badminton</span>
            <strong>视频复盘控制台</strong>
          </span>
        </Link>
        <nav className="nav">
          <NavLink to="/live" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            球场直播
          </NavLink>
          <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            上传分析
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            历史记录
          </NavLink>
        </nav>
      </header>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
