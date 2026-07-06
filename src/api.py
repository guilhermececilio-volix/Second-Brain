"""
API HTTP do Second Brain (FastAPI).

Expõe a mesma lógica usada pelo app Streamlit como endpoints, para o frontend
Next.js consumir. Não contém regra de negócio própria: só orquestra as funções
de src/query.py e src/ingest.py e devolve JSON.

Rodar da raiz do projeto (com o venv ativo e o banco no ar):
    uvicorn src.api:app --reload --port 8000
"""

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

app = FastAPI(title="Second Brain API")

# O front Next roda em outra porta (3000); libera o acesso em desenvolvimento.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modelos de entrada/saída ---------------------------------------------

class ChatIn(BaseModel):
    text: str


class UpdateIn(BaseModel):
    note_path: str
    text: str  # a informação nova a incorporar


class NotePathIn(BaseModel):
    note_path: str


class EditIn(BaseModel):
    note_path: str
    content: str  # markdown completo já editado


# --- Helpers de resposta ---------------------------------------------------

def _saved(note_path: str, content: str, acao: str) -> dict:
    return {"kind": "saved", "note_path": note_path, "content": content, "acao": acao}


def _do_create(text: str) -> dict:
    hoje = datetime.now().strftime("%Y-%m-%d")
    nota = structure_note(text, hoje)
    note_path = capture(nota)
    return _saved(note_path, nota, "criada")


def _do_update(note_path: str, text: str) -> dict:
    nova = merge_note(read_note(note_path), text)
    update_capture(note_path, nova)
    return _saved(note_path, nova, "atualizada")


# --- Endpoints -------------------------------------------------------------

@app.post("/chat")
def chat(body: ChatIn) -> dict:
    """Recebe uma mensagem, classifica e age (responder / criar / atualizar / dúvida)."""
    text = body.text.strip()
    if not text:
        return {"kind": "error", "message": "Mensagem vazia."}

    if classify(text) == "perguntar":
        resultado = answer(text)
        return {"kind": "answer", "text": resultado.text, "sources": resultado.sources}

    # Guardar: decide entre criar, atualizar ou perguntar (dúvida).
    candidatos = find_candidates(text)
    decisao = decide_save_action(text, candidatos)
    if decisao.action == "atualizar" and decisao.note_path:
        return _do_update(decisao.note_path, text)
    if decisao.action == "duvida" and decisao.note_path:
        return {"kind": "duvida", "note_path": decisao.note_path, "origin": text}
    return _do_create(text)


@app.post("/update")
def update(body: UpdateIn) -> dict:
    """Atualiza (merge) uma nota existente — usado pelo botão de dúvida/confirmação."""
    return _do_update(body.note_path, body.text)


@app.post("/create")
def create(body: ChatIn) -> dict:
    """Força a criação de uma nota nova a partir do texto — botão 'criar nova'."""
    return _do_create(body.text)


@app.post("/edit")
def edit(body: EditIn) -> dict:
    """Salva o markdown editado à mão de uma nota."""
    update_capture(body.note_path, body.content)
    return _saved(body.note_path, body.content, "editada")


@app.post("/delete")
def delete(body: NotePathIn) -> dict:
    """Apaga uma nota (botão desfazer)."""
    delete_capture(body.note_path)
    return {"kind": "deleted", "note_path": body.note_path}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
