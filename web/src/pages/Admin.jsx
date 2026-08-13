/** Admin paneli — foydalanuvchilar va `ai_in_pc` ruxsati. */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import Shell from "../components/Shell";
import { useAuth } from "../context/AuthContext";

export default function Admin() {
  const { user: me, refresh, toast } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ username: "", password: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await api("/api/users"));
    } catch (err) {
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  /** Bitta foydalanuvchining `ai_in_pc` holatini almashtiradi. */
  async function toggleAiInPc(target, enabled) {
    // Optimistik yangilash — javob kutmasdan
    setUsers((list) =>
      list.map((u) => (u.id === target.id ? { ...u, ai_in_pc: enabled } : u)),
    );
    try {
      await api(`/api/users/${target.id}`, {
        method: "PATCH",
        body: JSON.stringify({ ai_in_pc: enabled }),
      });
      toast(`${target.username}: ai_in_pc ${enabled ? "yoqildi" : "o'chirildi"}`);
      if (target.id === me.id) await refresh();
    } catch (err) {
      setUsers((list) =>
        list.map((u) => (u.id === target.id ? { ...u, ai_in_pc: !enabled } : u)),
      );
      toast(err.message, true);
    }
  }

  /** Hamma foydalanuvchiga birdaniga ruxsat berish/olib qo'yish. */
  async function toggleAll(enabled) {
    const label = enabled ? "berilsinmi" : "olib qo'yilsinmi";
    if (!confirm(`Barcha foydalanuvchilarga ai_in_pc ruxsati ${label}?`)) return;

    setBusy(true);
    try {
      const updated = await api(`/api/users/ai-in-pc/all?enabled=${enabled}`, {
        method: "POST",
      });
      setUsers(updated);
      await refresh();
      toast(
        enabled
          ? `Hammaga ruxsat berildi (${updated.length} ta)`
          : `Hammadan ruxsat olindi (${updated.length} ta)`,
      );
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function createUser(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/api/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ username: "", password: "" });
      toast("Foydalanuvchi qo'shildi");
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function removeUser(target) {
    if (!confirm(`${target.username} o'chirilsinmi? Bu qaytarib bo'lmaydi.`)) return;
    try {
      await api(`/api/users/${target.id}`, { method: "DELETE" });
      toast("O'chirildi");
      await load();
    } catch (err) {
      toast(err.message, true);
    }
  }

  const granted = users.filter((u) => u.ai_in_pc).length;

  return (
    <Shell>
      <div className="page">
        <header className="page-head">
          <div>
            <h1>Foydalanuvchilar</h1>
            <p className="sub">
              {users.length} ta hisob · {granted} tasida kompyuter ruxsati bor
            </p>
          </div>
          <div className="row">
            <button
              className="btn btn-primary"
              onClick={() => toggleAll(true)}
              disabled={busy || loading}
            >
              Hammaga ai_in_pc berish
            </button>
            <button
              className="btn btn-ghost btn-danger"
              onClick={() => toggleAll(false)}
              disabled={busy || loading}
            >
              Hammadan olish
            </button>
          </div>
        </header>

        <div className="warn-box">
          <b>Diqqat:</b> <code>ai_in_pc</code> foydalanuvchiga AI orqali
          terminal buyruqlarini bajarish va fayllar bilan ishlash imkonini
          beradi (workspace papkasi ichida). Faqat ishonchli odamlarga bering.
        </div>

        {loading ? (
          <p className="muted">Yuklanmoqda…</p>
        ) : (
          <div className="user-grid stagger">
            {users.map((u) => (
              <div className="user-card" key={u.id}>
                <div className="avatar">
                  {u.username.slice(0, 2).toUpperCase()}
                </div>
                <div className="grow">
                  <b>{u.username}</b>
                  <div className="badges">
                    <span
                      className={`pill${u.role === "admin" ? " pill-admin" : ""}`}
                    >
                      {u.role}
                    </span>
                    {!u.is_active && <span className="pill">bloklangan</span>}
                    {u.ai_provider && (
                      <span className="pill">{u.ai_model}</span>
                    )}
                  </div>
                </div>

                <label className="switch" title="Kompyuter ruxsati">
                  <input
                    type="checkbox"
                    checked={u.ai_in_pc}
                    onChange={(e) => toggleAiInPc(u, e.target.checked)}
                  />
                  <span className="track" />
                  ai_in_pc
                </label>

                <button
                  className="btn btn-ghost btn-danger"
                  onClick={() => removeUser(u)}
                  disabled={u.id === me.id}
                >
                  O'chirish
                </button>
              </div>
            ))}
          </div>
        )}

        <form className="new-user" onSubmit={createUser}>
          <div className="field">
            <label htmlFor="nu-username">Yangi login</label>
            <input
              id="nu-username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              minLength={3}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="nu-password">Parol</label>
            <input
              id="nu-password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              minLength={4}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Qo'shish
          </button>
        </form>
      </div>
    </Shell>
  );
}
