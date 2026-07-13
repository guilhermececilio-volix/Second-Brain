"""
Integração com o Google Calendar — único módulo que fala com a API do Google.

Cuida do OAuth (login na 1ª vez, refresh automático depois) e da criação de
eventos. Nenhum outro módulo importa as libs do Google: a API expõe estas
funções e o resto do projeto só as chama.

Segurança: o app NUNCA cria evento sozinho a partir da extração — quem chama
(a API) só cria após a confirmação explícita do usuário. Este módulo apenas
executa a criação quando mandado.

Fluxo de autenticação (uma vez):
    from src.calendar_sync import ensure_authorized
    ensure_authorized()   # abre o navegador para login; salva o token

Depois:
    from src.calendar_sync import create_event
    link = create_event("Reunião de review", "2026-07-13T09:00:00", 60)
"""

from datetime import datetime, timedelta
from pathlib import Path

from src.config import settings

# Escopo mínimo: criar/editar eventos (não lê e-mail, não apaga calendário).
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Fuso do usuário (o projeto é single-user, São Paulo). Poderia vir do .env
# no futuro; por ora fixo e explícito.
TIMEZONE = "America/Sao_Paulo"


def _require_oauth() -> None:
    """Encerra com mensagem clara se as credenciais OAuth não estão no .env."""
    if not settings.google_oauth_ready():
        raise RuntimeError(
            "Google Calendar não configurado. Preencha GOOGLE_CLIENT_ID e "
            "GOOGLE_CLIENT_SECRET no .env (veja .env.example)."
        )


def _client_config() -> dict:
    """Monta o dict de config do cliente OAuth a partir do .env.

    Evita ter um arquivo credentials.json solto no disco — as credenciais vêm
    do .env, como todo o resto dos segredos do projeto.
    """
    return {
        "installed": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _load_credentials():
    """Carrega o token salvo e renova se expirado. None se ainda não há token."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_path = Path(settings.google_token_path)
    if not token_path.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def is_authorized() -> bool:
    """True se já existe um token válido (ou renovável) salvo."""
    if not settings.google_oauth_ready():
        return False
    try:
        creds = _load_credentials()
        return bool(creds and creds.valid)
    except Exception:
        return False


def ensure_authorized() -> None:
    """Garante um token válido; se não houver, abre o navegador para login.

    Roda o fluxo de app instalado (abre o navegador, você faz login e autoriza).
    O token resultante é salvo em GOOGLE_TOKEN_PATH para os próximos usos.
    Chamar de um script local (scripts/google_auth.py), não no meio de um request.
    """
    _require_oauth()
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = _load_credentials()
    if creds and creds.valid:
        return  # já autorizado

    flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
    creds = flow.run_local_server(port=0)  # abre o navegador
    Path(settings.google_token_path).write_text(creds.to_json(), encoding="utf-8")


def _service():
    """Cria o cliente da Calendar API com o token salvo."""
    from googleapiclient.discovery import build

    creds = _load_credentials()
    if not creds or not creds.valid:
        raise RuntimeError(
            "Sem autorização do Google. Rode 'python scripts/google_auth.py' uma vez."
        )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(
    summary: str,
    start_iso: str,
    duration_min: int = 60,
    description: str = "",
) -> dict:
    """Cria um evento no calendário principal. Retorna {id, link, summary, start}.

    start_iso: início em ISO 8601 (ex.: '2026-07-13T09:00:00'). duration_min: minutos.
    Só é chamado após confirmação do usuário — este módulo não decide criar nada.
    """
    if not summary.strip():
        raise ValueError("Evento sem título.")

    inicio = datetime.fromisoformat(start_iso)
    fim = inicio + timedelta(minutes=duration_min)

    corpo = {
        "summary": summary.strip(),
        "description": description.strip(),
        "start": {"dateTime": inicio.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": fim.isoformat(), "timeZone": TIMEZONE},
    }
    evento = _service().events().insert(calendarId="primary", body=corpo).execute()
    return {
        "id": evento.get("id"),
        "link": evento.get("htmlLink"),
        "summary": summary.strip(),
        "start": inicio.isoformat(),
    }
