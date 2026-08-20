import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const MIN_PASSWORD = 6;

export default function Signup() {
  const { signup } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (password !== repeat) {
      setError("Parollar mos kelmadi");
      return;
    }
    if (password.length < MIN_PASSWORD) {
      setError(`Parol kamida ${MIN_PASSWORD} belgi bo'lsin`);
      return;
    }

    setBusy(true);
    try {
      await signup(username.trim(), password);
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
          <h1>Ro'yxatdan o'tish</h1>
          <p className="sub">Yangi hisob · oddiy foydalanuvchi huquqi bilan</p>

          <form onSubmit={handleSubmit} className="stagger">
            <div className="field anim-up">
              <label htmlFor="su-username">Username</label>
              <input
                id="su-username"
                autoComplete="username"
                placeholder="dilmurod"
                pattern="[\w.\-]{3,64}"
                title="3–64 belgi: harf, raqam, nuqta, tire, pastki chiziq"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="field anim-up">
              <label htmlFor="su-password">Parol</label>
              <input
                id="su-password"
                type="password"
                autoComplete="new-password"
                placeholder={`kamida ${MIN_PASSWORD} belgi`}
                minLength={MIN_PASSWORD}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="field anim-up">
              <label htmlFor="su-repeat">Parolni takrorlang</label>
              <input
                id="su-repeat"
                type="password"
                autoComplete="new-password"
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
                required
              />
            </div>

            <p className="error-msg anim-up">{error}</p>

            <button type="submit" className="btn btn-primary anim-up" disabled={busy}>
              {busy ? "Yaratilmoqda…" : "Hisob yaratish"}
            </button>
          </form>

          <p className="note">
            Kompyuter ruxsati (<code>ai_in_pc</code>) yangi hisobda o'chiq
            bo'ladi — uni faqat admin yoqadi.
          </p>

          <p className="alt-link">
            Hisobingiz bormi? <Link to="/login">Kirish</Link>
          </p>
        </div>
      </div>
    </section>
  );
}
