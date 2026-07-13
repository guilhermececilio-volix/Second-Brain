"""
Configuração central do projeto.

Carrega as variáveis do arquivo .env uma única vez e expõe valores
validados para o resto do código. Nenhum outro módulo deve ler
os.environ diretamente — sempre importe daqui.

Uso:
    from src.config import settings
    print(settings.chat_model)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Raiz do projeto (pasta que contém src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Carrega o .env da raiz do projeto, independente de onde o script foi chamado
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Valores de configuração imutáveis, lidos do ambiente."""

    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    chat_model: str = field(default_factory=lambda: os.environ.get("GEMINI_CHAT_MODEL", "gemini-3.1-flash-lite"))
    embedding_model: str = field(default_factory=lambda: os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"))

    # Sprint 2
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    obsidian_vault_path: str = field(default_factory=lambda: os.environ.get("OBSIDIAN_VAULT_PATH", ""))

    # Integração Google Calendar (OAuth 2.0)
    google_client_id: str = field(default_factory=lambda: os.environ.get("GOOGLE_CLIENT_ID", ""))
    google_client_secret: str = field(default_factory=lambda: os.environ.get("GOOGLE_CLIENT_SECRET", ""))
    google_token_path: str = field(default_factory=lambda: os.environ.get("GOOGLE_TOKEN_PATH", ".google_token.json"))

    def google_oauth_ready(self) -> bool:
        """True se as credenciais OAuth do Google estão configuradas no .env."""
        return bool(self.google_client_id and self.google_client_secret)

    def require_api_key(self) -> str:
        """Retorna a chave da API ou encerra com mensagem clara se faltar."""
        if not self.gemini_api_key or self.gemini_api_key == "coloque-sua-chave-aqui":
            raise SystemExit(
                "GEMINI_API_KEY não configurada.\n"
                "Copie .env.example para .env e cole sua chave do Google AI Studio."
            )
        return self.gemini_api_key


settings = Settings()
