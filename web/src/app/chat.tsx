"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const API = "http://127.0.0.1:8000";

// --- Tipos das mensagens no histórico da conversa ---
type Msg =
  | { role: "user"; text: string }
  | { role: "assistant"; kind: "answer"; text: string; sources: string[] }
  | { role: "assistant"; kind: "saved"; notePath: string; content: string; acao: string }
  | { role: "assistant"; kind: "duvida"; notePath: string; origin: string }
  | { role: "assistant"; kind: "error"; text: string };

async function postJSON(path: string, body: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Erro ${res.status}`);
  return res.json();
}

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  // Rola para a última mensagem quando algo muda.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  function push(m: Msg) {
    setMessages((prev) => [...prev, m]);
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    push({ role: "user", text });
    setInput("");
    setBusy(true);
    try {
      const r = await postJSON("/chat", { text });
      handleServer(r, text);
    } catch {
      push({ role: "assistant", kind: "error", text: "⏳ Não consegui falar com o cérebro agora. A cota do Gemini pode ter atingido o limite — tente de novo em instantes." });
    } finally {
      setBusy(false);
    }
  }

  function handleServer(r: Record<string, unknown>, origin: string) {
    const kind = r.kind as string;
    if (kind === "answer") {
      push({ role: "assistant", kind: "answer", text: r.text as string, sources: (r.sources as string[]) ?? [] });
    } else if (kind === "saved") {
      push({ role: "assistant", kind: "saved", notePath: r.note_path as string, content: r.content as string, acao: (r.acao as string) ?? "criada" });
    } else if (kind === "duvida") {
      push({ role: "assistant", kind: "duvida", notePath: r.note_path as string, origin });
    } else {
      push({ role: "assistant", kind: "error", text: (r.message as string) ?? "Algo deu errado." });
    }
  }

  async function resolveDuvida(i: number, action: "update" | "create") {
    const m = messages[i];
    if (m.role !== "assistant" || m.kind !== "duvida") return;
    setMessages((prev) => prev.filter((_, idx) => idx !== i));
    setBusy(true);
    try {
      const r = action === "update"
        ? await postJSON("/update", { note_path: m.notePath, text: m.origin })
        : await postJSON("/create", { text: m.origin });
      handleServer(r, m.origin);
    } finally {
      setBusy(false);
    }
  }

  async function undo(i: number) {
    const m = messages[i];
    if (m.role !== "assistant" || m.kind !== "saved") return;
    await postJSON("/delete", { note_path: m.notePath });
    setMessages((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function saveEdit(i: number) {
    const m = messages[i];
    if (m.role !== "assistant" || m.kind !== "saved") return;
    const r = await postJSON("/edit", { note_path: m.notePath, content: draft });
    setMessages((prev) => prev.map((msg, idx) => (idx === i ? { ...m, content: r.content } : msg)));
    setEditing(null);
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto w-full px-4">
      {/* Cabeçalho */}
      <header className="pt-8 pb-6">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/volix_logo_verde.png" alt="Volix" className="h-20 w-auto" />
        <h1 className="mt-5 text-2xl font-bold tracking-tight text-foreground">Second Brain</h1>
        <p className="mt-1 text-sm text-muted">
          Fale naturalmente — eu descubro se você quer guardar, atualizar ou perguntar.
        </p>
      </header>

      {/* Conversa */}
      <div className="flex-1 overflow-y-auto space-y-3 pb-4">
        {messages.length === 0 && (
          <div className="text-sm text-faint mt-8 text-center">
            Comece guardando um pensamento ou fazendo uma pergunta.
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className="animate-rise">
            {m.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-surface-2 border border-[color:var(--border-soft)] px-4 py-2.5 text-[0.95rem] text-foreground">
                  {m.text}
                </div>
              </div>
            ) : (
              <div className="flex justify-start">
                <div className="max-w-[92%] w-full rounded-2xl rounded-bl-md bg-surface border border-border px-4 py-3">
                  {m.kind === "answer" && <Answer text={m.text} sources={m.sources} />}
                  {m.kind === "error" && <p className="text-sm text-muted">{m.text}</p>}
                  {m.kind === "duvida" && (
                    <Duvida notePath={m.notePath} onUpdate={() => resolveDuvida(i, "update")} onCreate={() => resolveDuvida(i, "create")} />
                  )}
                  {m.kind === "saved" && (
                    <Saved
                      m={m}
                      editing={editing === i}
                      draft={draft}
                      onStartEdit={() => { setEditing(i); setDraft(m.content); }}
                      onDraft={setDraft}
                      onSaveEdit={() => saveEdit(i)}
                      onCancelEdit={() => setEditing(null)}
                      onUndo={() => undo(i)}
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {busy && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-md bg-surface border border-border px-4 py-3">
              <Dots />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Campo de entrada */}
      <div className="pb-6 pt-2">
        <div className="flex items-end gap-2 rounded-2xl bg-surface border border-border focus-within:border-accent transition-colors px-3 py-2 shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
          <textarea
            className="flex-1 resize-none bg-transparent outline-none text-foreground placeholder:text-faint text-[0.98rem] py-1.5 max-h-40"
            rows={1}
            placeholder="Escreva um pensamento ou uma pergunta..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
          />
          <button
            onClick={send}
            disabled={busy || !input.trim()}
            aria-label="Enviar"
            className="shrink-0 grid place-items-center w-9 h-9 rounded-lg bg-accent hover:bg-accent-bright disabled:opacity-40 disabled:hover:bg-accent transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0a0b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function Answer({ text, sources }: { text: string; sources: string[] }) {
  return (
    <div>
      <div className="text-[0.95rem] leading-relaxed text-text space-y-2
        [&_strong]:text-foreground [&_strong]:font-semibold
        [&_ul]:space-y-1.5 [&_ul]:my-1
        [&_li]:relative [&_li]:pl-4
        [&_li]:before:content-[''] [&_li]:before:absolute [&_li]:before:left-0
        [&_li]:before:top-[0.62em] [&_li]:before:w-[5px] [&_li]:before:h-[5px]
        [&_li]:before:rounded-full [&_li]:before:bg-accent
        [&_a]:text-accent [&_a]:no-underline hover:[&_a]:underline
        [&_code]:font-mono [&_code]:text-[0.85em] [&_code]:text-accent-bright">
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
      {sources.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[color:var(--border-soft)]">
          <div className="text-xs uppercase tracking-wider text-faint mb-1.5">Fontes</div>
          <div className="flex flex-wrap gap-1.5">
            {sources.map((s) => (
              <span key={s} className="text-xs text-muted bg-surface-2 border border-[color:var(--border-soft)] rounded-md px-2 py-0.5">
                {prettyTitle(s)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Saved({
  m, editing, draft, onStartEdit, onDraft, onSaveEdit, onCancelEdit, onUndo,
}: {
  m: { notePath: string; content: string; acao: string };
  editing: boolean; draft: string;
  onStartEdit: () => void; onDraft: (v: string) => void;
  onSaveEdit: () => void; onCancelEdit: () => void; onUndo: () => void;
}) {
  const verbo = m.acao === "atualizada" ? "Atualizei" : "Guardei";
  const [open, setOpen] = useState(false);
  return (
    <div>
      <p className="text-[0.95rem] text-text">
        <span className="text-accent">✓</span> {verbo} a nota{" "}
        <span className="font-mono text-xs text-muted">{noteName(m.notePath)}</span>.
      </p>

      {editing ? (
        <div className="mt-3">
          <textarea
            className="w-full h-48 rounded-lg bg-surface-2 border border-border focus:border-accent outline-none p-3 text-sm font-mono text-text"
            value={draft}
            onChange={(e) => onDraft(e.target.value)}
          />
          <div className="flex gap-2 mt-2">
            <BtnPrimary onClick={onSaveEdit}>Salvar</BtnPrimary>
            <Btn onClick={onCancelEdit}>Cancelar</Btn>
          </div>
        </div>
      ) : (
        <div className="mt-2.5 flex items-center gap-2">
          <Btn onClick={() => setOpen((v) => !v)}>{open ? "Ocultar" : "Ver nota"}</Btn>
          <Btn onClick={onStartEdit}>Editar</Btn>
          <Btn onClick={onUndo}>Desfazer</Btn>
        </div>
      )}

      {open && !editing && (
        <pre className="mt-3 rounded-lg bg-background border border-[color:var(--border-soft)] p-3 text-xs font-mono text-muted overflow-x-auto whitespace-pre-wrap">
          {m.content}
        </pre>
      )}
    </div>
  );
}

function Duvida({ notePath, onUpdate, onCreate }: { notePath: string; onUpdate: () => void; onCreate: () => void }) {
  return (
    <div>
      <p className="text-[0.95rem] text-text">
        🤔 Isso parece ter a ver com a nota{" "}
        <span className="font-mono text-xs text-muted">{noteName(notePath)}</span>. Atualizar ela ou criar uma nova?
      </p>
      <div className="mt-2.5 flex gap-2">
        <BtnPrimary onClick={onUpdate}>Atualizar essa</BtnPrimary>
        <Btn onClick={onCreate}>Criar nova</Btn>
      </div>
    </div>
  );
}

function Btn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-sm px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-text hover:bg-border hover:text-foreground transition-colors"
    >
      {children}
    </button>
  );
}

function BtnPrimary({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-sm px-3 py-1.5 rounded-lg bg-accent text-[#0a0a0b] font-medium hover:bg-accent-bright transition-colors"
    >
      {children}
    </button>
  );
}

function Dots() {
  return (
    <div className="flex gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

// Mostra só o nome legível da nota (sem a pasta Capturas/ e sem timestamp longo).
function noteName(path: string): string {
  const base = path.split("/").pop() ?? path;
  return base.replace(/\.md$/, "");
}

// Título amigável a partir do nome do arquivo: remove data/hora e troca hífens
// por espaços. Ex.: "2026-07-06-142152-Reunião-com-IA" -> "Reunião com IA".
function prettyTitle(path: string): string {
  const base = noteName(path);
  const semData = base.replace(/^\d{4}-\d{2}-\d{2}-\d{6}-/, "");
  return semData.replace(/-/g, " ") || base;
}
