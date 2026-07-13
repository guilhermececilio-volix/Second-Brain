"""
Avalia a qualidade do RAG contra o conjunto de casos (eval/cases.json).

Mede o retrieval (a nota certa entra no top-K?) e, com --grounding, também a
resposta do LLM (keyword presente? recusa quando não há evidência?).

Pré-requisitos:
  - banco no ar e vault já ingerido (python scripts/ingest.py)
  - .env com GEMINI_API_KEY e DATABASE_URL
  - casos preenchidos em eval/cases.json refletindo o seu vault

Rode da raiz do projeto:
    python scripts/eval.py                  # só retrieval (barato, sem LLM)
    python scripts/eval.py --grounding      # também avalia a resposta (usa LLM)
    python scripts/eval.py --top-k 8        # muda o K do retrieval
"""

import argparse
import sys
from pathlib import Path

# Permite rodar o script de qualquer lugar (adiciona a raiz ao path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.eval import load_cases, run_eval


def main():
    parser = argparse.ArgumentParser(description="Avalia a qualidade do RAG.")
    parser.add_argument(
        "--grounding",
        action="store_true",
        help="também avalia a resposta do LLM (keyword e recusa). Usa a API.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="quantos chunks recuperar no retrieval (padrão: 5).",
    )
    args = parser.parse_args()

    casos = load_cases()
    if not casos:
        raise SystemExit(
            "Nenhum caso em eval/cases.json. Adicione perguntas do seu vault real."
        )

    print(f"Rodando eval em {len(casos)} casos (top_k={args.top_k}, "
          f"grounding={'sim' if args.grounding else 'não'})...\n")
    relatorio = run_eval(casos, top_k=args.top_k, grounding=args.grounding)
    print(relatorio)


if __name__ == "__main__":
    main()
