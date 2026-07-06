"""
Teste rápido da API do Gemini usando os wrappers do projeto.

Valida as duas peças da Sprint 1:
  1) Chat (src/llm.py)         -> a chave funciona e o modelo responde.
  2) Embeddings (src/embeddings.py) -> a peça que vai alimentar o pgvector.

Rode da raiz do projeto:
    python scripts/test_gemini.py
"""

import sys
from pathlib import Path

# Permite rodar o script de qualquer lugar (adiciona a raiz ao path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.embeddings import GeminiEmbeddings
from src.llm import GeminiLLM


def testar_chat():
    print("== Teste de chat ==")
    llm = GeminiLLM()
    resposta = llm.ask("Em uma frase curta, o que é um 'second brain'?")
    print(resposta)


def testar_embeddings():
    print("\n== Teste de embeddings (base do pgvector) ==")
    emb = GeminiEmbeddings()
    vetor = emb.embed("Minha primeira memória no Second Brain.")
    print(f"Dimensões do vetor: {len(vetor)}")
    print(f"Primeiros valores: {vetor[:5]}")


if __name__ == "__main__":
    testar_chat()
    testar_embeddings()
    print("\nOK! A API respondeu. Chave válida e wrappers funcionando.")
