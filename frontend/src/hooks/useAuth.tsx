import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, TOKEN_STORAGE_KEY } from "@/services/api";
import type { PermissionsMeResponse, UserSummary } from "@/types/api";

interface AuthContextValue {
  user: UserSummary | null;
  permissions: PermissionsMeResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshPermissions: () => Promise<void>;
  hasPermission: (key: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [permissions, setPermissions] = useState<PermissionsMeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadSession = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) {
      setUser(null);
      setPermissions(null);
      setLoading(false);
      return;
    }
    try {
      const [me, perms] = await Promise.all([api.getMe(), api.getMyPermissions()]);
      setUser({
        id: me.user_id,
        hospital_id: me.hospital_id,
        hospital_name: me.hospital_name,
        full_name: me.full_name,
        email: me.email,
        roles: me.roles,
        is_active: me.is_active,
      });
      setPermissions(perms);
    } catch {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      setUser(null);
      setPermissions(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const login = async (email: string, password: string) => {
    const session = await api.login(email, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, session.access_token);
    setUser(session.user);
    const perms = await api.getMyPermissions();
    setPermissions(perms);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setUser(null);
    setPermissions(null);
  };

  const refreshPermissions = async () => {
    if (!localStorage.getItem(TOKEN_STORAGE_KEY)) return;
    const perms = await api.getMyPermissions();
    setPermissions(perms);
  };

  const hasPermission = (key: string) => {
    return Boolean(permissions?.permissions?.[key]?.allowed);
  };

  return (
    <AuthContext.Provider
      value={{ user, permissions, loading, login, logout, refreshPermissions, hasPermission }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}

