// One axios instance used everywhere. It adds the JWT to every request
// and silently refreshes the access token when it expires.
import axios from "axios";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export const api = axios.create({ baseURL: API });

const KEY = "gp_tokens";
export const getTokens = () => {
  try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
};
export const setTokens = (t) => localStorage.setItem(KEY, JSON.stringify(t));
export const clearTokens = () => localStorage.removeItem(KEY);

api.interceptors.request.use((config) => {
  const t = getTokens();
  if (t?.access) config.headers.Authorization = `Bearer ${t.access}`;
  return config;
});

let refreshing = null;
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    const tokens = getTokens();
    const isAuthCall = original?.url?.includes("/auth/");
    if (err.response?.status === 401 && tokens?.refresh && !original._retry && !isAuthCall) {
      original._retry = true;
      try {
        refreshing = refreshing || axios.post(`${API}/auth/refresh/`, { refresh: tokens.refresh })
          .finally(() => { refreshing = null; });
        const { data } = await refreshing;
        setTokens({ ...tokens, access: data.access });
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        clearTokens();
        window.dispatchEvent(new Event("gp-logout")); // session really expired
      }
    }
    return Promise.reject(err);
  }
);

// Turn any axios error into one clear, human-readable sentence.
export function errorMessage(err) {
  if (!err.response) return "Cannot reach the server. Check your internet connection and that the backend is running.";
  const { status, data } = err.response;
  if (status >= 500) return "Something went wrong on the server. Please try again.";
  if (status === 401) return data?.detail || "Your session has expired. Please log in again.";
  if (status === 404) return "Not found (it may have been deleted).";
  if (data && typeof data === "object") {
    if (data.detail) return String(data.detail);
    const flat = flatten(data);
    if (flat) return flat;
  }
  return "The request failed. Please check your input.";
}

function flatten(obj) {
  return Object.entries(obj)
    .map(([key, val]) => {
      const text = Array.isArray(val)
        ? val.map((v) => (typeof v === "object" ? flatten(v) : v)).join(" ")
        : typeof val === "object" ? flatten(val) : String(val);
      return key === "non_field_errors" ? text : `${key}: ${text}`;
    })
    .join(" | ");
}
