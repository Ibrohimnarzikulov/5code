/** AI yasagan saytning jonli ko'rinishi (sandbox iframe). */

import { useEffect, useState } from "react";

import { api } from "../api";
import { useAuth } from "../context/AuthContext";

export default function ArtifactPanel({ artifact, onClose }) {
  const { toast } = useAuth();
  const [tab, setTab] = useState("preview");
  const [code, setCode] = useState("");
  const [nonce, setNonce] = useState(0);

  // Yangi artifact / yangi versiya kelganda ko'rinishga qaytamiz
  useEffect(() => {
    setTab("preview");
    setCode("");
    setNonce(0);
  }, [artifact.id, artifact.version]);

  useEffect(() => {
    if (tab !== "code" || code) return;
    let cancelled = false;

    (async () => {
      try {
        const full = await api(`/api/artifacts/${artifact.id}`);
        if (!cancelled) setCode(full.html);
      } catch (err) {
        if (!cancelled) setCode(`Xatolik: ${err.message}`);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [tab, code, artifact.id]);

  async function download() {
    try {
      const full = await api(`/api/artifacts/${artifact.id}`);
      const blob = new Blob([full.html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const safeName =
        full.title.replace(/[^\p{L}\p{N}\-_ ]/gu, "").trim() || "sayt";
      link.href = url;
      link.download = `${safeName}.html`;
      link.click();
      URL.revokeObjectURL(url);
      toast("Yuklab olindi");
    } catch (err) {
      toast(err.message, true);
    }
  }

  const src = `/a/${artifact.token}?v=${artifact.version}&r=${nonce}`;

  return (
    <aside className="artifact-panel glass">
      <header className="artifact-head">
        <button className="back-to-chat icon-btn" onClick={onClose} title="Orqaga">
          ←
        </button>

        <div className="artifact-title">
          <b>{artifact.title}</b>
          <span className="pill">v{artifact.version}</span>
        </div>

        <div className="artifact-tabs">
          <button
            className={`tab${tab === "preview" ? " active" : ""}`}
            onClick={() => setTab("preview")}
          >
            Ko'rinish
          </button>
          <button
            className={`tab${tab === "code" ? " active" : ""}`}
            onClick={() => setTab("code")}
          >
            Kod
          </button>
        </div>

        <div className="artifact-actions">
          <button
            className="icon-btn"
            onClick={() => setNonce((n) => n + 1)}
            title="Yangilash"
          >
            ↻
          </button>
          <button
            className="icon-btn"
            onClick={() =>
              window.open(`/a/${artifact.token}`, "_blank", "noopener")
            }
            title="Yangi oynada"
          >
            ↗
          </button>
          <button className="icon-btn" onClick={download} title="Yuklab olish">
            ⤓
          </button>
          <button className="icon-btn" onClick={onClose} title="Yopish">
            ✕
          </button>
        </div>
      </header>

      <div className="artifact-body">
        {tab === "preview" ? (
          <iframe
            key={src}
            src={src}
            title={artifact.title}
            /* allow-same-origin YO'Q — artifact bizning origin'ga kira olmaydi */
            sandbox="allow-scripts allow-forms allow-popups allow-modals"
          />
        ) : (
          <pre className="artifact-code">
            <code>{code || "Yuklanmoqda…"}</code>
          </pre>
        )}
      </div>
    </aside>
  );
}
