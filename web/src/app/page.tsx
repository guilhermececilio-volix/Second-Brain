"use client";

import { useState } from "react";
import Chat from "./chat";
import Meeting from "./meeting";

type Aba = "chat" | "reuniao";

export default function Home() {
  const [aba, setAba] = useState<Aba>("chat");

  return (
    <div className="relative">
      {/* Navegação entre as telas */}
      <nav className="fixed top-4 right-4 z-10 flex gap-1 rounded-lg bg-surface border border-border p-1 text-xs">
        <button
          onClick={() => setAba("chat")}
          className={`px-3 py-1.5 rounded-md transition-colors ${
            aba === "chat" ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground"
          }`}
        >
          Conversar
        </button>
        <button
          onClick={() => setAba("reuniao")}
          className={`px-3 py-1.5 rounded-md transition-colors ${
            aba === "reuniao" ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground"
          }`}
        >
          Reunião
        </button>
      </nav>

      {aba === "chat" ? <Chat /> : <Meeting />}
    </div>
  );
}
