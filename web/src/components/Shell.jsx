/** Umumiy karkas: chap navigatsiya + kontent. */

import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { brandModel, brandProvider } from "../brand";
import { useAuth } from "../context/AuthContext";

export default function Shell({ children, sidebarExtra = null, wide = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  function closeMobile() {
    setMobileOpen(false);
  }

  return (
    <section className={`app${wide ? " with-artifact" : ""}`}>
      <button
        className="menu-btn icon-btn"
        onClick={() => setMobileOpen((v) => !v)}
        title="Menyu"
      >
        ☰
      </button>

      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={closeMobile} />
      )}

      <aside className={`sidebar glass${mobileOpen ? " open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>CodeAssistant</strong>
            <small>
              {user?.ai_provider
                ? `${brandProvider(user.ai_provider)} · ${brandModel(user.ai_model)}`
                : "standart model"}
            </small>
          </div>
        </div>

        <nav className="nav stagger">
          <NavLink to="/chat" className="nav-link anim-left" onClick={closeMobile}>
            💬 Suhbat
          </NavLink>
          <NavLink to="/models" className="nav-link anim-left" onClick={closeMobile}>
            ◆ Modellar
          </NavLink>
          <NavLink to="/artifacts" className="nav-link anim-left" onClick={closeMobile}>
            ◫ Saytlarim
          </NavLink>
          <NavLink to="/download" className="nav-link anim-left" onClick={closeMobile}>
            ⤓ Yuklab olish
          </NavLink>
          {user?.role === "admin" && (
            <NavLink to="/admin" className="nav-link anim-left" onClick={closeMobile}>
              ⚙︎ Foydalanuvchilar
            </NavLink>
          )}
        </nav>

        {sidebarExtra}

        <div className="sidebar-foot">
          <div className="user-row">
            <div className="avatar">
              {user?.username.slice(0, 2).toUpperCase()}
            </div>
            <div className="user-meta">
              <b>{user?.username}</b>
              <div className="badges">
                {user?.role === "admin" && (
                  <span className="pill pill-admin">admin</span>
                )}
                <span className={`pill${user?.ai_in_pc ? " pill-on" : ""}`}>
                  {user?.ai_in_pc ? "ai_in_pc" : "ai_in_pc o'chiq"}
                </span>
              </div>
            </div>
          </div>
          <button className="btn btn-ghost" onClick={handleLogout}>
            Chiqish
          </button>
        </div>
      </aside>

      {children}
    </section>
  );
}
