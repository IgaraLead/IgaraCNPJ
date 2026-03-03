import React, { useEffect, useState } from "react";
import { Outlet, NavLink, Navigate, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../store";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/search", label: "Consultas", icon: "🔍" },
  { to: "/history", label: "Histórico", icon: "📋" },
  { to: "/plans", label: "Planos", icon: "💎" },
  { to: "/settings", label: "Configurações", icon: "⚙️" },
];

const adminItems = [
  { to: "/admin", label: "Admin", icon: "🛡️" },
];

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

      {/* Sidebar */}
      <aside
        className={`glass-strong sidebar ${sidebarOpen ? "open" : ""}`}
        style={{
          width: "var(--sidebar-width, 260px)",
          minWidth: 260,
          padding: "1.5rem 1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
          borderRadius: 0,
          borderRight: "1px solid rgba(45,56,71,0.5)",
          background: "rgba(26,31,46,0.85)",
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

        <nav style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.625rem 0.75rem",
                borderRadius: "8px",
                textDecoration: "none",
                color: isActive ? "#fff" : "rgba(255,255,255,0.55)",
                background: isActive ? "rgba(0,112,255,0.15)" : "transparent",
                fontSize: "0.875rem",
                fontWeight: isActive ? 600 : 400,
                transition: "all 0.15s",
              })}
            >
              <span>{item.icon}</span>
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

      {/* Main content */}
      <main style={{ flex: 1, overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
