import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { searchApi, exportApi, type SearchParams, type SearchResult, type SearchResponse } from "../../shared/api";

const UFS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS",
  "MT","PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

export default function SearchPage() {
  const [uf, setUf] = useState("SP");
  const [municipio, setMunicipio] = useState("");
  const [cnae, setCnae] = useState("");
  const [situacao, setSituacao] = useState("");
  const [porte, setPorte] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [exporting, setExporting] = useState(false);

  const searchMutation = useMutation({
    mutationFn: (params: SearchParams) => searchApi.search(params),
    onSuccess: (res) => setData(res),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    const params: SearchParams = { uf, page: 1, limit: 50 };
    if (municipio) params.municipio = municipio;
    if (cnae) params.cnae = cnae;
    if (situacao) params.situacao = situacao;
    if (porte) params.porte = porte;
    if (q) params.q = q;
    searchMutation.mutate(params);
  };

  const handleExport = async (formato: "csv" | "xlsx") => {
    setExporting(true);
    try {
      const params: SearchParams & { formato: string } = { uf, formato };
      if (municipio) params.municipio = municipio;
      if (cnae) params.cnae = cnae;
      if (situacao) params.situacao = situacao;
      if (porte) params.porte = porte;
      if (q) params.q = q;
      const result = await exportApi.request(params);
      alert(`Exportação iniciada! Task ID: ${result.task_id}\nVerifique o status no endpoint de exportação.`);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao exportar");
    } finally {
      setExporting(false);
    }
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    const params: SearchParams = { uf, page: newPage, limit: 50 };
    if (municipio) params.municipio = municipio;
    if (cnae) params.cnae = cnae;
    if (situacao) params.situacao = situacao;
    if (porte) params.porte = porte;
    if (q) params.q = q;
    searchMutation.mutate(params);
  };

  return (
    <div className="page animate-in">
      <h1 className="page-title">Consultas</h1>

      {/* Filters */}
      <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <form onSubmit={handleSearch} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
          <div>
            <label style={labelStyle}>UF *</label>
            <select className="input select" value={uf} onChange={(e) => setUf(e.target.value)} required>
              {UFS.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Município</label>
            <input className="input" value={municipio} onChange={(e) => setMunicipio(e.target.value)} placeholder="Código" />
          </div>
          <div>
            <label style={labelStyle}>CNAE</label>
            <input className="input" value={cnae} onChange={(e) => setCnae(e.target.value)} placeholder="Ex: 6201501" />
          </div>
          <div>
            <label style={labelStyle}>Situação</label>
            <select className="input select" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
              <option value="">Todas</option>
              <option value="2">Ativa</option>
              <option value="3">Suspensa</option>
              <option value="4">Inapta</option>
              <option value="8">Baixada</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Porte</label>
            <select className="input select" value={porte} onChange={(e) => setPorte(e.target.value)}>
              <option value="">Todos</option>
              <option value="0">Não informado</option>
              <option value="1">Micro Empresa</option>
              <option value="3">Empresa de Pequeno Porte</option>
              <option value="5">Demais</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Busca textual</label>
            <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Razão social, nome fantasia" />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: "0.5rem" }}>
            <button className="btn btn-primary" type="submit" disabled={searchMutation.isPending}>
              {searchMutation.isPending ? "Buscando..." : "🔍 Buscar"}
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {searchMutation.isError && (
        <div style={{ background: "rgba(239,68,68,0.15)", borderRadius: 8, padding: "1rem", marginBottom: "1rem", color: "#fca5a5" }}>
          {searchMutation.error instanceof Error ? searchMutation.error.message : "Erro na busca"}
        </div>
      )}

      {data && (
        <div className="glass-strong" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <span style={{ color: "#fff", fontWeight: 600 }}>{data.total.toLocaleString("pt-BR")} resultados</span>
              {data.credits_consumed > 0 && (
                <span style={{ color: "rgba(255,255,255,0.5)", marginLeft: "1rem", fontSize: "0.875rem" }}>
                  {data.credits_consumed} créditos consumidos
                </span>
              )}
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="btn btn-ghost" onClick={() => handleExport("csv")} disabled={exporting}>CSV</button>
              <button className="btn btn-ghost" onClick={() => handleExport("xlsx")} disabled={exporting}>Excel</button>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={thStyle}>CNPJ</th>
                  <th style={thStyle}>Razão Social</th>
                  <th style={thStyle}>Nome Fantasia</th>
                  <th style={thStyle}>UF</th>
                  <th style={thStyle}>Situação</th>
                  <th style={thStyle}>CNAE</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((r) => (
                  <tr key={`${r.cnpj_basico}-${r.cnpj_ordem}-${r.cnpj_dv}`}>
                    <td style={tdStyle}>{formatCnpj(r)}</td>
                    <td style={tdStyle}>{r.razao_social || "—"}</td>
                    <td style={tdStyle}>{r.nome_fantasia || "—"}</td>
                    <td style={tdStyle}>{r.uf}</td>
                    <td style={tdStyle}>
                      <span className={`badge ${r.situacao_cadastral === "2" ? "badge-success" : "badge-warning"}`}>
                        {situacaoLabel(r.situacao_cadastral)}
                      </span>
                    </td>
                    <td style={tdStyle}>{r.cnae_fiscal_principal || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={{ display: "flex", justifyContent: "center", gap: "0.5rem", marginTop: "1rem" }}>
            <button className="btn btn-ghost" disabled={page <= 1} onClick={() => handlePageChange(page - 1)}>← Anterior</button>
            <span style={{ color: "#fff", padding: "0.5rem 1rem", fontSize: "0.875rem" }}>
              Página {data.page} de {Math.ceil(data.total / data.limit) || 1}
            </span>
            <button className="btn btn-ghost" disabled={page * data.limit >= data.total} onClick={() => handlePageChange(page + 1)}>Próxima →</button>
          </div>
        </div>
      )}
    </div>
  );
}

const labelStyle: React.CSSProperties = { display: "block", color: "rgba(255,255,255,0.7)", fontSize: "0.8rem", marginBottom: "0.375rem" };
const thStyle: React.CSSProperties = { color: "rgba(255,255,255,0.5)" };
const tdStyle: React.CSSProperties = { color: "rgba(255,255,255,0.85)", fontSize: "0.875rem" };

function formatCnpj(r: SearchResult) {
  if (!r.cnpj_basico) return "—";
  return `${r.cnpj_basico}/${r.cnpj_ordem || "0001"}-${r.cnpj_dv || "00"}`;
}

function situacaoLabel(code: string | null): string {
  const map: Record<string, string> = { "1": "Nula", "2": "Ativa", "3": "Suspensa", "4": "Inapta", "8": "Baixada" };
  return code ? map[code] || code : "—";
}
