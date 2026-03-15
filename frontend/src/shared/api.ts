/**
 * API client for the IgaraLead Entity backend.
 * All requests go through the Vite proxy (/api → http://localhost:8000).
 * Cookies are sent automatically (credentials: "include").
 */

const BASE = "/api";

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const { headers: customHeaders, ...restOptions } = options;
  const res = await fetch(`${BASE}${url}`, {
    credentials: "include",
    ...restOptions,
    headers: { "Content-Type": "application/json", ...customHeaders },
  });

  if (res.status === 401) {
    // Try to refresh
    const refreshRes = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshRes.ok) {
      // Retry original request
      const retryRes = await fetch(`${BASE}${url}`, {
        credentials: "include",
        ...restOptions,
        headers: { "Content-Type": "application/json", ...customHeaders },
      });
      if (!retryRes.ok) throw await parseError(retryRes);
      return retryRes.json();
    }
    // Refresh also failed — redirect to login (unless caller opts out)
    if (!options.signal?.aborted) {
      // Only redirect for "real" requests, not silent auth checks
      if (!(options as any).__noRedirect) {
        window.location.href = "/login";
      }
    }
    throw new Error("Session expired");
  }

  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return {} as T;
  return res.json();
}

async function parseError(res: Response) {
  try {
    const data = await res.json();
    return new Error(data.detail || `HTTP ${res.status}`);
  } catch {
    return new Error(`HTTP ${res.status}`);
  }
}

// ─── Auth ──────────────────────────────────────────────────

export interface User {
  id: number;
  nome: string;
  email: string;
  role: string;
  ativo: boolean;
  saldo_creditos: number;
  plano: string | null;
  status_assinatura: string | null;
}

export const authApi = {
  register: (data: { nome: string; email: string; senha: string; telefone?: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; senha: string }) =>
    request<{ message: string; user_id: number }>("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  logout: () =>
    request<{ message: string }>("/auth/logout", { method: "POST" }),

  me: async (): Promise<User> => {
    // Direct fetch — no refresh retry, no redirect.
    // Avoids noisy 401 console errors when user is simply not logged in.
    const res = await fetch(`${BASE}/auth/me`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error("Not authenticated");
    return res.json();
  },

  changePassword: (data: { senha_atual: string; nova_senha: string }) =>
    request<{ message: string }>("/auth/change-password", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Plans ─────────────────────────────────────────────────

export interface Plan {
  id: string;
  name: string;
  price: number;
  credits: number;
  credit_price: number;
  max_accumulation: number;
}

export interface Subscription {
  id: number;
  usuario_id: number;
  plano: string;
  status: string;
  data_inicio: string | null;
  data_proximo_ciclo: string | null;
  checkout_url?: string;
}

export const plansApi = {
  list: () => request<Plan[]>("/plans"),
  subscribe: (plano: string) =>
    request<Subscription>("/subscription/create", { method: "POST", body: JSON.stringify({ plano }) }),
  cancel: () =>
    request<{ message: string }>("/subscription/cancel", { method: "POST" }),
};

// ─── Credits ───────────────────────────────────────────────

export interface Credits {
  usuario_id: number;
  saldo: number;
  creditos_recebidos: number;
  creditos_consumidos: number;
}

export interface CreditTransaction {
  id: number;
  usuario_id: number;
  tipo: string;
  quantidade: number;
  motivo: string | null;
  created_at: string;
}

export const creditsApi = {
  balance: () => request<Credits>("/credits/me"),
  transactions: () => request<CreditTransaction[]>("/credits/me/transactions"),
};

// ─── Search ────────────────────────────────────────────────

export interface SearchParams {
  uf: string;
  municipio?: string; // comma-separated municipio codes
  cnae?: string;
  situacao?: string;
  porte?: string;
  natureza_juridica?: string;
  cep?: string;
  bairro?: string;
  logradouro?: string;
  matriz_filial?: string;
  capital_social_min?: number;
  capital_social_max?: number;
  data_abertura_inicio?: string;
  data_abertura_fim?: string;
  ddd?: string;
  com_email?: boolean;
  com_telefone?: boolean;
  simples?: string;
  mei?: string;
  q?: string;
  page?: number;
  limit?: number;
  search_id?: string; // Reuse existing search session (pagination)
}

export interface SearchResult {
  cnpj_basico: string;
  cnpj_ordem: string | null;
  cnpj_dv: string | null;
  razao_social: string | null;
  nome_fantasia: string | null;
  situacao_cadastral: string | null;
  uf: string;
  municipio: string | null;
  cnae_fiscal_principal: string | null;
  bairro: string | null;
  logradouro: string | null;
  numero: string | null;
  complemento: string | null;
  cep: string | null;
  telefone: string | null;
  email: string | null;
  capital_social: number | null;
  natureza_juridica: number | null;
  porte_empresa: number | null;
  data_inicio_atividade: string | null;
  identificador_matriz_filial: number | null;
  municipio_nome: string | null;
  socios: string | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  limit: number;
  credits_consumed: number;
  task_id?: string;
  search_id?: string;
}

export interface Municipio {
  codigo: number;
  descricao: string;
}

export interface ProcessResponse {
  search_id: string;
  status: string;
  credits_consumed: number;
  quantidade: number;
}

export interface ExportCreditResponse {
  task_id: string;
  status: string;
  credits_consumed: number;
}

export interface SearchHistory {
  id: number;
  search_id: string;
  params: SearchParams;
  total_results: number;
  status: string;
  credits_consumed: number;
  file_id: string | null;
  quantidade_processada: number | null;
  created_at: string;
}

export interface SearchHistoryDetail {
  search_id: string;
  params: SearchParams;
  total_results: number;
  status: string;
  credits_consumed: number;
  created_at: string;
}

export interface ProcessProgress {
  status: string;
  percent: number;
  phase: string;
}

export const searchApi = {
  search: (params: SearchParams) =>
    request<SearchResponse>("/search", { method: "POST", body: JSON.stringify(params) }),
  lookupCnpj: (cnpj: string) => request<Record<string, unknown>>(`/search/${cnpj}`),
  municipios: (uf: string) => request<Municipio[]>(`/search/municipios?uf=${uf}`),
  cnaes: (q: string, limit = 30) => request<CnaeItem[]>(`/search/cnaes?q=${encodeURIComponent(q)}&limit=${limit}`),
  process: (searchParams: SearchParams, quantidade: number, searchId?: string) =>
    request<ProcessResponse>("/search/process", {
      method: "POST",
      body: JSON.stringify({ search_params: searchParams, quantidade, search_id: searchId }),
    }),
  downloadFile: (fileId: string, formato: "csv" | "xlsx") => {
    // Use fetch with credentials to download the file as a blob
    const url = `${BASE}/search/download/${fileId}?formato=${formato}`;
    fetch(url, { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error("Download failed");
        return res.blob();
      })
      .then((blob) => {
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `contatos_${fileId}.${formato}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
      })
      .catch(() => {
        alert("Não foi possível baixar o arquivo. Tente novamente.");
      });
  },
  exportWithCredits: (searchParams: SearchParams, formato: "csv" | "xlsx") =>
    request<ExportCreditResponse>("/search/export", {
      method: "POST",
      body: JSON.stringify({ search_params: searchParams, formato }),
    }),
  history: (limit = 50) => request<SearchHistory[]>(`/search/history?limit=${limit}`),
  historyDetail: (searchId: string) => request<SearchHistoryDetail>(`/search/history/${searchId}`),
  deleteAllHistory: () => request<{ message: string; files_deleted: number }>("/search/history", { method: "DELETE" }),
  deleteHistoryEntry: (searchId: string) => request<{ message: string }>(`/search/history/${searchId}`, { method: "DELETE" }),
  progress: (searchId: string) => request<ProcessProgress>(`/search/progress/${searchId}`),
};

// ─── Export ────────────────────────────────────────────────

export interface ExportStatus {
  task_id: string;
  status: string;
  download_url: string | null;
}

export const exportApi = {
  request: (params: SearchParams & { formato: string }) =>
    request<ExportStatus>("/export", { method: "POST", body: JSON.stringify(params) }),
  status: (taskId: string) => request<ExportStatus>(`/export/${taskId}`),
};

// ─── Cross-Product Integrations ────────────────────────────

export interface IntegrationAction {
  integration: string;
  target: string;
  target_url: string;
  key: string;
  label: string;
  description: string;
  endpoint: string;
  method: string;
}

export interface IntegrationActionsResponse {
  source: string;
  organization: string;
  actions: IntegrationAction[];
}

export const integrationsApi = {
  getActions: () =>
    request<IntegrationActionsResponse>("/v1/integrations/actions/entity"),

  exportForImport: (searchId: string, target: "nexus" | "amplex", options?: { with_phone?: boolean; with_email?: boolean; limit?: number }) =>
    request<{ total: number; contacts: unknown[]; import_url: string }>("/v1/integrations/export-for-import", {
      method: "POST",
      body: JSON.stringify({ search_id: searchId, target, ...options }),
    }),
};

// ─── Admin ─────────────────────────────────────────────────

export interface Stats {
  usuarios_ativos: number;
  total_consultas: number;
  creditos_consumidos_total: number;
  fila_tamanho: number;
}

export interface EtlProgress {
  running: boolean;
  phase?: string;
  step?: string;
  percent?: number;
  detail?: string;
  updated_at?: number;
}

export interface AdminUser {
  id: number;
  nome: string;
  email: string;
  role: string;
  ativo: boolean;
  criado_em: string;
  plano: string | null;
  plano_permanente: boolean | null;
  plano_validade: string | null;
  plano_manual: boolean;
  saldo_creditos: number;
  is_env_admin: boolean;
}

export interface CnaeItem {
  codigo: string;
  descricao: string;
}

export interface ExtractionInfo {
  file_id: string | null;
  search_id: string;
  status: string;
  total_results: number;
  quantidade_processada: number | null;
  credits_consumed: number;
  created_at: string | null;
  params: Record<string, unknown>;
  usuario: { id: number; nome: string; email: string; role?: string } | null;
}

export const adminApi = {
  stats: () => request<Stats>("/admin/stats"),
  getQueue: () => request<{ queue_mode: boolean; queue_size: number }>("/admin/config/queue"),
  toggleQueue: (ativado: boolean) =>
    request<{ queue_mode: boolean }>("/admin/config/queue", { method: "POST", body: JSON.stringify({ ativado }) }),
  toggleUf: (uf: string, ativo: boolean) =>
    request<{ uf: string; ativo: boolean }>("/admin/ufs/toggle", { method: "POST", body: JSON.stringify({ uf, ativo }) }),
  getUfs: () => request<Record<string, boolean>>("/admin/ufs"),
  logs: (limit = 100) => request<Array<Record<string, unknown>>>(`/admin/logs?limit=${limit}`),
  users: (page = 1, limit = 50) =>
    request<{ users: AdminUser[]; total: number }>(`/admin/users?page=${page}&limit=${limit}`),
  createUser: (data: { nome: string; email: string; senha: string; role: string; telefone?: string }) =>
    request<{ id: number; email: string; role: string }>("/admin/users/create", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  changeRole: (userId: number, role: string, senha: string) =>
    request<{ user_id: number; role: string }>(`/admin/users/${userId}/role`, {
      method: "POST",
      body: JSON.stringify({ role }),
      headers: { "X-Admin-Password": senha },
    }),
  setSubscription: (userId: number, data: { plano: string; permanente: boolean; dias_validade?: number; creditos?: number }, senha: string) =>
    request<{ user_id: number; plano: string; permanente: boolean; data_validade: string | null }>(
      `/admin/users/${userId}/subscription`,
      { method: "POST", body: JSON.stringify(data), headers: { "X-Admin-Password": senha } },
    ),
  adjustCredits: (userId: number, quantidade: number, motivo: string, senha: string) =>
    request<{ user_id: number; novo_saldo: number }>(`/admin/users/${userId}/adjust-credits`, {
      method: "POST",
      body: JSON.stringify({ quantidade, motivo }),
      headers: { "X-Admin-Password": senha },
    }),
  blockUser: (userId: number, senha: string) =>
    request<{ user_id: number; ativo: boolean }>(`/admin/users/${userId}/block`, {
      method: "POST",
      headers: { "X-Admin-Password": senha },
    }),
  etlProgress: () => request<EtlProgress>("/admin/etl-progress"),
  runEtl: (mode: "atualizar" | "recriar", senha: string) =>
    request<{ status: string }>(`/admin/run-etl?mode=${mode}`, {
      method: "POST",
      headers: { "X-Admin-Password": senha },
    }),
  reindex: (senha: string) =>
    request<{ status: string }>("/admin/reindex", {
      method: "POST",
      headers: { "X-Admin-Password": senha },
    }),
  clearCache: (senha: string) =>
    request<{ status: string }>("/admin/clear-cache", {
      method: "POST",
      headers: { "X-Admin-Password": senha },
    }),
  searchExtractions: (q = "", page = 1, limit = 20) =>
    request<{ extractions: ExtractionInfo[]; total: number }>(`/admin/extractions?q=${encodeURIComponent(q)}&page=${page}&limit=${limit}`),
  getExtraction: (fileId: string) =>
    request<ExtractionInfo>(`/admin/extractions/${encodeURIComponent(fileId)}`),
};
