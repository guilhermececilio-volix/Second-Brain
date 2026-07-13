"""
Autoriza o Second Brain a acessar seu Google Calendar (roda UMA vez).

Abre o navegador para você fazer login e autorizar. O token é salvo em
GOOGLE_TOKEN_PATH (padrão: .google_token.json, fora do Git) e reutilizado
depois — os próximos usos renovam sozinhos, sem novo login.

Pré-requisitos:
  - GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET preenchidos no .env
    (gere em https://console.cloud.google.com/ → Credenciais → App para computador)

Rode da raiz do projeto:
    python scripts/google_auth.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calendar_sync import ensure_authorized, is_authorized
from src.config import settings


def main():
    if not settings.google_oauth_ready():
        raise SystemExit(
            "Faltam credenciais. Preencha GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET "
            "no .env (veja .env.example) e rode de novo."
        )

    if is_authorized():
        print("Já autorizado — o token existente é válido. Nada a fazer.")
        return

    print("Abrindo o navegador para você autorizar o acesso ao Google Calendar...")
    ensure_authorized()
    print("Pronto! Token salvo. O app já pode criar eventos na sua agenda.")


if __name__ == "__main__":
    main()
