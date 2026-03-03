import React, { useEffect, useState } from "react";
import { Outlet, NavLink, Navigate, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../store";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { to: "/search", label: "Consultas", icon: "search" },
  { to: "/history", label: "Histórico", icon: "history" },
  { to: "/plans", label: "Planos", icon: "plans" },
  { to: "/settings", label: "Configurações", icon: "settings" },
];

const adminItems = [
  { to: "/admin", label: "Admin", icon: "admin" },
];

/* SVG icons for sidebar (no emojis) */
function NavIcon({ name }: { name: string }) {
  const props = { width: 18, height: 18, fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (name) {
    case "dashboard":
      return <svg {...props} viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>;
    case "search":
      return <svg {...props} viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.35-4.35" /></svg>;
    case "history":
      return <svg {...props} viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15 15" /></svg>;
    case "plans":
      return <svg {...props} viewBox="0 0 24 24"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" /></svg>;
    case "settings":
      return <svg {...props} viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></svg>;
    case "admin":
      return <svg {...props} viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>;
    default:
      return null;
  }
}

export default function AppLayout() {
  const { user, loading, fetchUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="glass" style={{ padding: "2rem 3rem" }}>
          <p style={{ color: "#fff" }}>Carregando...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const items = user.role === "super_admin" ? [...navItems, ...adminItems] : navItems;

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Mobile menu button */}
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
        {sidebarOpen ? "✕" : "☰"}
      </button>

      {/* Mobile overlay */}
      <div className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`} onClick={() => setSidebarOpen(false)} />

      {/* Sidebar – fixed position */}
      <aside
        className={`sidebar ${sidebarOpen ? "open" : ""}`}
        style={{
          width: 260,
          minWidth: 260,
          position: "fixed",
          top: 0,
          left: 0,
          bottom: 0,
          padding: "1.5rem 1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
          borderRadius: 0,
          borderRight: "1px solid rgba(45,56,71,0.3)",
          background: "rgba(14,17,28,0.92)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          zIndex: 50,
          overflowY: "auto",
        }}
      >
        <div style={{ padding: "0.5rem", marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700 }}>
            <span style={{ background: "linear-gradient(135deg, hsl(268,100%,60%), hsl(213,100%,60%))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Igarateca</span>
          </h2>
          <p style={{ color: "rgba(255,255,255,0.45)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
            {user.plano ? `Plano: ${user.plano}` : "Plano gratuito"}
          </p>
        </div>

        <nav style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className="sidebar-nav-btn"
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.65rem 0.85rem",
                borderRadius: "10px",
                textDecoration: "none",
                color: isActive ? "#fff" : "rgba(255,255,255,0.55)",
                fontSize: "0.875rem",
                fontWeight: isActive ? 600 : 400,
                transition: "all 0.3s ease",
                position: "relative",
                overflow: "hidden",
                background: isActive ? "rgba(0,112,255,0.12)" : "transparent",
                border: isActive
                  ? "1px solid rgba(0,112,255,0.25)"
                  : "1px solid transparent",
                boxShadow: isActive
                  ? "0 0 15px rgba(0,112,255,0.1), inset 0 1px 0 rgba(255,255,255,0.06)"
                  : "none",
              })}
            >
              <NavIcon name={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ borderTop: "1px solid rgba(45,56,71,0.5)", paddingTop: "1rem" }}>
          <div style={{ padding: "0.5rem 0.75rem", marginBottom: "0.5rem" }}>
            <p style={{ color: "#fff", fontSize: "0.875rem", fontWeight: 500 }}>{user.nome}</p>
            <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.75rem" }}>{user.email}</p>
            <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
              Créditos: <strong style={{ color: "#fff" }}>{user.saldo_creditos.toLocaleString("pt-BR")}</strong>
            </p>
          </div>
          <button
            className="btn btn-ghost"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={() => logout().then(() => navigate("/login"))}
          >
            Sair
          </button>
        </div>
      </aside>

      {/* Main content – offset by sidebar width, independently scrollable */}
      <main style={{ flex: 1, marginLeft: 260, minHeight: "100vh", overflowY: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
