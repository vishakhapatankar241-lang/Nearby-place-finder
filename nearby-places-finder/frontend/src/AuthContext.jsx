import { createContext, useContext, useEffect, useState } from "react";
import { api, clearTokens, getTokens, setTokens } from "./api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // true while we check an existing token

  useEffect(() => {
    // On page load: if we have a token, ask the backend who we are
    if (!getTokens()) { setLoading(false); return; }
    api.get("/auth/me/").then(({ data }) => setUser(data)).catch(() => clearTokens()).finally(() => setLoading(false));
    const onLogout = () => setUser(null);
    window.addEventListener("gp-logout", onLogout);
    return () => window.removeEventListener("gp-logout", onLogout);
  }, []);

  async function login(email, password) {
    const { data } = await api.post("/auth/login/", { email, password });
    setTokens({ access: data.access, refresh: data.refresh });
    setUser(data.user);
  }

  async function register(email, password) {
    const { data } = await api.post("/auth/register/", { email, password });
    setTokens({ access: data.access, refresh: data.refresh });
    setUser(data.user);
  }

  function logout() {
    clearTokens();
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}
