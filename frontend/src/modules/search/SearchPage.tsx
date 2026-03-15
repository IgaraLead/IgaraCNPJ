import React, { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { searchApi, integrationsApi, type SearchParams, type SearchResult, type SearchResponse, type Municipio, type CnaeItem, type IntegrationAction } from "../../shared/api";
import { useAuth } from "../../shared/store";

const UFS = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS",
  "MT","PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

/* ── Multi-select dropdown component ────────────── */
function MunicipioMultiSelect({
  municipios,
  selected,
  onChange,
  loading,
}: {
  municipios: Municipio[];
  selected: Municipio[];
  onChange: (sel: Municipio[]) => void;
  loading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = municipios.filter((m) =>
    m.descricao.toLowerCase().includes(filter.toLowerCase())
  );

  const toggle = (m: Municipio) => {
    if (selected.find((s) => s.codigo === m.codigo)) {
      onChange(selected.filter((s) => s.codigo !== m.codigo));
    } else {
      onChange([...selected, m]);
    }
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        className="input"
        style={{
          minHeight: 38,
          display: "flex",
          flexWrap: "wrap",
          gap: "0.25rem",
          cursor: "pointer",
          alignItems: "center",
          padding: "0.375rem 0.625rem",
        }}
        onClick={() => setOpen(!open)}
      >
        {selected.length === 0 && (
          <span style={{ color: "var(--text-light)", fontSize: "0.875rem" }}>
            {loading ? "Carregando..." : "Selecione cidades"}
          </span>
        )}
        {selected.map((m) => (
          <span
            key={m.codigo}
            style={{
              background: "rgba(0,112,255,0.2)",
              color: "#fff",
              borderRadius: 6,
              padding: "0.15rem 0.5rem",
              fontSize: "0.75rem",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.25rem",
            }}
          >
            {m.descricao}
            <span
              style={{ cursor: "pointer", fontWeight: 700, marginLeft: 2 }}
              onClick={(e) => {
                e.stopPropagation();
                onChange(selected.filter((s) => s.codigo !== m.codigo));
              }}
            >
              ×
            </span>
          </span>
        ))}
      </div>
      {open && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 50,
            background: "rgba(26,31,46,0.97)",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-sm)",
            maxHeight: 220,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          }}
        >
          <input
            className="input"
            placeholder="Filtrar cidades..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            style={{ borderRadius: 0, borderBottom: "1px solid var(--glass-border)", flexShrink: 0 }}
            autoFocus
          />
          <div style={{ overflowY: "auto", flex: 1 }}>
            {filtered.length === 0 && (
              <div style={{ padding: "0.75rem", color: "var(--text-light)", fontSize: "0.8rem" }}>
                Nenhuma cidade encontrada
              </div>
            )}
            {filtered.map((m) => {
              const isSelected = !!selected.find((s) => s.codigo === m.codigo);
              return (
                <div
                  key={m.codigo}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggle(m);
                  }}
                  style={{
                    padding: "0.5rem 0.75rem",
                    fontSize: "0.8rem",
                    color: isSelected ? "#fff" : "var(--text-muted)",
                    background: isSelected ? "rgba(0,112,255,0.15)" : "transparent",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  <span style={{
                    width: 14, height: 14, borderRadius: 3,
                    border: isSelected ? "none" : "1px solid var(--border-subtle)",
                    background: isSelected ? "var(--primary)" : "transparent",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "0.65rem", color: "#fff", flexShrink: 0,
                  }}>
                    {isSelected && "✓"}
                  </span>
                  {m.descricao}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Process/Credits Modal ───────────────────────── */

/* ── CNAE Multi-select with async search ─────────── */
function CnaeMultiSelect({
  selected,
  onChange,
}: {
  selected: CnaeItem[];
  onChange: (sel: CnaeItem[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CnaeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const doSearch = (q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchApi.cnaes(q, 30);
        setResults(data);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
  };

  useEffect(() => {
    if (open) doSearch(query);
  }, [open]);

  const handleQueryChange = (val: string) => {
    setQuery(val);
    doSearch(val);
  };

  const toggle = (item: CnaeItem) => {
    if (selected.find((s) => s.codigo === item.codigo)) {
      onChange(selected.filter((s) => s.codigo !== item.codigo));
    } else {
      onChange([...selected, item]);
    }
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        className="input"
        style={{
          minHeight: 38,
          display: "flex",
          flexWrap: "wrap",
          gap: "0.25rem",
          cursor: "pointer",
          alignItems: "center",
          padding: "0.375rem 0.625rem",
        }}
        onClick={() => setOpen(!open)}
      >
        {selected.length === 0 && (
          <span style={{ color: "var(--text-light)", fontSize: "0.875rem" }}>
            Buscar por código ou descrição
          </span>
        )}
        {selected.map((c) => (
          <span
            key={c.codigo}
            style={{
              background: "rgba(0,112,255,0.2)",
              color: "#fff",
              borderRadius: 6,
              padding: "0.15rem 0.5rem",
              fontSize: "0.75rem",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.25rem",
            }}
          >
            {c.codigo}
            <span
              style={{ cursor: "pointer", fontWeight: 700, marginLeft: 2 }}
              onClick={(e) => {
                e.stopPropagation();
                onChange(selected.filter((s) => s.codigo !== c.codigo));
              }}
            >
              ×
            </span>
          </span>
        ))}
      </div>
      {open && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 50,
            background: "rgba(26,31,46,0.97)",
            border: "1px solid var(--glass-border)",
            borderRadius: "var(--radius-sm)",
            maxHeight: 260,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          }}
        >
          <input
            className="input"
            placeholder="Código ou descrição do CNAE..."
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            style={{ borderRadius: 0, borderBottom: "1px solid var(--glass-border)", flexShrink: 0 }}
            autoFocus
          />
          <div style={{ overflowY: "auto", flex: 1 }}>
            {loading && (
              <div style={{ padding: "0.75rem", color: "var(--text-light)", fontSize: "0.8rem" }}>
                Buscando...
              </div>
            )}
            {!loading && results.length === 0 && query && (
              <div style={{ padding: "0.75rem", color: "var(--text-light)", fontSize: "0.8rem" }}>
                Nenhum CNAE encontrado
              </div>
            )}
            {!loading && results.map((item) => {
              const isSelected = !!selected.find((s) => s.codigo === item.codigo);
              return (
                <div
                  key={item.codigo}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggle(item);
                  }}
                  style={{
                    padding: "0.5rem 0.75rem",
                    fontSize: "0.8rem",
                    color: isSelected ? "#fff" : "var(--text-muted)",
                    background: isSelected ? "rgba(0,112,255,0.15)" : "transparent",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  <span style={{
                    width: 14, height: 14, borderRadius: 3,
                    border: isSelected ? "none" : "1px solid var(--border-subtle)",
                    background: isSelected ? "var(--primary)" : "transparent",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "0.65rem", color: "#fff", flexShrink: 0,
                  }}>
                    {isSelected && "✓"}
                  </span>
                  <span style={{ color: "rgba(255,255,255,0.5)", minWidth: 65, fontFamily: "monospace", fontSize: "0.75rem" }}>
                    {item.codigo}
                  </span>
                  <span style={{ flex: 1 }}>{item.descricao}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Process/Credits Modal ───────────────────────── */
function ProcessModal({
  total,
  onProcess,
  onClose,
  processing,
  submitted,
}: {
  total: number;
  onProcess: (qty: number) => void;
  onClose: () => void;
  processing: boolean;
  submitted: boolean;
}) {
  const [quantidade, setQuantidade] = useState(Math.min(total, 100));
  const maxAllowed = Math.min(total, 50000);
  const navigate = useNavigate();

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }} onClick={onClose}>
      <div
        className="glass-strong"
        style={{ padding: "2rem", maxWidth: 440, width: "90%", animation: "fadeIn 0.2s ease-out" }}
        onClick={(e) => e.stopPropagation()}
      >
        {!submitted ? (
          <>
            <h3 style={{ color: "#fff", fontSize: "1.1rem", marginBottom: "1rem" }}>
              Processar Contatos
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
              Foram encontrados <strong style={{ color: "#fff" }}>{total.toLocaleString("pt-BR")}</strong> resultados.
              Informe quantos contatos deseja processar.
            </p>

            <div style={{ marginBottom: "1rem" }}>
              <label style={labelStyle}>Quantidade de contatos</label>
              <input
                className="input"
                type="number"
                min={1}
                max={maxAllowed}
                value={quantidade}
                onChange={(e) => setQuantidade(Math.max(1, Math.min(maxAllowed, parseInt(e.target.value) || 1)))}
              />
              <p style={{ color: "var(--text-light)", fontSize: "0.75rem", marginTop: "0.25rem" }}>
                Custo: <strong style={{ color: "#fff" }}>{quantidade.toLocaleString("pt-BR")}</strong> créditos
                (1 crédito por CNPJ · cobrados após processamento)
              </p>
            </div>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                disabled={processing}
                onClick={() => onProcess(quantidade)}
              >
                {processing ? "Enviando..." : `Processar (${quantidade} créditos)`}
              </button>
            </div>

            <button
              className="btn btn-ghost"
              style={{ width: "100%", marginTop: "1rem", justifyContent: "center" }}
              onClick={onClose}
            >
              Cancelar
            </button>
          </>
        ) : (
          <>
            <h3 style={{ color: "#fff", fontSize: "1.1rem", marginBottom: "1rem" }}>
              ✅ Pedido Enviado
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
              Seu pedido de <strong style={{ color: "#fff" }}>{quantidade.toLocaleString("pt-BR")}</strong> contatos está sendo processado.
              Os créditos serão debitados somente quando os arquivos estiverem prontos para download no seu <strong style={{ color: "#fff" }}>Histórico</strong>.
            </p>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                onClick={() => { onClose(); navigate("/history"); }}
              >
                Ir para Histórico
              </button>
              <button
                className="btn btn-ghost"
                style={{ flex: 1 }}
                onClick={onClose}
              >
                Continuar aqui
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}


/* ── Main SearchPage ─────────────────────────────── */
export default function SearchPage() {
  const { user, fetchUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [uf, setUf] = useState("SP");
  const [selectedMunicipios, setSelectedMunicipios] = useState<Municipio[]>([]);
  const [selectedCnaes, setSelectedCnaes] = useState<CnaeItem[]>([]);
  const [situacao, setSituacao] = useState("");
  const [porte, setPorte] = useState("");
  const [naturezaJuridica, setNaturezaJuridica] = useState("");
  const [cep, setCep] = useState("");
  const [bairro, setBairro] = useState("");
  const [logradouro, setLogradouro] = useState("");
  const [matrizFilial, setMatrizFilial] = useState("");
  const [capitalMin, setCapitalMin] = useState("");
  const [capitalMax, setCapitalMax] = useState("");
  const [dataAberturaInicio, setDataAberturaInicio] = useState("");
  const [dataAberturaFim, setDataAberturaFim] = useState("");
  const [ddd, setDdd] = useState("");
  const [comEmail, setComEmail] = useState("");
  const [comTelefone, setComTelefone] = useState("");
  const [simples, setSimples] = useState("");
  const [mei, setMei] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showProcessModal, setShowProcessModal] = useState(false);
  const [processSubmitted, setProcessSubmitted] = useState(false);
  const [integrationActions, setIntegrationActions] = useState<IntegrationAction[]>([]);
  const [importingTo, setImportingTo] = useState<string | null>(null);
  const historyLoadedRef = useRef(false);

  // Fetch municipalities when UF changes
  const municipiosQuery = useQuery({
    queryKey: ["municipios", uf],
    queryFn: () => searchApi.municipios(uf),
    staleTime: 1000 * 60 * 30, // cache 30min
  });

  // Clear selected municipios when UF changes (skip during history load)
  useEffect(() => {
    if (!historyLoadedRef.current) {
      setSelectedMunicipios([]);
    }
  }, [uf]);

  // Handle navigation state from history page
  useEffect(() => {
    const state = location.state as { params?: SearchParams; mode?: "continue" | "reuse" } | null;
    if (!state?.params || historyLoadedRef.current) return;
    historyLoadedRef.current = true;

    const p = state.params;
    if (p.uf) setUf(p.uf);
    if (p.cnae) setSelectedCnaes(p.cnae.split(",").map((c: string) => ({ codigo: c.trim(), descricao: "" })));
    if (p.situacao) setSituacao(p.situacao);
    if (p.porte) setPorte(p.porte);
    if (p.natureza_juridica) setNaturezaJuridica(p.natureza_juridica);
    if (p.cep) setCep(p.cep);
    if (p.bairro) setBairro(p.bairro);
    if (p.logradouro) setLogradouro(p.logradouro);
    if (p.matriz_filial) setMatrizFilial(p.matriz_filial);
    if (p.capital_social_min != null) setCapitalMin(String(p.capital_social_min));
    if (p.capital_social_max != null) setCapitalMax(String(p.capital_social_max));
    if (p.data_abertura_inicio) {
      const d = p.data_abertura_inicio;
      setDataAberturaInicio(d.length === 8 ? `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}` : d);
    }
    if (p.data_abertura_fim) {
      const d = p.data_abertura_fim;
      setDataAberturaFim(d.length === 8 ? `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}` : d);
    }
    if (p.ddd) setDdd(p.ddd);
    if (p.com_email === true) setComEmail("true");
    else if (p.com_email === false) setComEmail("false");
    if (p.com_telefone === true) setComTelefone("true");
    else if (p.com_telefone === false) setComTelefone("false");
    if (p.simples) setSimples(p.simples);
    if (p.mei) setMei(p.mei);
    if (p.q) setQ(p.q);

    // Load municipio objects from codes if present
    if (p.municipio && p.uf) {
      const codes = p.municipio.split(",").map(Number);
      searchApi.municipios(p.uf).then((munis) => {
        const matched = munis.filter((m) => codes.includes(m.codigo));
        if (matched.length) setSelectedMunicipios(matched);
      });
    }

    // Check for advanced filters
    const hasAdvanced = !!(p.natureza_juridica || p.cep || p.bairro || p.logradouro ||
      p.matriz_filial || p.capital_social_min != null || p.capital_social_max != null ||
      p.data_abertura_inicio || p.data_abertura_fim || p.ddd ||
      p.com_email != null || p.com_telefone != null || p.simples || p.mei);
    if (hasAdvanced) setShowAdvanced(true);

    // Auto-execute search in "continue" mode
    if (state.mode === "continue") {
      searchApi.search(p).then((res) => {
        setData(res);
      });
    }

    // Clear navigation state to avoid re-triggering
    navigate(location.pathname, { replace: true });
  }, [location.state]);

  // Fetch available integration actions from Hub
  useEffect(() => {
    integrationsApi.getActions().then(res => {
      setIntegrationActions(res.actions || []);
    }).catch(() => {});
  }, []);

  const handleExportForImport = async (actionKey: string) => {
    if (!data?.search_id) return;
    const action = integrationActions.find(a => a.key === actionKey);
    if (!action) return;
    setImportingTo(actionKey);
    try {
      await integrationsApi.exportForImport(data.search_id, action.target, {
        action_key: actionKey,
        target_url: action.target_url,
      });
      alert(`Dados exportados para ${action.target === "nexus" ? "Nexus" : "CRM"} com sucesso!`);
    } catch {
      alert("Erro ao exportar dados. Tente novamente.");
    } finally {
      setImportingTo(null);
    }
  };

  const buildParams = (): SearchParams => {
    const params: SearchParams = { uf, page: 1, limit: 20 };
    if (selectedMunicipios.length > 0) {
      params.municipio = selectedMunicipios.map((m) => m.codigo).join(",");
    }
    if (selectedCnaes.length > 0) params.cnae = selectedCnaes.map((c) => c.codigo).join(",");
    if (situacao) params.situacao = situacao;
    if (porte) params.porte = porte;
    if (naturezaJuridica) params.natureza_juridica = naturezaJuridica;
    if (cep) params.cep = cep;
    if (bairro) params.bairro = bairro;
    if (logradouro) params.logradouro = logradouro;
    if (matrizFilial) params.matriz_filial = matrizFilial;
    if (capitalMin) params.capital_social_min = parseFloat(capitalMin);
    if (capitalMax) params.capital_social_max = parseFloat(capitalMax);
    if (dataAberturaInicio) params.data_abertura_inicio = dataAberturaInicio.replace(/-/g, "");
    if (dataAberturaFim) params.data_abertura_fim = dataAberturaFim.replace(/-/g, "");
    if (ddd) params.ddd = ddd;
    if (comEmail === "true") params.com_email = true;
    else if (comEmail === "false") params.com_email = false;
    if (comTelefone === "true") params.com_telefone = true;
    else if (comTelefone === "false") params.com_telefone = false;
    if (simples) params.simples = simples;
    if (mei) params.mei = mei;
    if (q) params.q = q;
    return params;
  };

  const searchMutation = useMutation({
    mutationFn: (params: SearchParams) => searchApi.search(params),
    onSuccess: (res) => {
      setData(res);
    },
  });

  const processMutation = useMutation({
    mutationFn: ({ params, qty }: { params: SearchParams; qty: number }) =>
      searchApi.process(params, qty, data?.search_id),
    onSuccess: () => {
      setProcessSubmitted(true);
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    // New search = new session (no search_id passed → backend creates new entry)
    searchMutation.mutate(buildParams());
  };

  const handleProcess = (qty: number) => {
    processMutation.mutate({ params: buildParams(), qty });
  };

  const activeFilterCount = [
    selectedMunicipios.length > 0 ? "x" : "", selectedCnaes.length > 0 ? "x" : "", situacao, porte,
    naturezaJuridica, cep, bairro, logradouro, matrizFilial, capitalMin,
    capitalMax, dataAberturaInicio, dataAberturaFim, ddd, comEmail,
    comTelefone, simples, mei, q,
  ].filter(Boolean).length;

  const previewResults = data?.results ?? [];

  return (
    <div className="page animate-in">
      <h1 className="page-title">Consultas</h1>

      {/* Plan required gate */}
      {user?.status_assinatura !== "ativa" ? (
        <div className="glass-strong" style={{ padding: "3rem 2rem", textAlign: "center" }}>
          <div style={{ marginBottom: "1.5rem" }}>
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: "0 auto" }}>
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h2 style={{ color: "#fff", fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.75rem" }}>
            Assine um plano para consultar
          </h2>
          <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.95rem", maxWidth: 480, margin: "0 auto 2rem" }}>
            Para realizar consultas e acessar os dados de empresas, você precisa ter um plano ativo.
            Escolha o plano ideal para o seu negócio e comece a consultar agora.
          </p>
          <button
            className="btn btn-primary"
            style={{ fontSize: "1rem", padding: "0.75rem 2rem" }}
            onClick={() => navigate("/plans")}
          >
            Ver Planos Disponíveis
          </button>
          {user?.saldo_creditos > 0 && (
            <p style={{ color: "rgba(255,255,255,0.4)", fontSize: "0.8rem", marginTop: "1rem" }}>
              Você tem {user.saldo_creditos.toLocaleString("pt-BR")} créditos que ficarão disponíveis
              após a ativação de um plano.
            </p>
          )}
        </div>
      ) : (
      <>

      {/* Filters */}
      <div className="glass-strong" style={{ padding: "1.5rem", marginBottom: "1.5rem" }}>
        <form onSubmit={handleSearch}>
          {/* Primary filters */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
            <div>
              <label style={labelStyle}>UF *</label>
              <select className="input select" value={uf} onChange={(e) => setUf(e.target.value)} required>
                {UFS.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div style={{ gridColumn: "span 2" }}>
              <label style={labelStyle}>Município</label>
              <MunicipioMultiSelect
                municipios={municipiosQuery.data ?? []}
                selected={selectedMunicipios}
                onChange={setSelectedMunicipios}
                loading={municipiosQuery.isLoading}
              />
            </div>
            <div style={{ gridColumn: "span 2" }}>
              <label style={labelStyle}>CNAE</label>
              <CnaeMultiSelect selected={selectedCnaes} onChange={setSelectedCnaes} />
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
          </div>

          {/* Toggle advanced */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              background: "none", border: "none", color: "rgba(255,255,255,0.6)",
              cursor: "pointer", fontSize: "0.85rem", marginTop: "1rem", padding: 0,
              display: "flex", alignItems: "center", gap: "0.375rem",
            }}
          >
            {showAdvanced ? "▾" : "▸"} Filtros avançados
            {activeFilterCount > 0 && !showAdvanced && (
              <span style={{
                background: "hsl(268,100%,60%)", color: "#fff", borderRadius: "9999px",
                fontSize: "0.7rem", fontWeight: 700, padding: "0.1rem 0.45rem",
              }}>
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* Advanced filters */}
          {showAdvanced && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
              <div>
                <label style={labelStyle}>Natureza Jurídica</label>
                <input className="input" value={naturezaJuridica} onChange={(e) => setNaturezaJuridica(e.target.value)} placeholder="Código" />
              </div>
              <div>
                <label style={labelStyle}>CEP</label>
                <input className="input" value={cep} onChange={(e) => setCep(e.target.value)} placeholder="Ex: 01310100" />
              </div>
              <div>
                <label style={labelStyle}>Bairro</label>
                <input className="input" value={bairro} onChange={(e) => setBairro(e.target.value)} placeholder="Nome do bairro" />
              </div>
              <div>
                <label style={labelStyle}>Logradouro</label>
                <input className="input" value={logradouro} onChange={(e) => setLogradouro(e.target.value)} placeholder="Rua, avenida..." />
              </div>
              <div>
                <label style={labelStyle}>Matriz / Filial</label>
                <select className="input select" value={matrizFilial} onChange={(e) => setMatrizFilial(e.target.value)}>
                  <option value="">Todos</option>
                  <option value="1">Matriz</option>
                  <option value="2">Filial</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>DDD</label>
                <input className="input" value={ddd} onChange={(e) => setDdd(e.target.value)} placeholder="Ex: 11" />
              </div>
              <div>
                <label style={labelStyle}>Capital Social Mín.</label>
                <input className="input" type="number" min="0" step="0.01" value={capitalMin} onChange={(e) => setCapitalMin(e.target.value)} placeholder="R$" />
              </div>
              <div>
                <label style={labelStyle}>Capital Social Máx.</label>
                <input className="input" type="number" min="0" step="0.01" value={capitalMax} onChange={(e) => setCapitalMax(e.target.value)} placeholder="R$" />
              </div>
              <div>
                <label style={labelStyle}>Abertura (de)</label>
                <input className="input" type="date" value={dataAberturaInicio} onChange={(e) => setDataAberturaInicio(e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Abertura (até)</label>
                <input className="input" type="date" value={dataAberturaFim} onChange={(e) => setDataAberturaFim(e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Possui E-mail</label>
                <select className="input select" value={comEmail} onChange={(e) => setComEmail(e.target.value)}>
                  <option value="">Indiferente</option>
                  <option value="true">Sim</option>
                  <option value="false">Não</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Possui Telefone</label>
                <select className="input select" value={comTelefone} onChange={(e) => setComTelefone(e.target.value)}>
                  <option value="">Indiferente</option>
                  <option value="true">Sim</option>
                  <option value="false">Não</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Simples Nacional</label>
                <select className="input select" value={simples} onChange={(e) => setSimples(e.target.value)}>
                  <option value="">Todos</option>
                  <option value="S">Optante</option>
                  <option value="N">Não optante</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>MEI</label>
                <select className="input select" value={mei} onChange={(e) => setMei(e.target.value)}>
                  <option value="">Todos</option>
                  <option value="S">Sim</option>
                  <option value="N">Não</option>
                </select>
              </div>
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginTop: "1rem" }}>
            <button className="btn btn-primary" type="submit" disabled={searchMutation.isPending}>
              {searchMutation.isPending ? "Buscando..." : "Buscar"}
            </button>
          </div>
        </form>
      </div>

      {/* Errors */}
      {searchMutation.isError && (
        <div style={{ background: "rgba(239,68,68,0.15)", borderRadius: 8, padding: "1rem", marginBottom: "1rem", color: "#fca5a5" }}>
          {searchMutation.error instanceof Error ? searchMutation.error.message : "Erro na busca"}
        </div>
      )}
      {processMutation.isError && (
        <div style={{ background: "rgba(239,68,68,0.15)", borderRadius: 8, padding: "1rem", marginBottom: "1rem", color: "#fca5a5" }}>
          {processMutation.error instanceof Error ? processMutation.error.message : "Erro ao processar"}
        </div>
      )}

      {/* Results preview */}
      {data && (
        <div className="glass-strong" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.75rem" }}>
            <div>
              <span style={{ color: "#fff", fontWeight: 600, fontSize: "1.1rem" }}>
                {data.total.toLocaleString("pt-BR")} resultados encontrados
              </span>
              <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                Exibindo amostra de {data.results.length} resultados. Processe para acessar todos os dados.
              </p>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {integrationActions.find(a => a.key === "import_contacts_nexus") && (
                <button
                  className="btn"
                  style={{ background: "rgba(0,112,255,0.2)", color: "#60a5fa", border: "1px solid rgba(0,112,255,0.3)" }}
                  onClick={() => handleExportForImport("import_contacts_nexus")}
                  disabled={data.total === 0 || importingTo !== null}
                >
                  {importingTo === "import_contacts_nexus" ? "Importando..." : "Importar no Nexus"}
                </button>
              )}
              {integrationActions.find(a => a.key === "import_contacts_amplex") && (
                <button
                  className="btn"
                  style={{ background: "rgba(124,58,237,0.2)", color: "#a78bfa", border: "1px solid rgba(124,58,237,0.3)" }}
                  onClick={() => handleExportForImport("import_contacts_amplex")}
                  disabled={data.total === 0 || importingTo !== null}
                >
                  {importingTo === "import_contacts_amplex" ? "Importando..." : "Importar no CRM"}
                </button>
              )}
              <button
                className="btn btn-primary"
                onClick={() => setShowProcessModal(true)}
                disabled={data.total === 0}
              >
                Processar / Exportar
              </button>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={thStyle}>CNPJ</th>
                  <th style={thStyle}>Razão Social</th>
                  <th style={thStyle}>Nome Fantasia</th>
                  <th style={thStyle}>Situação</th>
                  <th style={thStyle}>UF</th>
                  <th style={thStyle}>Bairro</th>
                  <th style={thStyle}>CNAE</th>
                </tr>
              </thead>
              <tbody>
                {previewResults.map((r, i) => (
                  <tr key={`${r.cnpj_basico}-${r.cnpj_ordem}-${r.cnpj_dv}-${i}`}>
                    <td style={tdStyle}>{formatCnpj(r)}</td>
                    <td style={tdStyle}>{r.razao_social || "—"}</td>
                    <td style={tdStyle}>{r.nome_fantasia || "—"}</td>
                    <td style={tdStyle}>
                      <span className={`badge ${r.situacao_cadastral === "2" ? "badge-success" : "badge-warning"}`}>
                        {situacaoLabel(r.situacao_cadastral)}
                      </span>
                    </td>
                    <td style={tdStyle}>{r.uf}</td>
                    <td style={tdStyle}>{r.bairro || "—"}</td>
                    <td style={tdStyle}>{r.cnae_fiscal_principal || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Credit info */}
          <div style={{ marginTop: "1rem", textAlign: "center" }}>
            <p style={{ color: "var(--text-light)", fontSize: "0.8rem" }}>
              Seus créditos: <strong style={{ color: "#fff" }}>{user?.saldo_creditos?.toLocaleString("pt-BR") ?? 0}</strong>
            </p>
          </div>
        </div>
      )}

      {/* Process / Export modal */}
      {showProcessModal && data && (
        <ProcessModal
          total={data.total}
          onProcess={handleProcess}
          onClose={() => { setShowProcessModal(false); setProcessSubmitted(false); }}
          processing={processMutation.isPending}
          submitted={processSubmitted}
        />
      )}
      </>
      )}
    </div>
  );
}

const labelStyle: React.CSSProperties = { display: "block", color: "rgba(255,255,255,0.7)", fontSize: "0.8rem", marginBottom: "0.375rem" };
const thStyle: React.CSSProperties = { color: "rgba(255,255,255,0.5)", whiteSpace: "nowrap" };
const tdStyle: React.CSSProperties = { color: "rgba(255,255,255,0.85)", fontSize: "0.875rem", whiteSpace: "nowrap" };

function formatCnpj(r: SearchResult) {
  if (!r.cnpj_basico) return "—";
  return `${r.cnpj_basico}/${r.cnpj_ordem || "0001"}-${r.cnpj_dv || "00"}`;
}

function situacaoLabel(code: string | null): string {
  const map: Record<string, string> = { "1": "Nula", "2": "Ativa", "3": "Suspensa", "4": "Inapta", "8": "Baixada" };
  return code ? map[code] || code : "—";
}
