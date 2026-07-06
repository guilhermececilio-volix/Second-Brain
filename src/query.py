"""
Pipeline de consulta (RAG): pergunta → retrieval → resposta com fontes.

Junta as peças já existentes — embeddings (src/embeddings.py), busca por
similaridade (src/db.py) e chat (src/llm.py) — sem conhecer nenhum SDK nem
SQL diretamente. É o coração da FASE 2 descrita no ARCHITECTURE.md.

Uso (via código):
    from src.query import answer
    resultado = answer("O que anotei sobre produtividade?")
    print(resultado.text)
    for fonte in resultado.sources:
        print(fonte)

Normalmente chamado pelo comando de linha: python scripts/ask.py "sua pergunta"
"""

from dataclasses import dataclass

from src.db import Database, SearchHit
from src.embeddings import GeminiEmbeddings
from src.llm import GeminiLLM

# Quantos chunks recuperar para montar o contexto.
DEFAULT_TOP_K = 5

# Instrução de sistema: o modelo responde SÓ com base no contexto recuperado
# e cita as notas de origem. Evita "alucinar" conhecimento que não está nas notas.
SYSTEM_PROMPT = (
    "Você é o assistente de um 'second brain' pessoal. Responda à pergunta usando "
    "APENAS os trechos de notas fornecidos no contexto. Se a resposta não estiver "
    "no contexto, diga com honestidade que as notas não cobrem isso — não invente. "
    "Responda em português, de forma direta, e cite as notas de origem pelo caminho."
)


@dataclass
class Answer:
    """Resposta do RAG com as fontes que a embasaram."""

    text: str
    sources: list[str]  # caminhos das notas usadas, sem repetição
    hits: list[SearchHit]  # chunks recuperados (para depuração/UI)


def _build_prompt(question: str, hits: list[SearchHit]) -> str:
    """Monta o prompt final: trechos de contexto rotulados + a pergunta."""
    blocos = []
    for hit in hits:
        blocos.append(f"[Nota: {hit.note_path}]\n{hit.chunk_text}")
    contexto = "\n\n---\n\n".join(blocos)
    return f"Contexto (trechos das suas notas):\n\n{contexto}\n\nPergunta: {question}"


def answer(question: str, top_k: int = DEFAULT_TOP_K) -> Answer:
    """Responde a uma pergunta sobre as notas via RAG."""
    question = question.strip()
    if not question:
        raise ValueError("A pergunta está vazia.")

    embedder = GeminiEmbeddings()
    db = Database()
    llm = GeminiLLM()

    query_vector = embedder.embed(question)
    hits = db.search(query_vector, top_k=top_k)

    if not hits:
        return Answer(
            text="Não há nada ingerido no banco ainda. "
            "Rode 'python scripts/ingest.py' para indexar o seu vault.",
            sources=[],
            hits=[],
        )

    prompt = _build_prompt(question, hits)
    text = llm.ask(prompt, system=SYSTEM_PROMPT)

    # Fontes únicas, preservando a ordem de relevância.
    sources: list[str] = []
    for hit in hits:
        if hit.note_path not in sources:
            sources.append(hit.note_path)

    return Answer(text=text, sources=sources, hits=hits)
