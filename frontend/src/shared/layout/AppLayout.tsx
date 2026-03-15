import React, { useEffect, useState } from "react";
import { Outlet, NavLink, Navigate, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../store";
import Logo from "../ui/Logo";

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

const TOP_BAR_HEIGHT = 40;
const SIDEBAR_COLLAPSED = 68;
const SIDEBAR_EXPANDED = 260;
const CURRENT_PLATFORM = "entity";

const HUB_URL = import.meta.env.VITE_HUB_URL || "";
const NEXUS_URL = import.meta.env.VITE_NEXUS_URL || "";
const AMPLEX_URL = import.meta.env.VITE_AMPLEX_URL || "";

const platforms = [
  { key: "hub", name: "Hub", url: HUB_URL, icon: "🏠" },
  { key: "entity", name: "Entity", url: "", icon: "🔍" },
  { key: "amplex", name: "Amplex", url: AMPLEX_URL, icon: "📊" },
  { key: "nexus", name: "Nexus", url: NEXUS_URL, icon: "💬" },
];

export default function AppLayout() {
  const { user, loading, fetchUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [hovered, setHovered] = useState(false);

  const collapsed = !hovered;
  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED;

  useEffect(() => { fetchUser(); }, [fetchUser]);
  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="glass" style={{ padding: "2rem 3rem" }}>
          <p style={{ color: "#fff" }}>Carregando...</p>
        </div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  const items = ["admin", "super_admin"].includes(user.role) ? [...navItems, ...adminItems] : navItems;
  const visiblePlatforms = platforms.filter(p => p.key === CURRENT_PLATFORM || p.url);

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
        {sidebarOpen ? "✕" : "☰"}
      </button>
      <div className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`} onClick={() => setSidebarOpen(false)} />

      {/* Universal Top Bar */}
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, height: TOP_BAR_HEIGHT,
        background: "rgba(14,17,28,0.95)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(45,56,71,0.3)",
        display: "flex", alignItems: "center", padding: "0 1rem", zIndex: 60, gap: "0.25rem",
      }}>
        {visiblePlatforms.map(p => {
          const isCurrent = p.key === CURRENT_PLATFORM;
          return (
            <a
              key={p.key}
              href={isCurrent ? undefined : p.url}
              onClick={e => { if (isCurrent) e.preventDefault(); }}
              style={{
                display: "flex", alignItems: "center", gap: "0.4rem",
                padding: "0.3rem 0.75rem", borderRadius: "8px", textDecoration: "none",
                background: isCurrent ? "rgba(0,112,255,0.12)" : "transparent",
                border: isCurrent ? "1px solid rgba(0,112,255,0.25)" : "1px solid transparent",
                color: isCurrent ? "#fff" : "rgba(255,255,255,0.55)",
                fontSize: "0.8rem", fontWeight: isCurrent ? 600 : 400,
                transition: "all 0.2s", cursor: isCurrent ? "default" : "pointer",
              }}
              onMouseEnter={e => { if (!isCurrent) { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; e.currentTarget.style.color = "#fff"; } }}
              onMouseLeave={e => { if (!isCurrent) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "rgba(255,255,255,0.55)"; } }}
            >
              <span style={{ fontSize: "0.85rem" }}>{p.icon}</span>
              <span>{p.name}</span>
            </a>
          );
        })}
      </div>

      {/* Sidebar – collapsed by default, expands on hover */}
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{ position: "fixed", top: TOP_BAR_HEIGHT, left: 0, bottom: 0, width: sidebarWidth, zIndex: 50, transition: "width 0.25s ease" }}
      >
        <aside
          className={`sidebar ${sidebarOpen ? "open" : ""}`}
          style={{
            width: "100%", height: "100%",
            padding: collapsed ? "1.5rem 0.5rem" : "1.5rem 1rem",
            display: "flex", flexDirection: "column", gap: "0.25rem",
            borderRadius: 0, borderRight: "1px solid rgba(45,56,71,0.3)",
            background: "rgba(14,17,28,0.92)",
            backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
            overflowY: "auto", transition: "padding 0.25s ease",
            boxShadow: !collapsed ? "4px 0 20px rgba(0,0,0,0.3)" : "none",
          }}
        >
          <div style={{ padding: collapsed ? "0.5rem 0" : "0.5rem", marginBottom: "1rem", display: "flex", alignItems: "center", justifyContent: "center" }}>
            {!collapsed ? (
              <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", minWidth: 0 }}>
                <Logo size={36} style={{ flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <h2 style={{ fontSize: "1.05rem", fontWeight: 700, lineHeight: 1.2 }}>
                    <span style={{ fontFamily: "'Sansation', 'Space Grotesk', sans-serif", background: "linear-gradient(135deg, hsl(268,100%,60%), hsl(213,100%,60%))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>IgaraLead Entity</span>
                  </h2>
                  <p style={{ color: "rgba(255,255,255,0.45)", fontSize: "0.75rem", marginTop: "0.15rem" }}>
                    {user.plano ? `Plano: ${user.plano.charAt(0).toUpperCase() + user.plano.slice(1)}` : "Plano gratuito"}
                  </p>
                </div>
              </div>
            ) : (
              <Logo size={28} />
            )}
          </div>

          <nav style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className="sidebar-nav-btn"
                title={collapsed ? item.label : undefined}
                style={({ isActive }) => ({
                  display: "flex", alignItems: "center",
                  gap: collapsed ? 0 : "0.75rem",
                  justifyContent: collapsed ? "center" : "flex-start",
                  padding: collapsed ? "0.65rem" : "0.65rem 0.85rem",
                  borderRadius: "10px", textDecoration: "none",
                  color: isActive ? "#fff" : "rgba(255,255,255,0.55)",
                  fontSize: "0.875rem", fontWeight: isActive ? 600 : 400,
                  transition: "all 0.3s ease", position: "relative", overflow: "hidden",
                  background: isActive ? "rgba(0,112,255,0.12)" : "transparent",
                  border: isActive ? "1px solid rgba(0,112,255,0.25)" : "1px solid transparent",
                  boxShadow: isActive ? "0 0 15px rgba(0,112,255,0.1), inset 0 1px 0 rgba(255,255,255,0.06)" : "none",
                })}
              >
                <NavIcon name={item.icon} />
                {!collapsed && item.label}
              </NavLink>
            ))}
          </nav>

          <div style={{ borderTop: "1px solid rgba(45,56,71,0.5)", paddingTop: "1rem", marginTop: "0.5rem" }}>
            {!collapsed ? (
              <>
                <div style={{ padding: "0.5rem 0.75rem", marginBottom: "0.5rem" }}>
                  <p style={{ color: "#fff", fontSize: "0.875rem", fontWeight: 500 }}>{user.nome}</p>
                  <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.75rem" }}>{user.email}</p>
                  <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                    Créditos: <strong style={{ color: "#fff" }}>{user.saldo_creditos.toLocaleString("pt-BR")}</strong>
                  </p>
                </div>
                <button className="btn btn-ghost" style={{ width: "100%", justifyContent: "center" }} onClick={() => logout().then(() => navigate("/login"))}>
                  Sair
                </button>
              </>
            ) : (
              <button
                className="btn btn-ghost"
                style={{ width: "100%", justifyContent: "center", padding: "0.5rem" }}
                title={`${user.nome} · ${user.saldo_creditos} créditos`}
                onClick={() => logout().then(() => navigate("/login"))}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </button>
            )}
          </div>
        </aside>
      </div>

      {/* Main content – fixed offset by collapsed sidebar width */}
      <main style={{ flex: 1, marginLeft: SIDEBAR_COLLAPSED, marginTop: TOP_BAR_HEIGHT, minHeight: `calc(100vh - ${TOP_BAR_HEIGHT}px)`, overflowY: "auto", display: "flex", flexDirection: "column" }}>
        <div style={{ flex: 1 }}>
          <Outlet />
        </div>
        <footer style={{
          padding: "1rem 2rem", textAlign: "center",
          color: "rgba(255,255,255,0.35)", fontSize: "0.75rem",
          borderTop: "1px solid rgba(45,56,71,0.3)",
        }}>
          © {new Date().getFullYear()}{" "}
          <a
            href="https://igaralead.com.br"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "rgba(255,255,255,0.55)", textDecoration: "none", fontWeight: 500 }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#fff")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.55)")}
          >
            IgaraLead
          </a>
          . Todos os direitos reservados.
        </footer>
      </main>
    </div>
  );
}
