import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { creditsApi, searchApi, type SearchHistory } from "../../shared/api";

type TabType = "searches" | "credits";

function summarizeParams(params: Record<string, unknown>): string {
  const parts: string[] = [];
  if (params.uf) parts.push(`UF: ${params.uf}`);
  if (params.municipio) {
    const codes = String(params.municipio).split(",");
    parts.push(`${codes.length} município${codes.length > 1 ? "s" : ""}`);
  }
  if (params.cnae) parts.push(`CNAE: ${params.cnae}`);
  if (params.situacao) {
    const map: Record<string, string> = { "2": "Ativa", "3": "Suspensa", "4": "Inapta", "8": "Baixada" };
    parts.push(map[String(params.situacao)] || `Sit: ${params.situacao}`);
  }
  if (params.porte) parts.push(`Porte: ${params.porte}`);
  if (params.q) parts.push(`"${params.q}"`);
  if (params.bairro) parts.push(`Bairro: ${params.bairro}`);
  if (params.ddd) parts.push(`DDD: ${params.ddd}`);
  if (params.com_email === true) parts.push("Com e-mail");
  if (params.com_telefone === true) parts.push("Com telefone");
  if (params.simples === "S") parts.push("Simples");
  if (params.mei === "S") parts.push("MEI");
  return parts.length > 0 ? parts.join(" · ") : "Busca geral";
}

export default function HistoryPage() {
  const [tab, setTab] = useState<TabType>("searches");
  const navigate = useNavigate();

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["searchHistory"],
    queryFn: () => searchApi.history(50),
  });

  const { data: transactions, isLoading: txLoading } = useQuery({
    queryKey: ["transactions"],
    queryFn: creditsApi.transactions,
  });

  const allTransactions = transactions || [];

  const handleContinue = (entry: SearchHistory) => {
    navigate("/search", { state: { params: entry.params, mode: "continue" } });
  };

  const handleReuse = (entry: SearchHistory) => {
    navigate("/search", { state: { params: entry.params, mode: "reuse" } });
  };

  return (
    <div className="page animate-in">
      <h1 className="page-title">Histórico</h1>

      {/* Tab switcher */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          className={`btn ${tab === "searches" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setTab("searches")}
        >
          Consultas
        </button>
        <button
          className={`btn ${tab === "credits" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setTab("credits")}
        >
          Transações de Crédito
        </button>
      </div>

      <div className="glass-strong" style={{ padding: "1.5rem" }}>
        {tab === "searches" ? (
          /* Search History Tab */
          historyLoading ? (
            <p style={{ color: "rgba(255,255,255,0.5)" }}>Carregando...</p>
          ) : !history?.length ? (
            <p style={{ color: "rgba(255,255,255,0.5)" }}>Nenhuma consulta realizada ainda.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {history.map((entry) => (
                <div
                  key={entry.id}
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid var(--glass-border)",
                    borderRadius: "var(--radius-sm)",
                    padding: "1rem 1.25rem",
                    cursor: "pointer",
                    transition: "background 0.15s",
                  }}
                  onClick={() => handleContinue(entry)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.07)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.03)")}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.375rem" }}>
                        <span style={{ color: "var(--primary)", fontWeight: 600, fontSize: "0.8rem", letterSpacing: "0.02em" }}>
                          #{entry.search_id}
                        </span>
                        <span className={`badge ${entry.status === "realizada" ? "badge-success" : "badge-warning"}`} style={{ fontSize: "0.7rem" }}>
                          {entry.status}
                        </span>
                      </div>
                      <p style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.85rem", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {summarizeParams(entry.params as unknown as Record<string, unknown>)}
                      </p>
                      <div style={{ display: "flex", gap: "1rem", marginTop: "0.375rem" }}>
                        <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.75rem" }}>
                          {entry.total_results.toLocaleString("pt-BR")} resultados
                        </span>
                        <span style={{ color: "rgba(255,255,255,0.4)", fontSize: "0.75rem" }}>
                          {new Date(entry.created_at).toLocaleString("pt-BR")}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0, alignItems: "center" }}>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: "0.8rem", padding: "0.375rem 0.75rem" }}
                        onClick={(e) => { e.stopPropagation(); handleReuse(entry); }}
                        title="Carregar filtros sem executar a busca"
                      >
                        Reaproveitar
                      </button>
                      <button
                        className="btn btn-primary"
                        style={{ fontSize: "0.8rem", padding: "0.375rem 0.75rem" }}
                        onClick={(e) => { e.stopPropagation(); handleContinue(entry); }}
                        title="Abrir busca com resultados"
                      >
                        Continuar
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          /* Credit Transactions Tab */
          txLoading ? (
            <p style={{ color: "rgba(255,255,255,0.5)" }}>Carregando...</p>
          ) : !allTransactions.length ? (
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
