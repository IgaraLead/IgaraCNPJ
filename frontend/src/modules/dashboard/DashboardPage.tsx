import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../shared/store";
import { creditsApi } from "../../shared/api";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: credits } = useQuery({ queryKey: ["credits"], queryFn: creditsApi.balance });
  const { data: transactions } = useQuery({ queryKey: ["transactions"], queryFn: creditsApi.transactions });

  const recentTransactions = (transactions || []).slice(0, 5);

  // Build simple consumption chart from last 7 days of transactions
  const consumptionByDay = React.useMemo(() => {
    const days: Record<string, number> = {};
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const key = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
      days[key] = 0;
    }
    for (const t of transactions || []) {
      if (t.tipo === "consumo") {
        const d = new Date(t.created_at);
        const key = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
        if (key in days) {
          days[key] += Math.abs(t.quantidade);
        }
      }
    }
    return Object.entries(days);
  }, [transactions]);

  const maxConsumption = Math.max(1, ...consumptionByDay.map(([, v]) => v));

  return (
    <div className="page animate-in">
      <h1 className="page-title">Dashboard</h1>

      {/* Stats Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        <StatCard label="Créditos Disponíveis" value={credits?.saldo?.toLocaleString("pt-BR") ?? "0"} icon="💰" />
        <StatCard label="Plano Atual" value={user?.plano ? user.plano.charAt(0).toUpperCase() + user.plano.slice(1) : "Gratuito"} icon="💎" />
        <StatCard label="Créditos Consumidos" value={credits?.creditos_consumidos?.toLocaleString("pt-BR") ?? "0"} icon="📉" />
        <StatCard label="Status Assinatura" value={user?.status_assinatura ?? "—"} icon="✅" />
      </div>

      {/* Consumption Chart */}
      <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
        <h2 style={{ color: "#fff", fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>
          Consumo (últimos 7 dias)
        </h2>
        <div style={{ display: "flex", alignItems: "flex-end", gap: "0.5rem", height: 120 }}>
          {consumptionByDay.map(([label, value]) => (
            <div key={label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem" }}>
              <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.7rem" }}>
                {value > 0 ? value.toLocaleString("pt-BR") : ""}
              </span>
              <div
                style={{
                  width: "100%",
                  maxWidth: 48,
                  height: `${Math.max(4, (value / maxConsumption) * 80)}px`,
                  background: "linear-gradient(to top, hsl(268,100%,60%), hsl(213,100%,60%))",
                  borderRadius: "4px 4px 0 0",
                  transition: "height 0.3s ease",
                }}
              />
              <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.65rem" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Queries */}
      <div className="glass-strong" style={{ padding: "1.5rem" }}>
        <h2 style={{ color: "#fff", fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" }}>
          Atividade Recente
        </h2>
        {recentTransactions.length === 0 ? (
          <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>Nenhuma atividade encontrada.</p>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ color: "rgba(255,255,255,0.6)" }}>Tipo</th>
                  <th style={{ color: "rgba(255,255,255,0.6)" }}>Quantidade</th>
                  <th style={{ color: "rgba(255,255,255,0.6)" }}>Motivo</th>
                  <th style={{ color: "rgba(255,255,255,0.6)" }}>Data</th>
                </tr>
              </thead>
              <tbody>
                {recentTransactions.map((t) => (
                  <tr key={t.id}>
                    <td style={{ color: "#fff" }}>
                      <span className={`badge ${t.tipo === "consumo" ? "badge-warning" : "badge-success"}`}>
                        {t.tipo}
                      </span>
                    </td>
                    <td style={{ color: t.quantidade < 0 ? "#fca5a5" : "#86efac", fontWeight: 600 }}>
                      {t.quantidade > 0 ? "+" : ""}{t.quantidade.toLocaleString("pt-BR")}
                    </td>
                    <td style={{ color: "rgba(255,255,255,0.7)", fontSize: "0.875rem" }}>{t.motivo || "—"}</td>
                    <td style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>
                      {new Date(t.created_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="glass-strong" style={{ padding: "1.25rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.8rem" }}>{label}</span>
        <span style={{ fontSize: "1.25rem" }}>{icon}</span>
      </div>
      <p style={{ color: "#fff", fontSize: "1.5rem", fontWeight: 700 }}>{value}</p>
    </div>
  );
}
