/** Yuklab olish — `5code` o'rnatish buyruqlari va loyiha arxivi. */

import { useEffect, useState } from "react";

import { api, getToken } from "../api";
import Shell from "../components/Shell";
import { useAuth } from "../context/AuthContext";

function CodeBlock({ title, code, onCopy }) {
  return (
    <div className="code-card">
      <div className="code-head">
        <b>{title}</b>
        <button className="btn btn-ghost" onClick={() => onCopy(code)}>
          ⧉ Nusxa olish
        </button>
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function Download() {
  const { toast } = useAuth();
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/download/info")
      .then(setInfo)
      .catch((err) => toast(err.message, true));
  }, [toast]);

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("Nusxa olindi");
    } catch {
      toast("Nusxa olib bo'lmadi — qo'lda belgilang", true);
    }
  }

  /** Arxivni token bilan olib, brauzerga saqlaydi. */
  async function downloadZip() {
    setBusy(true);
    try {
      const response = await fetch("/api/download/source", {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error(`Server javobi: ${response.status}`);

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = info?.archive_name ?? "codeassistant.zip";
      link.click();
      URL.revokeObjectURL(url);
      toast("Arxiv yuklab olindi");
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  }

  const base = info?.base_model ?? "qwen2.5-coder:14b";
  const model = info?.local_model ?? "5code";

  const installCmd = [
    "# 1) Ollama (agar yo'q bo'lsa)",
    "#    https://ollama.com/download",
    "",
    "# 2) Asos modelni yuklash (~9GB, bir marta)",
    `ollama pull ${base}`,
    "",
    `# 3) ${model} buyrug'ini o'rnatish`,
    "unzip codeassistant.zip && cd codeassistant",
    "./ollama/install.sh",
  ].join("\n");

  const usageCmd = [
    `${model}                              # interaktiv suhbat`,
    `${model} "python da fayl o'qish"      # bir martalik savol`,
    `cat main.py | ${model} "shuni tushuntir"`,
    `${model} --web                        # web interfeysni ochish`,
    `${model} --update                     # modelni qayta yig'ish`,
    `${model} --status                     # holat tekshiruvi`,
  ].join("\n");

  const serverCmd = [
    "cp .env.example .env",
    "./run.sh          # backend " +
      (info?.backend_port ?? 1221) +
      " + frontend " +
      (info?.frontend_port ?? 1991),
  ].join("\n");

  return (
    <Shell>
      <div className="page">
        <header className="page-head">
          <div>
            <h1>Yuklab olish</h1>
            <p className="sub">
              Loyiha kodini oling va <code>{model}</code> ni o'z terminalingizga
              o'rnating. Lokal model internetsiz ishlaydi — hech qanday ma'lumot
              kompyuterdan chiqmaydi.
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={downloadZip}
            disabled={busy}
          >
            {busy ? "Tayyorlanmoqda…" : "⤓ Kodni yuklab olish (.zip)"}
          </button>
        </header>

        <div className="warn-box">
          Arxivga <code>.venv</code>, <code>node_modules</code>,{" "}
          <code>.env</code>, baza va <code>workspace</code> kirmaydi — faqat
          manba kodi.
        </div>

        <div className="code-list stagger">
          <CodeBlock title="O'rnatish" code={installCmd} onCopy={copy} />
          <CodeBlock title="Ishlatish" code={usageCmd} onCopy={copy} />
          <CodeBlock title="Serverni ishga tushirish" code={serverCmd} onCopy={copy} />
        </div>
      </div>
    </Shell>
  );
}
