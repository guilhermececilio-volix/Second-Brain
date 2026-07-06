"""
Interface web do Second Brain (Streamlit) — chat único.

Um só campo de conversa. O app classifica cada mensagem e age na hora:
  - perguntar: responde via RAG, citando as fontes.
  - guardar: estrutura a anotação (título, tags, frontmatter), grava no cofre
    e conecta às notas parecidas. Cada nota guardada traz Editar / Desfazer.

Rode da raiz do projeto (com o venv ativo e o banco no ar):
    streamlit run app.py
"""

import re
from datetime import datetime

import streamlit as st
from google.genai.errors import ClientError

from src.ingest import capture, delete_capture, update_capture
from src.query import answer, classify, structure_note
from src.theme import apply_theme


def _friendly_error(err: ClientError) -> str:
    """Transforma um erro da API do Gemini numa mensagem clara para o usuário."""
    msg = str(err)
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        espera = re.search(r"retry in ([\d.]+)s", msg, re.IGNORECASE)
        quando = f" Tente de novo em ~{round(float(espera.group(1)))}s." if espera else ""
        return f"⏳ Cota do Gemini atingida no momento.{quando}"
    return "⚠️ Tive um problema ao falar com o Gemini. Tente de novo em instantes."

st.set_page_config(page_title="Second Brain · Volix", page_icon="🧠")
apply_theme(st)
st.title("Second Brain")
st.caption("Fale naturalmente: eu descubro se você quer guardar um pensamento ou perguntar sobre suas notas.")

# Histórico: cada item é um dict. Tipos: user | answer | saved.
if "messages" not in st.session_state:
    st.session_state.messages = []
if "editing" not in st.session_state:
    st.session_state.editing = None  # índice da mensagem 'saved' em edição


def _answer_message(texto: str) -> dict:
    """Responde via RAG e monta a mensagem com as fontes."""
    resultado = answer(texto)
    corpo = resultado.text
    if resultado.sources:
        fontes = "\n".join(f"- {f}" for f in resultado.sources)
        corpo += f"\n\n**Fontes:**\n{fontes}"
    return {"role": "assistant", "type": "answer", "content": corpo}


def _save(texto: str) -> dict:
    """Estrutura e grava a anotação na hora. Guarda o path para Editar/Desfazer."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    nota = structure_note(texto, hoje)
    note_path = capture(nota)
    return {"role": "assistant", "type": "saved", "note_path": note_path, "content": nota}


def _handle(texto: str, forced: str | None = None) -> None:
    """Classifica e age: responde ou guarda direto."""
    kind = forced or classify(texto)
    if kind == "perguntar":
        st.session_state.messages.append(_answer_message(texto))
    else:
        st.session_state.messages.append(_save(texto))


# --- Histórico -------------------------------------------------------------
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg.get("type") == "saved":
            st.markdown(f"📥 **Guardei** em `{msg['note_path']}` e conectei às notas parecidas.")

            if st.session_state.editing == i:
                # Modo edição: reabre a nota para ajuste.
                editado = st.text_area("Editar nota", value=msg["content"], height=240, key=f"edit-{i}")
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("💾 Salvar edição", key=f"save-edit-{i}"):
                        update_capture(msg["note_path"], editado)
                        st.session_state.messages[i]["content"] = editado
                        st.session_state.editing = None
                        st.rerun()
                with c2:
                    if st.button("✕ Cancelar", key=f"cancel-edit-{i}"):
                        st.session_state.editing = None
                        st.rerun()
            else:
                with st.expander("Ver nota"):
                    st.code(msg["content"], language="markdown")
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button("✏️ Editar", key=f"edit-btn-{i}"):
                        st.session_state.editing = i
                        st.rerun()
                with c2:
                    if st.button("🗑 Desfazer", key=f"undo-{i}"):
                        delete_capture(msg["note_path"])
                        st.session_state.messages.pop(i)
                        st.rerun()
        else:
            st.markdown(msg["content"])

# --- Entrada nova ----------------------------------------------------------
if texto := st.chat_input("Escreva um pensamento ou uma pergunta..."):
    st.session_state.messages.append({"role": "user", "type": "user", "content": texto})
    try:
        with st.spinner("Pensando..."):
            _handle(texto)
    except ClientError as err:
        st.session_state.messages.append({"role": "assistant", "type": "answer", "content": _friendly_error(err)})
    st.rerun()
