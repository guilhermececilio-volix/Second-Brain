"""
API HTTP do Second Brain (FastAPI).

Expõe a mesma lógica usada pelo app Streamlit como endpoints, para o frontend
Next.js consumir. Não contém regra de negócio própria: só orquestra as funções
de src/query.py e src/ingest.py e devolve JSON.

Rodar da raiz do projeto (com o venv ativo e o banco no ar):
    uvicorn src.api:app --reload --port 8000
"""

from datetime import datetime

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.ingest import (
    capture,
    delete_capture,
    find_candidates,
    read_note,
    save_meeting,
    update_capture,
)
from src.meeting import MeetingExtraction, extract_points, transcript_from_docx
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
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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
        hoje = datetime.now().strftime("%d/%m/%Y")
        resultado = answer(text, today=hoje)
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


class TranscriptIn(BaseModel):
    transcript: str


class MeetingSaveIn(BaseModel):
    # A extração (possivelmente editada no preview) volta como JSON.
    titulo: str
    resumo: str = ""
    participantes: list[str] = []
    pontos: list[dict] = []


@app.post("/meeting/extract")
def meeting_extract(body: TranscriptIn) -> dict:
    """Extrai os pontos importantes de uma transcrição — para o preview, NÃO grava."""
    texto = body.transcript.strip()
    if not texto:
        return {"kind": "error", "message": "Transcrição vazia."}
    hoje = datetime.now().strftime("%d/%m/%Y")
    extraction = extract_points(texto, today=hoje)
    return {"kind": "extraction", **extraction.to_dict()}


@app.post("/meeting/extract-docx")
async def meeting_extract_docx(file: UploadFile = File(...)) -> dict:
    """Recebe um .docx (transcrição do Teams/Word), extrai o texto e os pontos."""
    if not (file.filename or "").lower().endswith(".docx"):
        return {"kind": "error", "message": "Envie um arquivo .docx."}
    try:
        texto = transcript_from_docx(await file.read())
    except Exception:
        return {"kind": "error", "message": "Não consegui ler o .docx. O arquivo pode estar corrompido."}
    hoje = datetime.now().strftime("%d/%m/%Y")
    extraction = extract_points(texto, today=hoje)
    return {"kind": "extraction", **extraction.to_dict()}


@app.post("/meeting/save")
def meeting_save(body: MeetingSaveIn) -> dict:
    """Grava a reunião: nota-mãe + notas-filhas (a extração pode ter sido editada)."""
    extraction = MeetingExtraction.from_dict(body.model_dump())
    if not extraction.pontos:
        return {"kind": "error", "message": "Nenhum ponto para salvar."}
    resultado = save_meeting(extraction)
    return {"kind": "meeting_saved", **resultado}


class EventIn(BaseModel):
    titulo: str
    data_iso: str
    duracao_min: int = 60
    descricao: str = ""


@app.get("/calendar/status")
def calendar_status() -> dict:
    """Diz se o Google Calendar está configurado e autorizado (para a UI decidir)."""
    from src.calendar_sync import is_authorized
    from src.config import settings
    return {"configured": settings.google_oauth_ready(), "authorized": is_authorized()}


@app.post("/calendar/event")
def calendar_event(body: EventIn) -> dict:
    """Cria UM evento na agenda — só é chamado após o usuário confirmar no preview."""
    from src.calendar_sync import create_event
    titulo = body.titulo.strip()
    if not titulo:
        return {"kind": "error", "message": "Evento sem título."}
    try:
        ev = create_event(titulo, body.data_iso, body.duracao_min, body.descricao)
        return {"kind": "event_created", **ev}
    except Exception as e:
        return {"kind": "error", "message": f"Não consegui criar o evento: {e}"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
