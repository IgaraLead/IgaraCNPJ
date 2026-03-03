import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type Stats, type EtlProgress } from "../../shared/api";
import { useAuth } from "../../shared/store";
import { Navigate } from "react-router-dom";

export default function AdminPage() {
  const { user } = useAuth();

  if (user?.role !== "super_admin") {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="page animate-in">
      <h1 className="page-title">🛡️ Super-Admin</h1>
      <StatsSection />
      <QueueSection />
      <UfManagementSection />
      <UsersSection />
      <LogsSection />
      <MaintenanceSection />
    </div>
  );
}

/* ─── Stats ──────────────────────────────────────────────── */

function StatsSection() {
  const { data: stats } = useQuery<Stats>({ queryKey: ["admin-stats"], queryFn: adminApi.stats });

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
      <StatCard label="Usuários Ativos" value={stats?.usuarios_ativos ?? 0} />
      <StatCard label="Total Consultas" value={stats?.total_consultas ?? 0} />
      <StatCard label="Créditos Consumidos" value={stats?.creditos_consumidos_total ?? 0} />
      <StatCard label="Fila" value={stats?.fila_tamanho ?? 0} />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass-strong" style={{ padding: "1.25rem" }}>
      <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.8rem" }}>{label}</p>
      <p style={{ color: "#fff", fontSize: "1.75rem", fontWeight: 700 }}>{value.toLocaleString("pt-BR")}</p>
    </div>
  );
}

/* ─── Queue ──────────────────────────────────────────────── */

function QueueSection() {
  const queryClient = useQueryClient();
  const { data: queue } = useQuery({ queryKey: ["admin-queue"], queryFn: adminApi.getQueue });
  const toggleMut = useMutation({
    mutationFn: (ativado: boolean) => adminApi.toggleQueue(ativado),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-queue"] }),
  });

  return (
    <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <h2 style={sectionTitleStyle}>Controle de Fila</h2>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <span style={{ color: "#fff" }}>
          Modo fila: <strong>{queue?.queue_mode ? "ATIVADO" : "DESATIVADO"}</strong>
        </span>
        <button
          className={`btn ${queue?.queue_mode ? "btn-danger" : "btn-primary"}`}
          onClick={() => toggleMut.mutate(!queue?.queue_mode)}
          disabled={toggleMut.isPending}
        >
          {queue?.queue_mode ? "Desativar" : "Ativar"}
        </button>
        <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>
          Tamanho: {queue?.queue_size ?? 0}
        </span>
      </div>
    </div>
  );
}

/* ─── UF Management ──────────────────────────────────────── */

const UF_LIST = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

function UfManagementSection() {
  const queryClient = useQueryClient();
  const { data: ufData } = useQuery<Record<string, boolean>>({
    queryKey: ["admin-ufs"],
    queryFn: adminApi.getUfs,
  });

  const toggleMut = useMutation({
    mutationFn: ({ uf, ativo }: { uf: string; ativo: boolean }) => adminApi.toggleUf(uf, ativo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-ufs"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  return (
    <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <h2 style={sectionTitleStyle}>Gestão de UFs</h2>
      <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.8rem", marginBottom: "1rem" }}>
        Ative ou desative UFs disponíveis para consulta.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
        {UF_LIST.map((uf) => {
          const active = ufData ? ufData[uf] !== false : true;
          return (
            <button
              key={uf}
              className={`btn ${active ? "btn-primary" : "btn-ghost"}`}
              style={{ minWidth: 52, justifyContent: "center", fontSize: "0.75rem", padding: "0.375rem 0.5rem", opacity: toggleMut.isPending ? 0.6 : 1 }}
              onClick={() => toggleMut.mutate({ uf, ativo: !active })}
              disabled={toggleMut.isPending}
            >
              {uf}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Users ──────────────────────────────────────────────── */

function UsersSection() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const { data } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () => adminApi.users(page),
  });

  const blockMut = useMutation({
    mutationFn: (userId: number) => adminApi.blockUser(userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const [adjustModal, setAdjustModal] = useState<{ userId: number; nome: string } | null>(null);
  const [adjustQty, setAdjustQty] = useState("");
  const [adjustMotivo, setAdjustMotivo] = useState("");

  const adjustMut = useMutation({
    mutationFn: ({ userId, quantidade, motivo }: { userId: number; quantidade: number; motivo: string }) =>
      adminApi.adjustCredits(userId, quantidade, motivo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setAdjustModal(null);
      setAdjustQty("");
      setAdjustMotivo("");
    },
  });

  return (
    <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <h2 style={sectionTitleStyle}>Usuários</h2>

      {adjustModal && (
        <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 8, padding: "1rem", marginBottom: "1rem" }}>
          <p style={{ color: "#fff", marginBottom: "0.5rem" }}>Ajustar créditos de <strong>{adjustModal.nome}</strong></p>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <input className="input" style={{ maxWidth: 120 }} type="number" placeholder="Quantidade" value={adjustQty} onChange={(e) => setAdjustQty(e.target.value)} />
            <input className="input" style={{ flex: 1, minWidth: 160 }} placeholder="Motivo" value={adjustMotivo} onChange={(e) => setAdjustMotivo(e.target.value)} />
            <button className="btn btn-primary" disabled={!adjustQty || !adjustMotivo || adjustMut.isPending}
              onClick={() => {
                const qty = parseInt(adjustQty);
                if (isNaN(qty)) return;
                adjustMut.mutate({ userId: adjustModal.userId, quantidade: qty, motivo: adjustMotivo });
              }}>
              Aplicar
            </button>
            <button className="btn btn-ghost" onClick={() => setAdjustModal(null)}>Cancelar</button>
          </div>
        </div>
      )}

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th style={thAdminStyle}>ID</th>
              <th style={thAdminStyle}>Nome</th>
              <th style={thAdminStyle}>Email</th>
              <th style={thAdminStyle}>Role</th>
              <th style={thAdminStyle}>Ativo</th>
              <th style={thAdminStyle}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {data?.users?.map((u: Record<string, unknown>) => (
              <tr key={u.id as number}>
                <td style={tdAdminStyle}>{u.id as number}</td>
                <td style={tdAdminStyle}>{u.nome as string}</td>
                <td style={tdAdminStyle}>{u.email as string}</td>
                <td style={tdAdminStyle}>{u.role as string}</td>
                <td>
                  <span className={`badge ${u.ativo ? "badge-success" : "badge-danger"}`}>
                    {u.ativo ? "Sim" : "Não"}
                  </span>
                </td>
                <td>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="btn btn-ghost" style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                      onClick={() => setAdjustModal({ userId: u.id as number, nome: u.nome as string })}>
                      Créditos
                    </button>
                    {(u.role as string) !== "super_admin" && (
                      <button className="btn btn-ghost" style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                        onClick={() => blockMut.mutate(u.id as number)} disabled={blockMut.isPending}>
                        {u.ativo ? "Bloquear" : "Desbloquear"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", justifyContent: "center", gap: "0.5rem", marginTop: "1rem" }}>
        <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Anterior</button>
        <span style={{ color: "#fff", padding: "0.5rem", fontSize: "0.875rem" }}>Página {page} de {Math.ceil((data?.total ?? 0) / 50) || 1}</span>
        <button className="btn btn-ghost" disabled={!data || page * 50 >= data.total} onClick={() => setPage(page + 1)}>Próxima →</button>
      </div>
    </div>
  );
}

/* ─── Logs ───────────────────────────────────────────────── */

function LogsSection() {
  const { data: logs } = useQuery({ queryKey: ["admin-logs"], queryFn: () => adminApi.logs(50) });

  return (
    <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <h2 style={sectionTitleStyle}>Logs de Ações</h2>
      {!logs || logs.length === 0 ? (
        <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>Nenhum log.</p>
      ) : (
        <div className="table-container" style={{ maxHeight: 300, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={thAdminStyle}>Data</th>
                <th style={thAdminStyle}>Ação</th>
                <th style={thAdminStyle}>Detalhes</th>
                <th style={thAdminStyle}>IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log: Record<string, unknown>, i: number) => (
                <tr key={i}>
                  <td style={tdAdminStyle}>{log.created_at ? new Date(log.created_at as string).toLocaleString("pt-BR") : "—"}</td>
                  <td style={tdAdminStyle}>{log.acao as string}</td>
                  <td style={{ ...tdAdminStyle, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {log.detalhes ? JSON.stringify(log.detalhes) : "—"}
                  </td>
                  <td style={tdAdminStyle}>{(log.ip_address as string) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ─── Maintenance ────────────────────────────────────────── */

const PHASE_LABELS: Record<string, string> = {
  init: "Inicializando",
  download: "Download",
  extract: "Extração",
  process: "Processamento",
  index: "Indexação",
  done: "Concluído",
  error: "Erro",
};

function MaintenanceSection() {
  const queryClient = useQueryClient();
  const [polling, setPolling] = useState(false);

  // Poll ETL progress every 2s when active
  const { data: progress } = useQuery<EtlProgress>({
    queryKey: ["etl-progress"],
    queryFn: adminApi.etlProgress,
    refetchInterval: polling ? 2000 : false,
  });

  // Start/stop polling based on running state
  useEffect(() => {
    if (progress?.running && progress.phase !== "done" && progress.phase !== "error") {
      setPolling(true);
    } else if (progress && (progress.phase === "done" || progress.phase === "error" || !progress.running)) {
      // Keep polling for a bit after done so UI catches final state
      const timer = setTimeout(() => setPolling(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [progress]);

  const etlMut = useMutation({
    mutationFn: adminApi.runEtl,
    onSuccess: () => {
      setPolling(true);
      queryClient.invalidateQueries({ queryKey: ["etl-progress"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  const cacheMut = useMutation({
    mutationFn: adminApi.clearCache,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-stats"] }),
  });

  const isRunning = progress?.running && progress.phase !== "done" && progress.phase !== "error";
  const isDone = progress?.phase === "done";
  const isError = progress?.phase === "error";
  const pct = progress?.percent ?? 0;

  return (
    <div className="glass-strong" style={{ padding: "1.5rem" }}>
      <h2 style={sectionTitleStyle}>Manutenção</h2>

      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: isRunning || isDone || isError ? "1.25rem" : 0 }}>
        <button
          className="btn btn-primary"
          onClick={() => etlMut.mutate()}
          disabled={!!isRunning || etlMut.isPending}
        >
          {isRunning ? "⏳ ETL em execução..." : "🔄 Rodar ETL"}
        </button>
        <button className="btn btn-ghost" onClick={() => cacheMut.mutate()} disabled={cacheMut.isPending}>
          {cacheMut.isPending ? "Limpando..." : "🧹 Limpar Cache"}
        </button>
      </div>

      {/* ── ETL Progress Bar ── */}
      {(isRunning || isDone || isError) && (
        <div style={{ marginTop: "0.25rem" }}>
          {/* Phase label + step */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.5rem" }}>
            <span style={{ color: isError ? "#fca5a5" : "#fff", fontWeight: 600, fontSize: "0.9rem" }}>
              {PHASE_LABELS[progress?.phase ?? ""] ?? progress?.phase}
            </span>
            <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.8rem" }}>
              {progress?.step}
            </span>
          </div>

          {/* Bar track */}
          <div style={{
            width: "100%",
            height: 22,
            borderRadius: 11,
            background: "rgba(255,255,255,0.08)",
            overflow: "hidden",
            position: "relative",
          }}>
            {/* Fill */}
            <div style={{
              width: `${isError ? 100 : Math.max(pct, 0)}%`,
              height: "100%",
              borderRadius: 11,
              background: isError
                ? "linear-gradient(90deg, #ef4444, #dc2626)"
                : isDone
                  ? "linear-gradient(90deg, #22c55e, #16a34a)"
                  : "linear-gradient(135deg, hsl(268,100%,60%), hsl(213,100%,60%))",
              transition: "width 0.6s ease",
            }} />
            {/* Percentage text */}
            {!isError && (
              <span style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "#fff",
                textShadow: "0 1px 2px rgba(0,0,0,0.4)",
              }}>
                {pct.toFixed(1)}%
              </span>
            )}
          </div>

          {/* Detail line */}
          {progress?.detail && (
            <p style={{
              color: isError ? "#fca5a5" : "rgba(255,255,255,0.5)",
              fontSize: "0.8rem",
              marginTop: "0.4rem",
            }}>
              {progress.detail}
            </p>
          )}
        </div>
      )}

      {/* mutation-level messages */}
      {etlMut.isError && !isRunning && (
        <p style={{ color: "#fca5a5", marginTop: "0.5rem", fontSize: "0.875rem" }}>
          {etlMut.error?.message}
        </p>
      )}
      {cacheMut.isSuccess && <p style={{ color: "#86efac", marginTop: "0.5rem", fontSize: "0.875rem" }}>Cache limpo!</p>}
      {cacheMut.isError && (
        <p style={{ color: "#fca5a5", marginTop: "0.5rem", fontSize: "0.875rem" }}>
          {cacheMut.error?.message}
        </p>
      )}
    </div>
  );
}

const sectionTitleStyle: React.CSSProperties = { color: "#fff", fontSize: "1.125rem", fontWeight: 600, marginBottom: "1rem" };
const thAdminStyle: React.CSSProperties = { color: "rgba(255,255,255,0.5)" };
const tdAdminStyle: React.CSSProperties = { color: "rgba(255,255,255,0.8)", fontSize: "0.875rem" };
