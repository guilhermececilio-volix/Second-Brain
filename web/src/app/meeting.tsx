"use client";

import { useEffect, useState } from "react";
import Strands from "./strands";

const API = "http://127.0.0.1:8001";

// --- Tipos que espelham o backend (src/meeting.py) ---
type Ponto = {
  tipo: "decisao" | "tarefa" | "data" | "contexto";
  texto: string;
  responsavel: string | null;
  prazo: string | null;
  data_iso: string | null;
};
type Extraction = {
  titulo: string;
  resumo: string;
  participantes: string[];
  pontos: Ponto[];
};
// Evento proposto para a agenda (derivado dos pontos com data_iso).
type EventoProposto = {
  titulo: string;
  data_iso: string;
  duracao_min: number;
  criado?: string; // link do evento após criar
};

const TIPO_LABEL: Record<Ponto["tipo"], string> = {
  decisao: "Decisão",
  tarefa: "Tarefa",
  data: "Data",
  contexto: "Contexto",
};
const TIPO_COR: Record<Ponto["tipo"], string> = {
  decisao: "var(--accent)",
  tarefa: "#eab308",
  data: "#06b6d4",
  contexto: "var(--muted)",
};

async function postJSON(path: string, body: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Erro ${res.status}`);
  return res.json();
}

export default function Meeting() {
  const [transcript, setTranscript] = useState("");
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<{ mae: string; filhas: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Integração com a agenda: status e eventos já criados (por data_iso).
  const [calAuth, setCalAuth] = useState<boolean | null>(null);
  const [criados, setCriados] = useState<Record<string, string>>({}); // data_iso -> link

  // Descobre se o Google Calendar está autorizado (uma vez, ao montar).
  useEffect(() => {
    fetch(`${API}/calendar/status`)
      .then((r) => r.json())
      .then((r) => setCalAuth(!!r.authorized))
      .catch(() => setCalAuth(false));
  }, []);

  // Eventos propostos = pontos com data_iso concreto.
  const eventos: EventoProposto[] = (extraction?.pontos ?? [])
    .filter((p) => p.data_iso)
    .map((p) => ({
      titulo: p.texto.length <= 80 ? p.texto : p.texto.slice(0, 77) + "...",
      data_iso: p.data_iso as string,
      duracao_min: 60,
    }));

  async function criarEvento(ev: EventoProposto) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await postJSON("/calendar/event", {
        titulo: ev.titulo,
        data_iso: ev.data_iso,
        duracao_min: ev.duracao_min,
        descricao: `Da reunião: ${extraction?.titulo ?? ""}`,
      });
      if (r.kind === "error") setError(r.message);
      else setCriados((prev) => ({ ...prev, [ev.data_iso]: r.link }));
    } catch {
      setError("Não consegui criar o evento agora.");
    } finally {
      setBusy(false);
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    // .docx é binário (Word/Teams): manda pro backend ler e já extrair.
    // .txt/.vtt são texto: só carrega no campo para o usuário revisar/extrair.
    if (file.name.toLowerCase().endsWith(".docx")) {
      await extrairDocx(file);
    } else {
      setTranscript(await file.text());
    }
    e.target.value = ""; // permite re-selecionar o mesmo arquivo
  }

  async function extrairDocx(file: File) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/meeting/extract-docx`, { method: "POST", body: form });
      if (!res.ok) throw new Error();
      const r = await res.json();
      if (r.kind === "error") setError(r.message);
      else setExtraction(r as Extraction);
    } catch {
      setError("Não consegui ler o .docx agora. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  async function extrair() {
    const texto = transcript.trim();
    if (!texto || busy) return;
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const r = await postJSON("/meeting/extract", { transcript: texto });
      if (r.kind === "error") setError(r.message);
      else setExtraction(r as Extraction);
    } catch {
      setError("Não consegui extrair agora. A cota do Gemini pode ter estourado — tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  async function salvar() {
    if (!extraction || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await postJSON("/meeting/save", extraction);
      if (r.kind === "error") setError(r.message);
      else {
        setSaved({ mae: r.mae, filhas: r.filhas });
        setExtraction(null);
        setTranscript("");
      }
    } catch {
      setError("Não consegui salvar agora. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  // Edição de um ponto no preview.
  function updatePonto(i: number, patch: Partial<Ponto>) {
    if (!extraction) return;
    setExtraction({
      ...extraction,
      pontos: extraction.pontos.map((p, idx) => (idx === i ? { ...p, ...patch } : p)),
    });
  }
  function removePonto(i: number) {
    if (!extraction) return;
    setExtraction({ ...extraction, pontos: extraction.pontos.filter((_, idx) => idx !== i) });
  }

  return (
    <div className="flex flex-col min-h-screen max-w-2xl mx-auto w-full px-4 pb-10">
      <header className="pt-8 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Reunião → Notas</h1>
        <p className="mt-1 text-sm text-muted">
          Cole ou suba a transcrição — eu extraio os pontos importantes e crio as notas linkadas.
        </p>
      </header>

      {/* Entrada da transcrição */}
      {!extraction && !saved && (
        <div className="space-y-3">
          <textarea
            className="w-full min-h-[200px] resize-y rounded-2xl bg-surface border border-border focus:border-accent transition-colors outline-none text-foreground placeholder:text-faint text-[0.95rem] p-4"
            placeholder="Cole aqui a transcrição da reunião..."
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <label className="text-xs text-muted cursor-pointer hover:text-foreground transition-colors">
              <input type="file" accept=".docx,.txt,.md,.vtt" className="hidden" onChange={onFile} />
              ↑ subir arquivo (.docx do Teams, ou .txt)
            </label>
            <div className="flex-1" />
            <button
              onClick={extrair}
              disabled={busy || !transcript.trim()}
              className="rounded-lg bg-accent hover:bg-accent-bright disabled:opacity-40 disabled:hover:bg-accent transition-colors px-4 py-2 text-sm font-semibold text-[#0a0a0b]"
            >
              {busy ? "Extraindo…" : "Extrair pontos"}
            </button>
          </div>
        </div>
      )}

      {/* Estado "pensando" reusando o Strands */}
      {busy && (
        <div className="relative w-full h-[120px] overflow-hidden rounded-2xl bg-surface border border-border mt-4">
          <Strands className="absolute inset-0" style={{ width: "100%", height: "100%" }}
            count={3} speed={0.9} glow={2.6} intensity={0.8} taper={3} scale={2.6} />
          <div className="absolute bottom-2 left-0 right-0 text-xs text-muted text-center">
            processando reunião…
          </div>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-[#ef4444]">{error}</p>}

      {/* Preview editável */}
      {extraction && !busy && (
        <div className="space-y-4">
          <div className="rounded-2xl bg-surface border border-border p-4">
            <input
              className="w-full bg-transparent outline-none text-lg font-bold text-foreground"
              value={extraction.titulo}
              onChange={(e) => setExtraction({ ...extraction, titulo: e.target.value })}
            />
            <textarea
              className="w-full mt-2 bg-transparent outline-none resize-y text-sm text-text"
              rows={2}
              value={extraction.resumo}
              onChange={(e) => setExtraction({ ...extraction, resumo: e.target.value })}
            />
            {extraction.participantes.length > 0 && (
              <p className="mt-1 text-xs text-muted">
                Participantes: {extraction.participantes.join(", ")}
              </p>
            )}
          </div>

          <div className="text-xs text-muted">
            {extraction.pontos.length} ponto(s) — revise, edite ou remova antes de salvar:
          </div>

          {extraction.pontos.map((p, i) => (
            <div key={i} className="rounded-xl bg-surface-2 border border-[color:var(--border-soft)] p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                  style={{ color: TIPO_COR[p.tipo], border: `1px solid ${TIPO_COR[p.tipo]}` }}>
                  {TIPO_LABEL[p.tipo]}
                </span>
                <div className="flex-1" />
                <button onClick={() => removePonto(i)}
                  className="text-xs text-faint hover:text-[#ef4444] transition-colors">
                  remover
                </button>
              </div>
              <textarea
                className="w-full bg-transparent outline-none resize-y text-[0.95rem] text-foreground"
                rows={2}
                value={p.texto}
                onChange={(e) => updatePonto(i, { texto: e.target.value })}
              />
              {(p.tipo === "tarefa" || p.responsavel || p.prazo) && (
                <div className="flex gap-2 mt-2">
                  <input
                    className="flex-1 bg-transparent border border-[color:var(--border-soft)] rounded px-2 py-1 text-xs text-text outline-none focus:border-accent"
                    placeholder="responsável"
                    value={p.responsavel ?? ""}
                    onChange={(e) => updatePonto(i, { responsavel: e.target.value || null })}
                  />
                  <input
                    className="flex-1 bg-transparent border border-[color:var(--border-soft)] rounded px-2 py-1 text-xs text-text outline-none focus:border-accent"
                    placeholder="prazo"
                    value={p.prazo ?? ""}
                    onChange={(e) => updatePonto(i, { prazo: e.target.value || null })}
                  />
                </div>
              )}
            </div>
          ))}

          {/* Adicionar à agenda — só aparece se houver eventos com data concreta */}
          {eventos.length > 0 && (
            <div className="rounded-2xl bg-surface border border-[#06b6d4]/30 p-4 space-y-2">
              <p className="text-sm font-semibold text-foreground">📅 Adicionar à agenda</p>
              {calAuth === false && (
                <p className="text-xs text-muted">
                  Google Calendar não conectado. Rode{" "}
                  <code className="text-faint">python scripts/google_auth.py</code> uma vez para ativar.
                </p>
              )}
              {eventos.map((ev, i) => {
                const link = criados[ev.data_iso];
                const quando = ev.data_iso.replace("T", " às ").slice(0, 16);
                return (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <div className="flex-1">
                      <span className="text-foreground">{ev.titulo}</span>
                      <span className="text-xs text-muted ml-2">{quando}</span>
                    </div>
                    {link ? (
                      <a href={link} target="_blank" rel="noreferrer"
                        className="text-xs text-accent hover:text-accent-bright">✓ criado ↗</a>
                    ) : (
                      <button onClick={() => criarEvento(ev)} disabled={busy || calAuth !== true}
                        className="text-xs rounded-md border border-[#06b6d4]/50 text-[#06b6d4] hover:bg-[#06b6d4]/10 disabled:opacity-40 px-2 py-1 transition-colors">
                        criar evento
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={() => { setExtraction(null); setError(null); }}
              className="rounded-lg border border-border hover:border-muted transition-colors px-4 py-2 text-sm text-muted">
              Descartar
            </button>
            <div className="flex-1" />
            <button onClick={salvar} disabled={busy || extraction.pontos.length === 0}
              className="rounded-lg bg-accent hover:bg-accent-bright disabled:opacity-40 transition-colors px-4 py-2 text-sm font-semibold text-[#0a0a0b]">
              Salvar {extraction.pontos.length} nota(s) + reunião
            </button>
          </div>
        </div>
      )}

      {/* Confirmação de salvo */}
      {saved && (
        <div className="rounded-2xl bg-surface border border-accent/40 p-4">
          <p className="text-sm text-foreground font-semibold">✓ Reunião salva</p>
          <p className="mt-1 text-xs text-muted">
            Nota-mãe + {saved.filhas.length} nota(s) criadas e linkadas no seu vault.
          </p>
          <button onClick={() => setSaved(null)}
            className="mt-3 text-xs text-accent hover:text-accent-bright transition-colors">
            + processar outra reunião
          </button>
        </div>
      )}
    </div>
  );
}
