import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setCsrf } from "./api";

export type Me = {
  user: { id: string; name: string; email: string };
  org: { id: string; name: string; kill_switch: { active: boolean; by: string; at: string; reason: string } | null };
  role: string; role_id: string; csrf: string;
  permissions: string[];
  scopes: { agents: string[]; data: Record<string, string[]>; actions: string[]; approval_limit: number | null };
  orgs: { id: string; name: string; role: string; industry?: string; created?: string }[];
};

type Ctx = { me: Me | null; loading: boolean; refresh: () => Promise<Me | null>; logout: () => Promise<void>; can: (p: string) => boolean };
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      const m = await api<Me>("/api/auth/me");
      setCsrf(m.csrf);
      setMe(m);
      return m;
    } catch {
      setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const logout = async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setMe(null); };
  const can = (p: string) => !!me && (me.permissions.includes("*") || me.permissions.includes(p) || me.permissions.includes(p.split(":")[0] + ":*"));
  return <AuthCtx.Provider value={{ me, loading, refresh, logout, can }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
