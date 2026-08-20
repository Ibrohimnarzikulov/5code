import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="screen">
      <div className="login-wrap">
        <div className="login-card glass">
          <h1>CodeAssistant</h1>
          <p className="sub">Shaxsiy AI tizim · lokal va cloud modellar</p>

          <form onSubmit={handleSubmit} className="stagger">
            <div className="field anim-up">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                autoComplete="username"
                placeholder="macbookair_4"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="field anim-up">
              <label htmlFor="password">Parol</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <p className="error-msg anim-up">{error}</p>

            <button type="submit" className="btn btn-primary anim-up" disabled={busy}>
              {busy ? "Tekshirilmoqda…" : "Kirish"}
            </button>
          </form>

          <p className="alt-link">
            Hisobingiz yo'qmi? <Link to="/signup">Ro'yxatdan o'ting</Link>
          </p>
        </div>
      </div>
    </section>
  );
}
