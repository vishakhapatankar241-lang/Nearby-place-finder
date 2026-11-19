import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { errorMessage } from "../api";

export default function Login({ mode }) {
  const { login, register } = useAuth();
  const isRegister = mode === "register";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    // client-side checks first (the server validates again)
    if (!email.trim() || !password) return setError("Email and password are required.");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Please enter a valid email address.");
    if (isRegister && password.length < 8) return setError("Password must be at least 8 characters.");

    setBusy(true);
    try {
      if (isRegister) await register(email.trim(), password);
      else await login(email.trim(), password);
      // App.jsx redirects to the map automatically once `user` is set
    } catch (err) {
      if (!isRegister && err.response?.status === 401) setError("Wrong email or password.");
      else setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate>
        <h1>📍 Nearby Places Finder</h1>
        <h2>{isRegister ? "Create an account" : "Log in"}</h2>
        {error && <div className="alert error">{error}</div>}
        <label>Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete={isRegister ? "new-password" : "current-password"} />
        </label>
        <button className="btn primary" disabled={busy}>{busy ? "Please wait…" : isRegister ? "Sign up" : "Log in"}</button>
        <p className="muted">
          {isRegister ? <>Already have an account? <Link to="/login">Log in</Link></>
                      : <>New here? <Link to="/register">Create an account</Link></>}
        </p>
      </form>
    </div>
  );
}
