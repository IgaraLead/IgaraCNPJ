import { useState, useEffect, useRef } from "react";

interface Product {
  key: string;
  name: string;
  description: string;
  url: string;
  icon: string;
  color: string;
}

const HUB_URL = import.meta.env.VITE_HUB_URL || "http://localhost:8001";
const NEXUS_URL = import.meta.env.VITE_NEXUS_URL || "";
const AMPLEX_URL = import.meta.env.VITE_AMPLEX_URL || "";

const PRODUCTS: Product[] = [
  { key: "hub", name: "Hub", description: "Painel Central", url: HUB_URL, icon: "🏠", color: "#0070ff" },
  { key: "amplex", name: "Amplex", description: "CRM", url: AMPLEX_URL, icon: "📊", color: "#10b981" },
  { key: "nexus", name: "Nexus", description: "Atendimento", url: NEXUS_URL, icon: "💬", color: "#8b5cf6" },
  { key: "entity", name: "Entity", description: "Dados CNPJ", url: "", icon: "🔍", color: "#f59e0b" },
];

export default function ProductSwitcher() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const products = PRODUCTS.filter(p => p.key === "entity" || p.key === "hub" || p.url);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        title="Alternar entre plataformas"
        style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          width: 36, height: 36, borderRadius: "10px",
          background: open ? "rgba(0,112,255,0.15)" : "rgba(255,255,255,0.06)",
          border: open ? "1px solid rgba(0,112,255,0.3)" : "1px solid rgba(45,56,71,0.4)",
          color: "#e2e8f0", cursor: "pointer", transition: "all 0.2s",
        }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = "rgba(255,255,255,0.1)"; }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = "rgba(255,255,255,0.06)"; }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 8px)", right: 0, zIndex: 1000,
          width: 260, padding: "8px",
          background: "rgba(14,17,28,0.97)", border: "1px solid rgba(45,56,71,0.5)",
          borderRadius: "14px", backdropFilter: "blur(20px)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        }}>
          <p style={{
            fontSize: "0.65rem", fontWeight: 600, textTransform: "uppercase",
            letterSpacing: "0.1em", color: "rgba(255,255,255,0.35)",
            padding: "8px 10px 4px", margin: 0,
          }}>
            Plataformas
          </p>
          {products.map(p => {
            const isCurrent = p.key === "entity";
            return (
              <a
                key={p.key}
                href={isCurrent ? undefined : p.url}
                onClick={e => { if (isCurrent) e.preventDefault(); else setOpen(false); }}
                style={{
                  display: "flex", alignItems: "center", gap: "10px",
                  padding: "10px", borderRadius: "10px", textDecoration: "none",
                  background: isCurrent ? "rgba(0,112,255,0.1)" : "transparent",
                  border: isCurrent ? "1px solid rgba(0,112,255,0.2)" : "1px solid transparent",
                  transition: "all 0.15s", cursor: isCurrent ? "default" : "pointer",
                }}
                onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.background = "rgba(255,255,255,0.06)"; }}
                onMouseLeave={e => { if (!isCurrent) e.currentTarget.style.background = isCurrent ? "rgba(0,112,255,0.1)" : "transparent"; }}
              >
                <span style={{
                  width: 34, height: 34, borderRadius: "9px",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: `${p.color}18`, fontSize: "1.1rem", flexShrink: 0,
                }}>
                  {p.icon}
                </span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: 0, color: "#fff", fontSize: "0.85rem", fontWeight: 600 }}>{p.name}</p>
                  <p style={{ margin: 0, color: "rgba(255,255,255,0.45)", fontSize: "0.7rem" }}>{p.description}</p>
                </div>
                {isCurrent && (
                  <span style={{
                    marginLeft: "auto", fontSize: "0.6rem", fontWeight: 600,
                    color: "#0070ff", background: "rgba(0,112,255,0.12)",
                    padding: "2px 8px", borderRadius: "6px",
                  }}>
                    ATUAL
                  </span>
                )}
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
