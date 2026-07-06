"""
Tema visual da Volix para o app Streamlit.

Aplica a identidade do sistema de design SDG (apresentações da Volix): paleta
verde-escura, tipografia Mosk e o logo. Isola todo o CSS/asset aqui para manter
o app.py focado na lógica.

Uso:
    from src.theme import apply_theme, logo_path
    apply_theme(st)
"""

import base64
from functools import lru_cache
from pathlib import Path

from src.config import PROJECT_ROOT

ASSETS = PROJECT_ROOT / "assets"

# Paleta oficial (references/design-tokens.md do sistema SDG da Volix).
BG_DEEP = "#0A0F0D"
BG_ELEVATED = "#101814"
BRAND_GREEN = "#43C49E"
BRAND_GREEN_BRIGHT = "#5FE3B8"
BRAND_GREEN_DEEP = "#0F2A22"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#E6EDE9"
TEXT_MUTED = "#8FA098"

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

    /* Tipografia da marca em tudo. */
    html, body, [class*="css"], .stApp, .stMarkdown, input, textarea, button,
    [data-testid="stChatInput"] textarea {{
        font-family: 'Mosk', system-ui, sans-serif;
    }}

    /* Fundo: verde-quase-preto com um brilho verde sutil no topo. */
    .stApp {{
        background:
            radial-gradient(1200px 600px at 50% -10%, rgba(67,196,158,0.10), transparent 60%),
            {BG_DEEP};
        color: {TEXT_SECONDARY};
    }}

    /* Barra superior e menu do Streamlit: transparentes, sem faixa branca. */
    header[data-testid="stHeader"] {{
        background: transparent;
    }}
    [data-testid="stToolbar"] {{ right: 12px; }}
    [data-testid="stToolbar"] * {{ color: {TEXT_MUTED} !important; }}
    #MainMenu, [data-testid="stDecoration"] {{ background: transparent; }}

    /* Coluna central mais estreita e arejada. */
    .block-container {{
        max-width: 820px;
        padding-top: 2.5rem;
        padding-bottom: 7rem;  /* espaço para o input flutuante */
    }}

    /* Títulos: branco puro, peso alto, escala generosa. */
    h1 {{
        color: {TEXT_PRIMARY};
        font-weight: 800;
        letter-spacing: -0.02em;
        font-size: clamp(34px, 4.4vw, 60px);
        margin-bottom: .2rem;
    }}
    h2, h3 {{ color: {TEXT_PRIMARY}; font-weight: 800; letter-spacing: -0.01em; }}

    /* Legenda sob o título. */
    .stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
        color: {TEXT_MUTED} !important;
        font-size: 1.02rem;
    }}

    /* Balões de chat: cartões elevados, cantos suaves, fio verde discreto. */
    [data-testid="stChatMessage"] {{
        background: {BG_ELEVATED};
        border: 1px solid rgba(67,196,158,0.16);
        border-radius: 16px;
        padding: 2px 4px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    }}
    [data-testid="stChatMessage"] p {{ color: {TEXT_SECONDARY}; }}
    /* Avatar do chat no verde da marca. */
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"] {{
        background: {BRAND_GREEN_DEEP};
        color: {BRAND_GREEN_BRIGHT};
    }}

    /* Botões (refazer): pílula verde. */
    .stButton > button {{
        background: transparent;
        color: {BRAND_GREEN};
        border: 1px solid rgba(67,196,158,0.45);
        border-radius: 999px;
        font-weight: 500;
        padding: 4px 14px;
        transition: all .2s cubic-bezier(.2,.7,.2,1);
    }}
    .stButton > button:hover {{
        background: {BRAND_GREEN};
        color: {BG_DEEP};
        border-color: {BRAND_GREEN};
    }}

    /* Barra de input flutuante. Toda a cadeia de containers da base fica escura
       (o fundo branco vinha de um wrapper pai, não do stChatInput em si). */
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {{
        background: transparent !important;
    }}
    /* Fundo escuro em TODO elemento dentro do input (o branco estava num
       wrapper BaseWeb interno; forçamos a cadeia inteira). */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] * {{
        background-color: {BG_ELEVATED} !important;
    }}
    [data-testid="stChatInput"] {{
        max-width: 820px;
        margin: 0 auto;
        border: 1px solid rgba(67,196,158,0.28) !important;
        border-radius: 16px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.45);
        transition: border-color .2s ease;
        overflow: hidden;
    }}
    [data-testid="stChatInput"]:focus-within {{
        border-color: {BRAND_GREEN} !important;
    }}
    [data-testid="stChatInputTextArea"] {{
        background-color: transparent !important;
        color: {TEXT_PRIMARY} !important;
        font-size: 1.05rem;
        -webkit-text-fill-color: {TEXT_PRIMARY};
    }}
    [data-testid="stChatInputTextArea"]::placeholder {{
        color: {TEXT_MUTED} !important;
        -webkit-text-fill-color: {TEXT_MUTED};
    }}
    /* Botão de enviar: verde sólido, não herda o fundo escuro acima. */
    [data-testid="stChatInputSubmitButton"] {{
        background-color: {BRAND_GREEN} !important;
    }}
    [data-testid="stChatInputSubmitButton"]:hover {{
        background-color: {BRAND_GREEN_BRIGHT} !important;
    }}
    /* Botão de enviar do chat: verde. */
    [data-testid="stChatInputSubmitButton"] {{
        background: {BRAND_GREEN};
        color: {BG_DEEP};
        border-radius: 10px;
    }}
    [data-testid="stChatInputSubmitButton"]:hover {{ background: {BRAND_GREEN_BRIGHT}; }}
    [data-testid="stChatInputSubmitButton"] svg {{ color: {BG_DEEP}; fill: {BG_DEEP}; }}

    /* Spinner e links no verde da marca. */
    .stSpinner > div {{ border-top-color: {BRAND_GREEN} !important; }}
    a, a:visited {{ color: {BRAND_GREEN}; text-decoration: none; }}
    a:hover {{ color: {BRAND_GREEN_BRIGHT}; text-decoration: underline; }}

    /* Cabeçalho: logo + faixa verde que esmaece. */
    .volix-header {{
        display: flex;
        align-items: center;
        gap: 18px;
        margin: 0 0 1.6rem;
    }}
    .volix-header img {{ height: 30px; opacity: .96; }}
    .volix-header .rule {{
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, {BRAND_GREEN}, rgba(67,196,158,0) 90%);
    }}
    </style>
    """


def apply_theme(st) -> None:
    """Injeta o CSS do tema e o cabeçalho com o logo da Volix."""
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="volix-header">
            <img src="{_logo_data_uri()}" alt="Volix"/>
            <div class="rule"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
