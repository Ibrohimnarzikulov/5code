/** Model tanlash sahifasi — lokal (Ollama) va cloud modellar. */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { brandModel, brandProvider } from "../brand";
import Shell from "../components/Shell";
import { useAuth } from "../context/AuthContext";

export default function Models() {
  const { user, setUser, toast } = useAuth();
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setModels(await api("/api/models"));
    } catch (err) {
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const isSelected = (option) =>
    user?.ai_provider === option.provider && user?.ai_model === option.model;

  async function choose(option) {
    if (!option.available) return;
    setSaving(`${option.provider}:${option.model}`);
    try {
      const updated = await api("/api/models/selection", {
        method: "PUT",
        body: JSON.stringify({ provider: option.provider, model: option.model }),
      });
      setUser(updated);
      toast(`Tanlandi: ${option.label}`);
    } catch (err) {
      toast(err.message, true);
    } finally {
      setSaving("");
    }
  }

  async function useDefault() {
    setSaving("default");
    try {
      const updated = await api("/api/models/selection", {
        method: "PUT",
        body: JSON.stringify({ provider: null, model: null }),
      });
      setUser(updated);
      toast("Standart modelga qaytarildi");
    } catch (err) {
      toast(err.message, true);
    } finally {
      setSaving("");
    }
  }

  const local = models.filter((m) => m.local);
  const cloud = models.filter((m) => !m.local);

  return (
    <Shell>
      <div className="page">
        <header className="page-head">
          <div>
            <h1>AI modellar</h1>
            <p className="sub">
              Qaysi model bilan ishlashni tanlang. Lokal modellar internetsiz
              ishlaydi va hech qanday ma'lumot kompyuterdan chiqmaydi.
            </p>
          </div>
          <button className="btn btn-ghost" onClick={load} disabled={loading}>
            ↻ Yangilash
          </button>
        </header>

        {loading ? (
          <p className="muted">Yuklanmoqda…</p>
        ) : (
          <>
            <Section
              title="Lokal — 5code"
              hint="Kompyuteringizda ishlaydi · maxfiy · tekin"
              models={local}
              isSelected={isSelected}
              saving={saving}
              onChoose={choose}
            />
            <Section
              title="Cloud"
              hint="Kuchliroq, lekin so'rovlar internetga chiqadi"
              models={cloud}
              isSelected={isSelected}
              saving={saving}
              onChoose={choose}
            />

            <div className="page-foot">
              <span className="muted">
                Joriy tanlov:{" "}
                <b>
                  {user?.ai_provider
                    ? `${brandProvider(user.ai_provider)} · ${brandModel(user.ai_model)}`
                    : "standart (serverdagi sozlama)"}
                </b>
              </span>
              {user?.ai_provider && (
                <button
                  className="btn btn-ghost"
                  onClick={useDefault}
                  disabled={saving === "default"}
                >
                  Standartga qaytarish
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}

function Section({ title, hint, models, isSelected, saving, onChoose }) {
  if (!models.length) return null;

  return (
    <section className="model-section">
      <h2>
        {title} <small>{hint}</small>
      </h2>
      <div className="model-grid stagger">
        {models.map((option) => {
          const key = `${option.provider}:${option.model}`;
          const selected = isSelected(option);
          return (
            <button
              key={key}
              className={[
                "model-card",
                selected ? "selected" : "",
                option.available ? "" : "unavailable",
              ].join(" ")}
              onClick={() => onChoose(option)}
              disabled={!option.available || saving === key}
              title={option.available ? "" : "Hozircha mavjud emas"}
            >
              <div className="model-top">
                <span className="model-glyph">{option.local ? "◆" : "☁"}</span>
                <b>{option.label}</b>
                {option.recommended && <span className="pill pill-on">tavsiya</span>}
                {selected && <span className="pill pill-admin">tanlangan</span>}
              </div>
              <p>{option.description}</p>
              <div className="model-foot">
                <code>{option.local ? brandModel(option.model) : option.model}</code>
                {!option.available && (
                  <span className="pill">
                    {option.local ? "yuklanmagan" : "kalit yo'q"}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
