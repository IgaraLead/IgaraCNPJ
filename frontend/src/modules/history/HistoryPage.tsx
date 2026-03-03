import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { creditsApi } from "../../shared/api";

type TabType = "searches" | "credits";

export default function HistoryPage() {
  const [tab, setTab] = useState<TabType>("searches");
  const { data: transactions, isLoading } = useQuery({
    queryKey: ["transactions"],
    queryFn: creditsApi.transactions,
  });

  const searchTransactions = (transactions || []).filter(
    (t) => t.tipo === "consumo" && t.motivo
  );
  const allTransactions = transactions || [];

  return (
    <div className="page animate-in">
      <h1 className="page-title">Histórico</h1>

      {/* Tab switcher */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          className={`btn ${tab === "searches" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setTab("searches")}
        >
          🔍 Consultas
        </button>
        <button
          className={`btn ${tab === "credits" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setTab("credits")}
        >
          💰 Transações de Crédito
        </button>
      </div>

      <div className="glass-strong" style={{ padding: "1.5rem" }}>
        {isLoading ? (
          <p style={{ color: "rgba(255,255,255,0.5)" }}>Carregando...</p>
        ) : tab === "searches" ? (
          /* Search History Tab */
          !searchTransactions.length ? (
            <p style={{ color: "rgba(255,255,255,0.5)" }}>Nenhuma consulta realizada ainda.</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Data</th>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Descrição</th>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Resultados</th>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Créditos</th>
                  </tr>
                </thead>
                <tbody>
                  {searchTransactions.map((t) => (
                    <tr key={t.id}>
                      <td style={{ color: "rgba(255,255,255,0.7)", fontSize: "0.875rem" }}>
                        {new Date(t.created_at).toLocaleString("pt-BR")}
                      </td>
                      <td style={{ color: "rgba(255,255,255,0.85)", fontSize: "0.875rem" }}>
                        {t.motivo || "—"}
                      </td>
                      <td style={{ color: "rgba(255,255,255,0.7)", fontSize: "0.875rem" }}>
                        {Math.abs(t.quantidade)}
                      </td>
                      <td style={{ color: "#fca5a5", fontWeight: 600 }}>
                        −{Math.abs(t.quantidade).toLocaleString("pt-BR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          /* Credit Transactions Tab */
          !allTransactions.length ? (
            <p style={{ color: "rgba(255,255,255,0.5)" }}>Nenhuma transação encontrada.</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Data</th>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Tipo</th>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Quantidade</th>
                    <th style={{ color: "rgba(255,255,255,0.5)" }}>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {allTransactions.map((t) => (
                    <tr key={t.id}>
                      <td style={{ color: "rgba(255,255,255,0.7)", fontSize: "0.875rem" }}>
                        {new Date(t.created_at).toLocaleString("pt-BR")}
                      </td>
                      <td>
                        <span className={`badge ${t.tipo === "consumo" ? "badge-warning" : t.tipo === "ajuste_manual" ? "badge-danger" : "badge-success"}`}>
                          {t.tipo}
                        </span>
                      </td>
                      <td style={{ color: t.quantidade < 0 ? "#fca5a5" : "#86efac", fontWeight: 600 }}>
                        {t.quantidade > 0 ? "+" : ""}{t.quantidade.toLocaleString("pt-BR")}
                      </td>
                      <td style={{ color: "rgba(255,255,255,0.7)", fontSize: "0.875rem" }}>
                        {t.motivo || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </div>
  );
}
