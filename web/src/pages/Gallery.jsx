/** Saytlarim — AI yasagan barcha artifactlar galereyasi. */

import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import ArtifactPanel from "../components/ArtifactPanel";
import Shell from "../components/Shell";
import { useAuth } from "../context/AuthContext";

export default function Gallery() {
  const { toast } = useAuth();
  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setArtifacts(await api("/api/artifacts"));
    } catch (err) {
      toast(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(artifact, event) {
    event.stopPropagation();
    if (!confirm(`"${artifact.title}" o'chirilsinmi?`)) return;
    try {
      await api(`/api/artifacts/${artifact.id}`, { method: "DELETE" });
      if (open?.id === artifact.id) setOpen(null);
      setArtifacts((list) => list.filter((a) => a.id !== artifact.id));
      toast("O'chirildi");
    } catch (err) {
      toast(err.message, true);
    }
  }

  return (
    <Shell wide={Boolean(open)}>
      <div className="page">
        <header className="page-head">
          <div>
            <h1>Saytlarim</h1>
            <p className="sub">
              AI yasagan saytlar. Kartochkani bosing — o'ng panelda jonli
              ochiladi.
            </p>
          </div>
          <button className="btn btn-ghost" onClick={load} disabled={loading}>
            ↻ Yangilash
          </button>
        </header>

        {loading && <p className="muted">Yuklanmoqda…</p>}

        {!loading && artifacts.length === 0 && (
          <p className="muted">
            Hozircha sayt yasalmagan. Suhbatda «menga portfolio sayt yasab ber»
            deb yozib ko'ring.
          </p>
        )}

        <div className="gallery stagger">
          {artifacts.map((artifact) => (
            <div
              className="gallery-card"
              key={artifact.id}
              onClick={() => setOpen(artifact)}
            >
              <iframe
                className="thumb"
                src={`/a/${artifact.token}`}
                title={artifact.title}
                loading="lazy"
                sandbox="allow-scripts"
              />
              <div className="meta">
                <b>{artifact.title}</b>
                <span className="pill">v{artifact.version}</span>
                <button
                  className="icon-btn"
                  title="O'chirish"
                  onClick={(e) => remove(artifact, e)}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {open && <ArtifactPanel artifact={open} onClose={() => setOpen(null)} />}
    </Shell>
  );
}
