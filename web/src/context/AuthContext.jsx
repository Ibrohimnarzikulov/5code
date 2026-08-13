/** Autentifikatsiya va toast konteksti. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, clearToken, setToken, setUnauthorizedHandler } from "../api";

const AuthContext = createContext(null);

/** @returns {{user, loading, login, signup, logout, refresh, toast, toasts}} */
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth faqat AuthProvider ichida ishlaydi");
  return ctx;
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState([]);

  const toast = useCallback((message, isError = false) => {
    const id = crypto.randomUUID();
    setToasts((list) => [...list, { id, message, isError }]);
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 4200);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  // 401 kelganda avtomatik chiqish
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
  }, []);

  // Sahifa yangilanganda tokenni tekshirish
  useEffect(() => {
    (async () => {
      try {
        setUser(await api("/api/auth/me"));
      } catch {
        clearToken();
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const authenticate = useCallback(async (path, body) => {
    const data = await api(path, {
      method: "POST",
      auth: false,
      body: JSON.stringify(body),
    });
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const login = useCallback(
    (username, password) =>
      authenticate("/api/auth/login", { username, password }),
    [authenticate],
  );

  const signup = useCallback(
    (username, password) =>
      authenticate("/api/auth/register", { username, password }),
    [authenticate],
  );

  const refresh = useCallback(async () => {
    try {
      setUser(await api("/api/auth/me"));
    } catch {
      /* refresh muhim emas */
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, setUser, loading, login, signup, logout, refresh, toast, toasts }}
    >
      {children}
    </AuthContext.Provider>
  );
}
