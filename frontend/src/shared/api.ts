/**
 * API client for the CNPJ Platform backend.
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
  municipio?: string;
  cnae?: string;
  situacao?: string;
  porte?: string;
  q?: string;
  page?: number;
  limit?: number;
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
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  limit: number;
  credits_consumed: number;
}

export const searchApi = {
  search: (params: SearchParams) =>
    request<SearchResponse>("/search", { method: "POST", body: JSON.stringify(params) }),
  lookupCnpj: (cnpj: string) => request<Record<string, unknown>>(`/search/${cnpj}`),
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
    request<{ users: Array<Record<string, unknown>>; total: number }>(`/admin/users?page=${page}&limit=${limit}`),
  adjustCredits: (userId: number, quantidade: number, motivo: string) =>
    request<{ user_id: number; novo_saldo: number }>(`/admin/users/${userId}/adjust-credits`, {
      method: "POST",
      body: JSON.stringify({ quantidade, motivo }),
    }),
  blockUser: (userId: number) =>
    request<{ user_id: number; ativo: boolean }>(`/admin/users/${userId}/block`, { method: "POST" }),
  etlProgress: () => request<EtlProgress>("/admin/etl-progress"),
  runEtl: () => request<{ status: string }>("/admin/run-etl", { method: "POST" }),
  clearCache: () => request<{ status: string }>("/admin/clear-cache", { method: "POST" }),
};
