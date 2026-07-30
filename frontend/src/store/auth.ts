// Auth store: token + current user, persisted via localStorage token.

import { create } from "zustand";
import { api, clearToken, getToken, setToken } from "../api/client";
import type { Role, User } from "../api/types";

interface AuthState {
  user: User | null;
  role: Role | null;
  loading: boolean;
  initialized: boolean;
  login: (email: string, password: string) => Promise<Role>;
  register: (
    email: string,
    password: string,
    fullName: string,
    role: Role,
  ) => Promise<Role>;
  loadSession: () => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  role: null,
  loading: false,
  initialized: false,

  async login(email, password) {
    set({ loading: true });
    try {
      const res = await api.login(email, password);
      setToken(res.access_token);
      const user = await api.me();
      set({ user, role: user.role });
      return user.role;
    } finally {
      set({ loading: false });
    }
  },

  async register(email, password, fullName, role) {
    set({ loading: true });
    try {
      const res = await api.register({
        email,
        password,
        full_name: fullName,
        role,
      });
      setToken(res.access_token);
      const user = await api.me();
      set({ user, role: user.role });
      return user.role;
    } finally {
      set({ loading: false });
    }
  },

  async loadSession() {
    const token = getToken();
    if (!token) {
      set({ initialized: true });
      return;
    }
    try {
      const user = await api.me();
      set({ user, role: user.role, initialized: true });
    } catch {
      clearToken();
      set({ user: null, role: null, initialized: true });
    }
  },

  logout() {
    clearToken();
    set({ user: null, role: null });
  },
}));
