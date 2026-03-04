import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { creditsApi, searchApi, type SearchHistory, type ProcessProgress } from "../../shared/api";
import { useAuth } from "../../shared/store";

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
  const queryClient = useQueryClient();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["searchHistory"],
    queryFn: () => searchApi.history(50),
    refetchInterval: (query) => {
      const entries = query.state.data;
      if (entries?.some((e) => e.status === "processando")) return 5000;
      return false;
    },
  });

  const hasProcessing = useMemo(
    () => history?.some((e) => e.status === "processando") ?? false,
    [history],
  );

  // Refresh credit balance when a processing entry completes
  const { fetchUser } = useAuth();
  const prevHasProcessing = useRef(hasProcessing);
  useEffect(() => {
    if (prevHasProcessing.current && !hasProcessing) {
      fetchUser();
    }
    prevHasProcessing.current = hasProcessing;
  }, [hasProcessing, fetchUser]);

  // Poll individual progress for each "processando" entry
  const processingIds = useMemo(
    () => (history ?? []).filter((e) => e.status === "processando").map((e) => e.search_id),
    [history],
  );
  const [progressMap, setProgressMap] = useState<Record<string, ProcessProgress>>({});

  const pollProgress = useCallback(async () => {
    if (processingIds.length === 0) return;
    const results = await Promise.allSettled(
      processingIds.map((id) => searchApi.progress(id).then((p) => [id, p] as const)),
    );
    setProgressMap((prev) => {
      const next = { ...prev };
      for (const r of results) {
        if (r.status === "fulfilled") {
          const [id, p] = r.value;
          next[id] = p;
        }
      }
      return next;
    });
  }, [processingIds]);

  useEffect(() => {
    if (processingIds.length === 0) return;
    pollProgress(); // immediate first poll
    const interval = setInterval(pollProgress, 2000);
    return () => clearInterval(interval);
  }, [processingIds, pollProgress]);

  const { data: transactions, isLoading: txLoading } = useQuery({
    queryKey: ["transactions"],
    queryFn: creditsApi.transactions,
  });

  const deleteAllMutation = useMutation({
    mutationFn: searchApi.deleteAllHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["searchHistory"] });
      setShowDeleteConfirm(false);
    },
  });

  const handleCopyId = (searchId: string) => {
    navigator.clipboard.writeText(searchId).then(() => {
      setCopiedId(searchId);
      setTimeout(() => setCopiedId(null), 1500);
    });
  };

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
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", alignItems: "center" }}>
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
        {tab === "searches" && history && history.length > 0 && (
          <button
            className="btn btn-ghost"
            style={{ marginLeft: "auto", color: "#fca5a5", fontSize: "0.8rem" }}
            onClick={() => setShowDeleteConfirm(true)}
          >
            🗑 Apagar Histórico
          </button>
        )}
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 200,
          background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }} onClick={() => setShowDeleteConfirm(false)}>
          <div
            className="glass-strong"
            style={{ padding: "2rem", maxWidth: 440, width: "90%", animation: "fadeIn 0.2s ease-out" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ color: "#fff", fontSize: "1.1rem", marginBottom: "1rem" }}>
              Apagar Histórico de Consultas
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
              Tem certeza que deseja apagar <strong style={{ color: "#fff" }}>todo o histórico de consultas</strong>?
            </p>
            <p style={{ color: "#fca5a5", fontSize: "0.85rem", marginBottom: "1.25rem", background: "rgba(239,68,68,0.1)", padding: "0.75rem", borderRadius: "8px", border: "1px solid rgba(239,68,68,0.2)" }}>
              ⚠ Esta ação também vai <strong>apagar todos os arquivos de exportação</strong> (CSV e XLSX) salvos na plataforma. Essa ação não pode ser desfeita.
            </p>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                className="btn btn-danger"
                style={{ flex: 1 }}
                onClick={() => deleteAllMutation.mutate()}
                disabled={deleteAllMutation.isPending}
              >
                {deleteAllMutation.isPending ? "Apagando..." : "Sim, apagar tudo"}
              </button>
              <button
                className="btn btn-ghost"
                style={{ flex: 1 }}
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

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
                        <span
                          style={{
                            color: "var(--primary)",
                            fontWeight: 600,
                            fontSize: "0.8rem",
                            letterSpacing: "0.02em",
                            cursor: "pointer",
                            position: "relative",
                            borderBottom: "1px dashed rgba(0,112,255,0.4)",
                            paddingBottom: "1px",
                          }}
                          title="Clique para copiar o ID"
                          onClick={(e) => { e.stopPropagation(); handleCopyId(entry.search_id); }}
                        >
                          #{entry.search_id}
                          {copiedId === entry.search_id && (
                            <span style={{
                              position: "absolute",
                              top: "-1.6rem",
                              left: "50%",
                              transform: "translateX(-50%)",
                              background: "rgba(34,197,94,0.9)",
                              color: "#fff",
                              fontSize: "0.65rem",
                              padding: "0.15rem 0.4rem",
                              borderRadius: "4px",
                              whiteSpace: "nowrap",
                              pointerEvents: "none",
                            }}>
                              Copiado!
                            </span>
                          )}
                        </span>
                        <span
                          className={`badge ${entry.status === "processada" ? "badge-success" : entry.status === "erro" ? "badge-danger" : entry.status === "processando" ? "badge-warning" : "badge-success"}`}
                          style={{ fontSize: "0.7rem", display: "inline-flex", alignItems: "center", gap: "0.3rem" }}
                        >
                          {entry.status === "processando" && (
                            <span style={{ display: "inline-block", width: 8, height: 8, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                          )}
                          {entry.status}
                        </span>
                      </div>
                      <p style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.85rem", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {summarizeParams(entry.params as unknown as Record<string, unknown>)}
                      </p>
                      <div style={{ display: "flex", gap: "1rem", marginTop: "0.375rem" }}>
                        <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.75rem" }}>
                          {entry.total_results.toLocaleString("pt-BR")} resultados
                          {entry.quantidade_processada ? ` · ${entry.quantidade_processada.toLocaleString("pt-BR")} processados` : ""}
                          {entry.credits_consumed > 0 && ` · ${entry.credits_consumed.toLocaleString("pt-BR")} créditos`}
                        </span>
                        <span style={{ color: "rgba(255,255,255,0.4)", fontSize: "0.75rem" }}>
                          {new Date(entry.created_at).toLocaleString("pt-BR")}
                        </span>
                      </div>
                      {/* Processing progress bar */}
                      {entry.status === "processando" && (
                        <ProgressBar
                          percent={progressMap[entry.search_id]?.percent ?? 0}
                          phase={progressMap[entry.search_id]?.phase ?? "Aguardando início..."}
                          isProcessing
                        />
                      )}
                      {entry.status === "processada" && entry.quantidade_processada != null && entry.quantidade_processada > 0 && entry.total_results > 0 && (
                        <ProgressBar
                          percent={Math.min((entry.quantidade_processada / entry.total_results) * 100, 100)}
                          phase={`${entry.quantidade_processada.toLocaleString("pt-BR")} de ${entry.total_results.toLocaleString("pt-BR")} processados`}
                          isProcessing={false}
                        />
                      )}
                      {entry.status === "erro" && (
                        <p style={{ color: "var(--danger)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                          Falha no processamento. Nenhum crédito foi cobrado. Tente novamente.
                        </p>
                      )}
                      {entry.status === "processando" && !progressMap[entry.search_id] && (
                        <p style={{ color: "var(--warning)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                          Aguardando início do processamento...
                        </p>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0, alignItems: "center", flexWrap: "wrap" }}>
                      {entry.file_id && entry.status === "processada" && (
                        <>
                          <button
                            className="btn btn-ghost"
                            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem", color: "#86efac" }}
                            onClick={(e) => { e.stopPropagation(); searchApi.downloadFile(entry.file_id!, "csv"); }}
                            title="Baixar arquivo CSV"
                          >
                            ⬇ CSV
                          </button>
                          <button
                            className="btn btn-ghost"
                            style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem", color: "#86efac" }}
                            onClick={(e) => { e.stopPropagation(); searchApi.downloadFile(entry.file_id!, "xlsx"); }}
                            title="Baixar arquivo Excel"
                          >
                            ⬇ XLSX
                          </button>
                        </>
                      )}
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

/* ── Progress Bar Component ─────────────────────────── */

function ProgressBar({ percent, phase, isProcessing }: { percent: number; phase: string; isProcessing: boolean }) {
  const pct = Math.min(Math.max(percent, 0), 100);
  const pctLabel = pct < 1 && pct > 0 ? "<1" : Math.round(pct).toString();

  return (
    <div style={{ marginTop: "0.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
        <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.7rem" }}>
          {phase}
        </span>
        <span style={{
          color: isProcessing ? "var(--warning)" : "var(--primary)",
          fontSize: "0.7rem",
          fontWeight: 600,
        }}>
          {pctLabel}%
        </span>
      </div>
      <div style={{
        width: "100%",
        height: 6,
        background: "rgba(255,255,255,0.08)",
        borderRadius: 3,
        overflow: "hidden",
      }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: 3,
          background: isProcessing
            ? "linear-gradient(90deg, var(--warning), #fbbf24)"
            : "linear-gradient(90deg, var(--primary), #60a5fa)",
          transition: "width 0.4s ease",
          animation: isProcessing ? "progressPulse 1.5s ease-in-out infinite" : "none",
        }} />
      </div>
    </div>
  );
}
