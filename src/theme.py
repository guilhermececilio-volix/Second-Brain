"""
Tema visual do app Streamlit — estética shadcn (neutro + toque de verde Volix).

Base em cinzas neutros (zinc), muito respiro e detalhes sutis, com o verde da
Volix reservado a acentos pontuais (botão de enviar, links, foco). A fonte Mosk
e o logo da marca são mantidos. Todo o CSS/asset fica isolado aqui.

Uso:
    from src.theme import apply_theme
    apply_theme(st)
"""

import base64
from functools import lru_cache

from src.config import PROJECT_ROOT

ASSETS = PROJECT_ROOT / "assets"

# --- Paleta neutra estilo shadcn (dark) + acento verde Volix ---
BG = "#0A0A0B"           # fundo (zinc quase preto, neutro)
SURFACE = "#141416"      # cartões / mensagens
SURFACE_2 = "#1B1B1E"    # inputs / hover
BORDER = "#27272A"       # bordas sutis (zinc-800)
BORDER_SOFT = "#1F1F22"
TEXT_PRIMARY = "#FAFAFA"  # títulos (zinc-50)
TEXT = "#D4D4D8"          # corpo (zinc-300)
TEXT_MUTED = "#8B8B90"    # legendas (zinc-500)
TEXT_FAINT = "#5A5A60"
ACCENT = "#43C49E"        # verde Volix — só acento
ACCENT_BRIGHT = "#5FE3B8"

# Fontes Mosk: nome do arquivo -> peso CSS.
_FONTS = {
    "Mosk Normal 400.ttf": 400,
    "Mosk Medium 500.ttf": 500,
    "Mosk Extra-Bold 800.ttf": 800,
}


@lru_cache(maxsize=None)
def _font_face(filename: str, weight: int) -> str:
    """Gera uma regra @font-face com a fonte embutida em base64."""
    data = (ASSETS / "fonts" / filename).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return (
        "@font-face{"
        "font-family:'Mosk';"
        f"font-weight:{weight};"
        "font-display:block;"
        f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
        "}"
    )


@lru_cache(maxsize=None)
def _logo_data_uri() -> str:
    """Logo da Volix (versão negativa, para fundo escuro) como data URI."""
    data = (ASSETS / "identity" / "volix_logo.png").read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _css() -> str:
    faces = "".join(_font_face(f, w) for f, w in _FONTS.items())
    return f"""
    <style>
    {faces}

    html, body, [class*="css"], .stApp, .stMarkdown, input, textarea, button,
    [data-testid="stChatInputTextArea"] {{
        font-family: 'Mosk', system-ui, -apple-system, sans-serif;
    }}

    /* Fundo neutro chapado — minimalismo shadcn, sem gradiente chamativo. */
    .stApp {{ background: {BG}; color: {TEXT}; }}

    header[data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stToolbar"] {{ right: 12px; }}
    [data-testid="stToolbar"] * {{ color: {TEXT_FAINT} !important; }}

    /* Coluna central estreita e com muito respiro. */
    .block-container {{
        max-width: 720px;
        padding-top: 2rem;
        padding-bottom: 7rem;
    }}

    /* Tipografia: título contido, não gigante (registro shadcn). */
    h1 {{
        color: {TEXT_PRIMARY};
        font-weight: 800;
        letter-spacing: -0.025em;
        font-size: 1.7rem;
        margin: 0 0 .15rem;
    }}
    h2, h3 {{ color: {TEXT_PRIMARY}; font-weight: 700; letter-spacing: -0.01em; }}
    .stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
        color: {TEXT_MUTED} !important;
        font-size: .92rem;
    }}

    /* Mensagens de chat: cartão limpo, borda sutil, bastante padding. */
    [data-testid="stChatMessage"] {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: .5rem .9rem;
        box-shadow: none;
        margin-bottom: .3rem;
    }}
    [data-testid="stChatMessage"] p {{ color: {TEXT}; line-height: 1.6; }}
    /* Mensagem do usuário: um pouco mais escura, sem borda — hierarquia sutil. */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
        background: {SURFACE_2};
        border-color: {BORDER_SOFT};
    }}
    /* Avatares discretos, monocromáticos. */
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"] {{
        background: {SURFACE_2};
        color: {TEXT_MUTED};
        border: 1px solid {BORDER};
    }}

    /* Blocos de código (nota estruturada): fundo neutro, mono. */
    [data-testid="stChatMessage"] pre, [data-testid="stChatMessage"] code {{
        background: {BG} !important;
        border: 1px solid {BORDER_SOFT};
        border-radius: 8px;
        color: {TEXT} !important;
    }}

    /* Expander "Ver nota": discreto. */
    [data-testid="stExpander"] {{
        border: 1px solid {BORDER};
        border-radius: 10px;
        background: {SURFACE};
    }}
    [data-testid="stExpander"] summary {{ color: {TEXT_MUTED}; }}
    [data-testid="stExpander"] summary:hover {{ color: {TEXT}; }}

    /* Botões: estilo shadcn "outline" — fundo neutro, borda, hover suave. */
    .stButton > button {{
        background: {SURFACE_2};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 9px;
        font-weight: 500;
        font-size: .88rem;
        padding: .35rem .85rem;
        transition: all .15s ease;
    }}
    .stButton > button:hover {{
        background: {BORDER};
        border-color: #3A3A3F;
        color: {TEXT_PRIMARY};
    }}
    .stButton > button:active {{ transform: translateY(1px); }}

    /* Área de texto (edição de nota): fundo input neutro. */
    .stTextArea textarea {{
        background: {SURFACE_2} !important;
        color: {TEXT} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 10px;
    }}
    .stTextArea textarea:focus {{ border-color: {ACCENT} !important; }}

    /* Campo de chat na base: cartão neutro, foco verde discreto. */
    [data-testid="stBottom"], [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {{ background: transparent !important; }}
    [data-testid="stChatInput"], [data-testid="stChatInput"] * {{
        background-color: {SURFACE} !important;
    }}
    [data-testid="stChatInput"] {{
        max-width: 720px;
        margin: 0 auto;
        border: 1px solid {BORDER} !important;
        border-radius: 14px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
        transition: border-color .15s ease;
        overflow: hidden;
    }}
    [data-testid="stChatInput"]:focus-within {{ border-color: {ACCENT} !important; }}
    [data-testid="stChatInputTextArea"] {{
        background-color: transparent !important;
        color: {TEXT_PRIMARY} !important;
        font-size: 1rem;
        -webkit-text-fill-color: {TEXT_PRIMARY};
    }}
    [data-testid="stChatInputTextArea"]::placeholder {{
        color: {TEXT_FAINT} !important;
        -webkit-text-fill-color: {TEXT_FAINT};
    }}
    /* Botão de enviar: o único verde forte — o "acento" da tela. */
    [data-testid="stChatInputSubmitButton"] {{
        background-color: {ACCENT} !important;
        border-radius: 8px;
    }}
    [data-testid="stChatInputSubmitButton"]:hover {{ background-color: {ACCENT_BRIGHT} !important; }}
    [data-testid="stChatInputSubmitButton"] svg {{ color: {BG}; fill: {BG}; }}

    .stSpinner > div {{ border-top-color: {ACCENT} !important; }}
    a, a:visited {{ color: {ACCENT}; text-decoration: none; }}
    a:hover {{ color: {ACCENT_BRIGHT}; text-decoration: underline; }}

    /* Cabeçalho: logo pequeno + rótulo discreto, alinhado à esquerda. */
    .app-header {{ margin: 0 0 1.8rem; }}
    .app-header img {{ height: 22px; opacity: .9; display: block; }}
    </style>
    """


def apply_theme(st) -> None:
    """Injeta o CSS do tema e o cabeçalho com o logo da Volix."""
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown(
        f'<div class="app-header"><img src="{_logo_data_uri()}" alt="Volix"/></div>',
        unsafe_allow_html=True,
    )
