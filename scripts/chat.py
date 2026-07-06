"""
Chat interativo com o Gemini (usando o wrapper do projeto).

Rode da raiz do projeto:
    python scripts/chat.py

Digite suas mensagens. Para sair: 'sair', 'exit' ou Ctrl+C.
O histórico é mantido, então o modelo lembra do que você falou antes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import GeminiLLM


def main():
    llm = GeminiLLM()
    chat = llm.start_chat()
    print(f"Chat com Gemini ({llm.model}). Digite 'sair' para encerrar.\n")

    while True:
        try:
            msg = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            break

        if not msg:
            continue
        if msg.lower() in ("sair", "exit", "quit"):
            print("Até mais!")
            break

        print(f"\nGemini: {chat.send(msg)}\n")


if __name__ == "__main__":
    main()
