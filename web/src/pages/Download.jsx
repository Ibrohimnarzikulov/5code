/** Yuklab olish — `5code` ni bir buyruq bilan o'rnatish. */

import { useEffect, useState } from "react";

import { api } from "../api";
import Shell from "../components/Shell";
import { useAuth } from "../context/AuthContext";

const INSTALL_CMD =
  "curl -fsSL https://raw.githubusercontent.com/Ibrohimnarzikulov/5code/main/install.sh | bash";

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

  const model = info?.local_model ?? "5code";

  const usageCmd = [
    `${model}                              # interaktiv suhbat`,
    `${model} "python da fayl o'qish"      # bir martalik savol`,
    `cat main.py | ${model} "shuni tushuntir"`,
    `${model} --web                        # web interfeysni ochish`,
    `${model} --update                     # modelni qayta yig'ish`,
    `${model} --status                     # holat tekshiruvi`,
  ].join("\n");

  return (
    <Shell>
      <div className="page">
        <header className="page-head">
          <div>
            <h1>Yuklab olish</h1>
            <p className="sub">
              Bitta buyruq bilan <code>{model}</code> ni o'z terminalingizga
              o'rnating. Lokal model internetsiz ishlaydi — hech qanday
              ma'lumot kompyuterdan chiqmaydi.
            </p>
          </div>
        </header>

        <div className="code-list stagger">
          <CodeBlock title="O'rnatish" code={INSTALL_CMD} onCopy={copy} />
          <CodeBlock title="Ishlatish" code={usageCmd} onCopy={copy} />
        </div>
      </div>
    </Shell>
  );
}
