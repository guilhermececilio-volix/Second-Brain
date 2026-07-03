"""
Teste rápido da API do Google AI Studio (Gemini).
Roda dois testes:
  1) Chat  -> valida que a chave funciona.
  2) Embeddings -> valida a peça que vai alimentar o pgvector (o "banco de memórias").

A chave NUNCA fica aqui. Ela é lida do arquivo .env (veja .env.example).
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("Defina GEMINI_API_KEY no arquivo .env antes de rodar.")

client = genai.Client(api_key=api_key)


def testar_chat():
    print("== Teste de chat ==")
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Em uma frase curta, o que e um 'second brain'?",
    )
    print(resp.text.strip())


def testar_embeddings():
    print("\n== Teste de embeddings (base do pgvector) ==")
    resp = client.models.embed_content(
        model="gemini-embedding-001",
        contents="Minha primeira memoria no Second Brain.",
    )
    vetor = resp.embeddings[0].values
    print(f"Dimensoes do vetor: {len(vetor)}")
    print(f"Primeiros valores: {vetor[:5]}")


if __name__ == "__main__":
    testar_chat()
    testar_embeddings()
    print("\nOK! A API respondeu. Chave valida.")
