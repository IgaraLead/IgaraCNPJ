/**
 * Global auth store using Zustand.
 * Manages user state and provides login/logout actions.
 */

import { create } from "zustand";
import { authApi, type User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;

  fetchUser: () => Promise<void>;
  login: (email: string, senha: string) => Promise<void>;
  register: (nome: string, email: string, senha: string, telefone?: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  error: null,

  fetchUser: async () => {
    set({ loading: true, error: null });
    try {
      const user = await authApi.me();
      set({ user, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },

  login: async (email, senha) => {
    set({ loading: true, error: null });
    try {
      await authApi.login({ email, senha });
      const user = await authApi.me();
      set({ user, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao fazer login";
      set({ error: msg, loading: false });
      throw e;
    }
  },

  register: async (nome, email, senha, telefone) => {
    set({ loading: true, error: null });
    try {
      await authApi.register({ nome, email, senha, telefone });
      const user = await authApi.me();
      set({ user, loading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao criar conta";
      set({ error: msg, loading: false });
      throw e;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } finally {
      set({ user: null, loading: false, error: null });
    }
  },
}));
