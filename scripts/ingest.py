"""
Ingere o vault do Obsidian no banco (pgvector).

Lê as notas (.md) do OBSIDIAN_VAULT_PATH, divide em chunks, gera embeddings
e grava no PostgreSQL. É incremental: só reprocessa notas que mudaram.

Pré-requisitos:
  - banco no ar:      docker compose up -d
  - .env preenchido:  DATABASE_URL e OBSIDIAN_VAULT_PATH

Rode da raiz do projeto:
    python scripts/ingest.py
"""

import sys
from pathlib import Path

# Permite rodar o script de qualquer lugar (adiciona a raiz ao path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest import ingest_vault


def main():
    print("Ingerindo o vault do Obsidian...\n")
    resumo = ingest_vault()
    print(f"\nPronto. {resumo}")


if __name__ == "__main__":
    main()
