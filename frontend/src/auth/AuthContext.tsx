import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, tokenStore } from "../lib/api";

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  display_name?: string;
  nome_guerra?: string;
  posto_graduacao?: string;
  full_name?: string;
  cpf?: string;
  birth_date?: string | null;
  phone?: string;
  date_joined?: string;
  roles: string[];
}

interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  /** Devolve o usuário autenticado — quem chama decide a rota inicial. */
  login: (username: string, password: string) => Promise<CurrentUser>;
  logout: () => void;
  /** Recarrega /auth/me — usar após o usuário editar o próprio perfil. */
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!tokenStore.access) {
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<CurrentUser>("/auth/me");
      setUser(data);
    } catch {
      tokenStore.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api.post("/auth/token", { username, password });
    tokenStore.set(data.access, data.refresh);
    const me = await api.get<CurrentUser>("/auth/me");
    setUser(me.data);
    return me.data;
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    const me = await api.get<CurrentUser>("/auth/me");
    setUser(me.data);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh }),
    [user, loading, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
