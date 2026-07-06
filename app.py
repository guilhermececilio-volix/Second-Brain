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

from src.ingest import (
    capture,
    delete_capture,
    find_candidates,
    read_note,
    update_capture,
)
from src.query import (
    answer,
    classify,
    decide_save_action,
    merge_note,
    structure_note,
)
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


def _create(texto: str) -> dict:
    """Estrutura e cria uma nota nova. Guarda o path para Editar/Desfazer."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    nota = structure_note(texto, hoje)
    note_path = capture(nota)
    return {"role": "assistant", "type": "saved", "note_path": note_path, "content": nota,
            "acao": "criada"}


def _update(note_path: str, texto: str) -> dict:
    """Mescla a informação nova na nota existente, preservando o resto."""
    atual = read_note(note_path)
    nova = merge_note(atual, texto)
    update_capture(note_path, nova)
    return {"role": "assistant", "type": "saved", "note_path": note_path, "content": nova,
            "acao": "atualizada"}


def _save(texto: str) -> None:
    """Decide entre criar nota nova, atualizar existente, ou perguntar (dúvida)."""
    candidatos = find_candidates(texto)
    decisao = decide_save_action(texto, candidatos)

    if decisao.action == "atualizar" and decisao.note_path:
        st.session_state.messages.append(_update(decisao.note_path, texto))
    elif decisao.action == "duvida" and decisao.note_path:
        # Não age sozinho: pergunta se atualiza aquela nota ou cria nova.
        st.session_state.messages.append(
            {"role": "assistant", "type": "duvida", "note_path": decisao.note_path, "origin": texto}
        )
    else:
        st.session_state.messages.append(_create(texto))


def _handle(texto: str, forced: str | None = None) -> None:
    """Classifica e age: responde ou guarda (criar/atualizar/dúvida)."""
    kind = forced or classify(texto)
    if kind == "perguntar":
        st.session_state.messages.append(_answer_message(texto))
    else:
        _save(texto)


# --- Histórico -------------------------------------------------------------
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg.get("type") == "duvida":
            nome = msg["note_path"]
            st.markdown(f"🤔 Isso parece ter a ver com a nota `{nome}`. Quer **atualizar** ela ou **criar uma nova**?")
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("✏️ Atualizar essa", key=f"dv-upd-{i}"):
                    origin, note_path = msg["origin"], msg["note_path"]
                    st.session_state.messages.pop(i)
                    with st.spinner("Atualizando..."):
                        st.session_state.messages.append(_update(note_path, origin))
                    st.rerun()
            with c2:
                if st.button("🆕 Criar nova", key=f"dv-new-{i}"):
                    origin = msg["origin"]
                    st.session_state.messages.pop(i)
                    with st.spinner("Criando..."):
                        st.session_state.messages.append(_create(origin))
                    st.rerun()
        elif msg.get("type") == "saved":
            acao = msg.get("acao", "criada")
            verbo = "Atualizei" if acao == "atualizada" else "Guardei"
            st.markdown(f"📥 **{verbo}** a nota `{msg['note_path']}`.")

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
