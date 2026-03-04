import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, searchApi, type Stats, type EtlProgress, type AdminUser, type ExtractionInfo } from "../../shared/api";
import { useAuth } from "../../shared/store";
import { Navigate } from "react-router-dom";

export default function AdminPage() {
  const { user, fetchUser } = useAuth();

  if (!user || !["admin", "super_admin"].includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="page animate-in">
      <h1 className="page-title">Painel Administrativo</h1>
      <StatsSection />
      <ExtractionsSection />
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

/* ─── Extractions Lookup ─────────────────────────────────── */

function ExtractionsSection() {
  const [searchTerm, setSearchTerm] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ExtractionInfo | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-extractions", query, page],
    queryFn: () => adminApi.searchExtractions(query, page),
    placeholderData: (prev) => prev,
  });

  const handleSearch = () => { setQuery(searchTerm); setPage(1); };

  const formatParams = (params: Record<string, unknown>) => {
    return Object.entries(params)
      .filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0))
      .filter(([k]) => !["page", "limit"].includes(k))
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
      .join(" | ");
  };

  return (
    <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <h2 style={sectionTitleStyle}>Pesquisar Consultas</h2>

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          className="input"
          placeholder="Buscar por ID, email ou nome..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          style={{ flex: 1 }}
        />
        <button className="btn btn-primary" onClick={handleSearch} disabled={isLoading}>
          Buscar
        </button>
      </div>

      {/* Selected extraction detail */}
      {selected && (
        <div className="glass" style={{ padding: "1rem", marginBottom: "1rem", borderLeft: "3px solid hsl(268,100%,60%)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <h3 style={{ color: "#fff", fontSize: "0.95rem", margin: 0 }}>Detalhes da Extração</h3>
            <button className="btn btn-ghost" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }} onClick={() => setSelected(null)}>✕</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginTop: "0.75rem", fontSize: "0.85rem" }}>
            <div><span style={labelSm}>File ID</span><span style={{ color: "#fff" }}>{selected.file_id || "—"}</span></div>
            <div><span style={labelSm}>Search ID</span><span style={{ color: "#fff" }}>{selected.search_id}</span></div>
            <div><span style={labelSm}>Usuário</span><span style={{ color: "#fff" }}>{selected.usuario ? `${selected.usuario.nome} (${selected.usuario.email})` : "—"}</span></div>
            <div><span style={labelSm}>Status</span><span style={{ color: "#fff" }}>{selected.status}</span></div>
            <div><span style={labelSm}>Contatos Processados</span><span style={{ color: "#fff" }}>{selected.quantidade_processada?.toLocaleString("pt-BR") ?? "—"}</span></div>
            <div><span style={labelSm}>Créditos Consumidos</span><span style={{ color: "#fff" }}>{selected.credits_consumed.toLocaleString("pt-BR")}</span></div>
            <div><span style={labelSm}>Total Resultados</span><span style={{ color: "#fff" }}>{selected.total_results.toLocaleString("pt-BR")}</span></div>
            <div><span style={labelSm}>Data</span><span style={{ color: "#fff" }}>{selected.created_at ? new Date(selected.created_at).toLocaleString("pt-BR") : "—"}</span></div>
            <div>
              <span style={labelSm}>Exportada</span>
              <span style={{ color: selected.file_id && selected.status === "processada" ? "#4ade80" : "#fca5a5" }}>
                {selected.file_id && selected.status === "processada" ? "Sim" : "Não"}
              </span>
            </div>
            <div>
              {selected.file_id && selected.status === "processada" && (
                <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.15rem" }}>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem", color: "#86efac" }}
                    onClick={() => searchApi.downloadFile(selected.file_id!, "csv")}
                  >
                    ⬇ CSV
                  </button>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem", color: "#86efac" }}
                    onClick={() => searchApi.downloadFile(selected.file_id!, "xlsx")}
                  >
                    ⬇ XLSX
                  </button>
                </div>
              )}
            </div>
          </div>
          <div style={{ marginTop: "0.5rem" }}>
            <span style={labelSm}>Filtros Utilizados</span>
            <p style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.8rem", wordBreak: "break-word", margin: 0 }}>
              {formatParams(selected.params)}
            </p>
          </div>
        </div>
      )}

      {/* Results table */}
      {data && data.extractions.length > 0 ? (
        <>
          <div className="table-container" style={{ maxHeight: 300, overflow: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th style={thAdminStyle}>Search ID</th>
                  <th style={thAdminStyle}>Usuário</th>
                  <th style={thAdminStyle}>Status</th>
                  <th style={thAdminStyle}>Exportada</th>
                  <th style={thAdminStyle}>Contatos</th>
                  <th style={thAdminStyle}>Créditos</th>
                  <th style={thAdminStyle}>Data</th>
                  <th style={thAdminStyle}></th>
                </tr>
              </thead>
              <tbody>
                {data.extractions.map((ext) => (
                  <tr key={ext.search_id} style={{ cursor: "pointer" }} onClick={() => setSelected(ext)}>
                    <td style={{ ...tdAdminStyle, fontFamily: "monospace", fontSize: "0.8rem" }}>{ext.search_id}</td>
                    <td style={tdAdminStyle}>{ext.usuario?.nome ?? "—"}</td>
                    <td>
                      <span className={`badge ${ext.status === "processada" ? "badge-success" : ext.status === "erro" ? "badge-danger" : ext.status === "processando" ? "badge-warning" : "badge-success"}`} style={{ fontSize: "0.7rem" }}>
                        {ext.status}
                      </span>
                    </td>
                    <td>
                      {ext.file_id && ext.status === "processada" ? (
                        <div style={{ display: "flex", gap: "0.25rem" }}>
                          <button
                            className="btn btn-ghost"
                            style={{ fontSize: "0.65rem", padding: "0.15rem 0.35rem", color: "#86efac" }}
                            onClick={(e) => { e.stopPropagation(); searchApi.downloadFile(ext.file_id!, "csv"); }}
                          >
                            CSV
                          </button>
                          <button
                            className="btn btn-ghost"
                            style={{ fontSize: "0.65rem", padding: "0.15rem 0.35rem", color: "#86efac" }}
                            onClick={(e) => { e.stopPropagation(); searchApi.downloadFile(ext.file_id!, "xlsx"); }}
                          >
                            XLSX
                          </button>
                        </div>
                      ) : (
                        <span style={{ color: "rgba(255,255,255,0.3)", fontSize: "0.8rem" }}>—</span>
                      )}
                    </td>
                    <td style={tdAdminStyle}>{ext.quantidade_processada?.toLocaleString("pt-BR") ?? "—"}</td>
                    <td style={tdAdminStyle}>{ext.credits_consumed.toLocaleString("pt-BR")}</td>
                    <td style={tdAdminStyle}>{ext.created_at ? new Date(ext.created_at).toLocaleString("pt-BR") : "—"}</td>
                    <td><button className="btn btn-ghost" style={actionBtnStyle}>Ver</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: "0.5rem", marginTop: "0.75rem" }}>
            <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Anterior</button>
            <span style={{ color: "#fff", padding: "0.5rem", fontSize: "0.875rem" }}>Página {page} de {Math.ceil(data.total / 20) || 1}</span>
            <button className="btn btn-ghost" disabled={page * 20 >= data.total} onClick={() => setPage(page + 1)}>Próxima →</button>
          </div>
        </>
      ) : data && data.extractions.length === 0 ? (
        <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>Nenhuma consulta encontrada.</p>
      ) : null}
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

const PLAN_OPTIONS = ["basico", "profissional", "negocios", "corporativo", "enterprise"];

function UsersSection() {
  const queryClient = useQueryClient();
  const { fetchUser } = useAuth();
  const [page, setPage] = useState(1);
  const { data } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () => adminApi.users(page),
  });

  // Block user
  const blockMut = useMutation({
    mutationFn: (userId: number) => adminApi.blockUser(userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  // Adjust credits modal
  const [adjustModal, setAdjustModal] = useState<{ userId: number; nome: string } | null>(null);
  const [adjustQty, setAdjustQty] = useState("");
  const [adjustMotivo, setAdjustMotivo] = useState("");
  const adjustMut = useMutation({
    mutationFn: ({ userId, quantidade, motivo }: { userId: number; quantidade: number; motivo: string }) =>
      adminApi.adjustCredits(userId, quantidade, motivo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      fetchUser();
      setAdjustModal(null);
      setAdjustQty("");
      setAdjustMotivo("");
    },
  });

  // Change role
  const roleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      adminApi.changeRole(userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      fetchUser();
    },
  });

  // Create user modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [newPhone, setNewPhone] = useState("");
  const createMut = useMutation({
    mutationFn: () =>
      adminApi.createUser({ nome: newName, email: newEmail, senha: newPassword, role: newRole, telefone: newPhone || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setShowCreateModal(false);
      setNewName(""); setNewEmail(""); setNewPassword(""); setNewRole("user"); setNewPhone("");
    },
  });

  // Subscription modal
  const [subModal, setSubModal] = useState<{ userId: number; nome: string } | null>(null);
  const [subPlano, setSubPlano] = useState("basico");
  const [subPermanente, setSubPermanente] = useState(false);
  const [subDias, setSubDias] = useState("30");
  const [subCreditos, setSubCreditos] = useState("");
  const subMut = useMutation({
    mutationFn: () =>
      adminApi.setSubscription(subModal!.userId, {
        plano: subPlano,
        permanente: subPermanente,
        dias_validade: subPermanente ? undefined : parseInt(subDias) || 30,
        creditos: subCreditos ? parseInt(subCreditos) : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      fetchUser();
      setSubModal(null);
    },
  });

  return (
    <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h2 style={sectionTitleStyle}>Usuários</h2>
        <button className="btn btn-primary" style={{ fontSize: "0.8rem" }} onClick={() => setShowCreateModal(true)}>
          + Criar Conta
        </button>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 8, padding: "1.25rem", marginBottom: "1rem" }}>
          <p style={{ color: "#fff", fontWeight: 600, marginBottom: "0.75rem" }}>Criar Nova Conta</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem" }}>
            <div>
              <label style={labelSm}>Nome</label>
              <input className="input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Nome completo" />
            </div>
            <div>
              <label style={labelSm}>Email</label>
              <input className="input" type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="email@dominio.com" />
            </div>
            <div>
              <label style={labelSm}>Senha</label>
              <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Mínimo 8 caracteres" />
            </div>
            <div>
              <label style={labelSm}>Nível</label>
              <select className="input select" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                <option value="user">Usuário</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label style={labelSm}>Telefone</label>
              <input className="input" value={newPhone} onChange={(e) => setNewPhone(e.target.value)} placeholder="Opcional" />
            </div>
          </div>
          {createMut.isError && (
            <p style={{ color: "#fca5a5", fontSize: "0.8rem", marginTop: "0.5rem" }}>{createMut.error?.message}</p>
          )}
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
            <button className="btn btn-primary" disabled={!newName || !newEmail || !newPassword || createMut.isPending}
              onClick={() => createMut.mutate()}>
              {createMut.isPending ? "Criando..." : "Criar"}
            </button>
            <button className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>Cancelar</button>
          </div>
        </div>
      )}

      {/* Adjust credits inline */}
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

      {/* Subscription modal */}
      {subModal && (
        <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 8, padding: "1.25rem", marginBottom: "1rem" }}>
          <p style={{ color: "#fff", fontWeight: 600, marginBottom: "0.75rem" }}>
            Definir assinatura de <strong>{subModal.nome}</strong>
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "0.75rem" }}>
            <div>
              <label style={labelSm}>Plano</label>
              <select className="input select" value={subPlano} onChange={(e) => setSubPlano(e.target.value)}>
                {PLAN_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelSm}>Validade</label>
              <select className="input select" value={subPermanente ? "true" : "false"} onChange={(e) => setSubPermanente(e.target.value === "true")}>
                <option value="false">Temporário</option>
                <option value="true">Permanente</option>
              </select>
            </div>
            {!subPermanente && (
              <div>
                <label style={labelSm}>Dias de validade</label>
                <input className="input" type="number" min="1" value={subDias} onChange={(e) => setSubDias(e.target.value)} />
              </div>
            )}
            <div>
              <label style={labelSm}>Créditos (opcional)</label>
              <input className="input" type="number" min="0" value={subCreditos} onChange={(e) => setSubCreditos(e.target.value)} placeholder="Adicionar créditos" />
            </div>
          </div>
          {subMut.isError && (
            <p style={{ color: "#fca5a5", fontSize: "0.8rem", marginTop: "0.5rem" }}>{subMut.error?.message}</p>
          )}
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
            <button className="btn btn-primary" disabled={subMut.isPending}
              onClick={() => subMut.mutate()}>
              {subMut.isPending ? "Salvando..." : "Definir Assinatura"}
            </button>
            <button className="btn btn-ghost" onClick={() => setSubModal(null)}>Cancelar</button>
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
              <th style={thAdminStyle}>Nível</th>
              <th style={thAdminStyle}>Plano</th>
              <th style={thAdminStyle}>Créditos</th>
              <th style={thAdminStyle}>Ativo</th>
              <th style={thAdminStyle}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {data?.users?.map((u: AdminUser) => (
              <tr key={u.id}>
                <td style={tdAdminStyle}>{u.id}</td>
                <td style={tdAdminStyle}>
                  {u.nome}
                  {u.is_env_admin && (
                    <span style={{ marginLeft: 6, background: "rgba(139,92,246,0.3)", color: "#c4b5fd", borderRadius: 4, fontSize: "0.6rem", padding: "0.1rem 0.35rem", fontWeight: 700 }}>
                      PRINCIPAL
                    </span>
                  )}
                </td>
                <td style={tdAdminStyle}>{u.email}</td>
                <td>
                  {u.is_env_admin ? (
                    <span className="badge badge-success" style={{ fontSize: "0.7rem" }}>Super Admin</span>
                  ) : u.role === "super_admin" ? (
                    <span className="badge badge-success" style={{ fontSize: "0.7rem" }}>Super Admin</span>
                  ) : (
                    <select
                      className="input select"
                      style={{ fontSize: "0.75rem", padding: "0.2rem 0.4rem", minWidth: 90 }}
                      value={u.role}
                      onChange={(e) => roleMut.mutate({ userId: u.id, role: e.target.value })}
                      disabled={roleMut.isPending}
                    >
                      <option value="user">Usuário</option>
                      <option value="admin">Admin</option>
                    </select>
                  )}
                </td>
                <td style={tdAdminStyle}>
                  {u.plano ? (
                    <span>
                      <span>{u.plano.charAt(0).toUpperCase() + u.plano.slice(1)}</span>
                      {u.plano_manual && (
                        <span style={{ marginLeft: 4, color: "rgba(255,255,255,0.4)", fontSize: "0.65rem" }}>manual</span>
                      )}
                      {u.plano_permanente === true && (
                        <span style={{ marginLeft: 4, color: "#86efac", fontSize: "0.65rem" }}>∞</span>
                      )}
                      {u.plano_validade && (
                        <span style={{ marginLeft: 4, color: "rgba(255,255,255,0.4)", fontSize: "0.65rem" }}>
                          até {new Date(u.plano_validade).toLocaleDateString("pt-BR")}
                        </span>
                      )}
                    </span>
                  ) : (
                    <span style={{ color: "rgba(255,255,255,0.3)" }}>—</span>
                  )}
                </td>
                <td style={tdAdminStyle}>{u.saldo_creditos.toLocaleString("pt-BR")}</td>
                <td>
                  <span className={`badge ${u.ativo ? "badge-success" : "badge-danger"}`}>
                    {u.ativo ? "Sim" : "Não"}
                  </span>
                </td>
                <td>
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <button className="btn btn-ghost" style={actionBtnStyle}
                      onClick={() => setAdjustModal({ userId: u.id, nome: u.nome })}>
                      Créditos
                    </button>
                    <button className="btn btn-ghost" style={actionBtnStyle}
                      onClick={() => { setSubModal({ userId: u.id, nome: u.nome }); setSubPlano(u.plano || "basico"); }}>
                      Plano
                    </button>
                    {!u.is_env_admin && u.role !== "super_admin" && (
                      <button className="btn btn-ghost" style={actionBtnStyle}
                        onClick={() => blockMut.mutate(u.id)} disabled={blockMut.isPending}>
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
  const [progress, setProgress] = useState<EtlProgress | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // SSE connection for real-time ETL progress
  const connectSSE = useCallback(() => {
    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource("/api/admin/etl-progress/stream", { withCredentials: true });

    es.onmessage = (event) => {
      try {
        const data: EtlProgress = JSON.parse(event.data);
        setProgress(data);

        // Refresh stats when ETL finishes
        if (data.phase === "done" || data.phase === "error") {
          queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
        }
      } catch {
        // Ignore parse errors (e.g. keepalive comments)
      }
    };

    es.onerror = () => {
      es.close();
      // Reconnect after 5s on error
      setTimeout(connectSSE, 5000);
    };

    eventSourceRef.current = es;
  }, [queryClient]);

  useEffect(() => {
    connectSSE();
    return () => {
      eventSourceRef.current?.close();
    };
  }, [connectSSE]);

  const etlMut = useMutation({
    mutationFn: adminApi.runEtl,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  const reindexMut = useMutation({
    mutationFn: adminApi.reindex,
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
        <button
          className="btn btn-ghost"
          onClick={() => reindexMut.mutate()}
          disabled={!!isRunning || reindexMut.isPending}
        >
          {reindexMut.isPending ? "Reindexando..." : "🗂️ Recriar Índices"}
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
      {reindexMut.isError && !isRunning && (
        <p style={{ color: "#fca5a5", marginTop: "0.5rem", fontSize: "0.875rem" }}>
          {reindexMut.error?.message}
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
const labelSm: React.CSSProperties = { color: "rgba(255,255,255,0.6)", fontSize: "0.75rem", marginBottom: "0.2rem", display: "block" };
const actionBtnStyle: React.CSSProperties = { fontSize: "0.7rem", padding: "0.2rem 0.45rem" };
