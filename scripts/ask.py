"""
Pergunta ao seu Second Brain pela linha de comando (RAG).

A pergunta vem como argumento; sem argumento, entra em modo interativo.

Pré-requisitos:
  - banco no ar e vault já ingerido (python scripts/ingest.py)
  - .env com GEMINI_API_KEY e DATABASE_URL

Rode da raiz do projeto:
    python scripts/ask.py "O que anotei sobre produtividade?"
    python scripts/ask.py          # modo interativo
"""

import sys
from pathlib import Path

# Permite rodar o script de qualquer lugar (adiciona a raiz ao path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.query import answer


def _responder(pergunta: str) -> None:
    resultado = answer(pergunta)
    print(f"\n{resultado.text}\n")
    if resultado.sources:
        print("Fontes:")
        for fonte in resultado.sources:
            print(f"  - {fonte}")


def main():
    # Modo direto: pergunta veio nos argumentos.
    if len(sys.argv) > 1:
        _responder(" ".join(sys.argv[1:]))
        return

    # Modo interativo.
    print("Pergunte ao seu Second Brain. Digite 'sair' para encerrar.\n")
    while True:
        try:
            pergunta = input("Pergunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            break
        if not pergunta:
            continue
        if pergunta.lower() in ("sair", "exit", "quit"):
            print("Até mais!")
            break
        _responder(pergunta)


if __name__ == "__main__":
    main()
