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

import re
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


# Instrução para o classificador: decidir entre guardar um pensamento novo ou
# perguntar sobre as notas. Responde uma única palavra.
CLASSIFY_PROMPT = (
    "Você classifica a intenção de uma mensagem num app de notas pessoais. "
    "Se a pessoa quer PERGUNTAR/consultar algo que já anotou, responda: perguntar. "
    "Se ela está registrando um pensamento, fato ou ideia para GUARDAR, responda: guardar. "
    "Responda com uma única palavra: 'guardar' ou 'perguntar'. Nada além disso."
)


def classify(message: str) -> str:
    """Decide se a mensagem é 'guardar' ou 'perguntar'.

    Em caso de dúvida, cai em 'perguntar' — responder é inofensivo, enquanto
    guardar por engano criaria uma nota indesejada no cofre.
    """
    message = message.strip()
    if not message:
        raise ValueError("Mensagem vazia.")

    resposta = GeminiLLM().ask(message, system=CLASSIFY_PROMPT).lower()
    return "guardar" if "guardar" in resposta else "perguntar"


# Instrução para o juiz de relação entre duas notas. Responde uma palavra.
RELATES_PROMPT = (
    "Você decide se duas notas merecem ser ligadas por um link, como no grafo do "
    "Obsidian. Todas as notas são de uma mesma pessoa (o dono do caderno); "
    "'eu/meu/minha' se referem sempre a ela. Ligue quando as duas notas são sobre o "
    "MESMO SUJEITO CONCRETO:\n"
    "- ambas descrevem a PRÓPRIA pessoa (quem ela é): perfil, biografia, gostos, "
    "preferências, características pessoais → LIGAR entre si.\n"
    "- ambas sobre o mesmo projeto, trabalho, lugar ou evento específico → LIGAR.\n"
    "NÃO ligue quando uma é sobre a pessoa (perfil/gostos) e a outra sobre uma "
    "atividade/projeto que ela faz — são sujeitos diferentes. NÃO ligue projetos "
    "diferentes entre si, nem notas só por serem da mesma categoria."
)

# Limita o texto de cada nota enviado ao juiz (evita prompt gigante).
_RELATES_MAX_CHARS = 800


def filter_related(source_text: str, candidates: list[tuple[str, str]]) -> list[str]:
    """Dentre os candidatos, retorna os que se relacionam com a nota-fonte.

    Faz UMA única chamada ao Gemini (não uma por candidato) — essencial para não
    estourar o limite de requisições por minuto. `candidates` é uma lista de
    (identificador, texto); o retorno é a sublista de identificadores ligados.
    """
    if not candidates:
        return []

    blocos = []
    for i, (_id, texto) in enumerate(candidates):
        blocos.append(f"[{i}]\n{texto[:_RELATES_MAX_CHARS]}")
    lista = "\n\n".join(blocos)
    prompt = (
        f"NOTA PRINCIPAL:\n{source_text[:_RELATES_MAX_CHARS]}\n\n"
        f"NOTAS CANDIDATAS (cada uma com um número entre colchetes):\n{lista}\n\n"
        "Liste os números das candidatas que devem ser ligadas à nota principal, "
        "separados por vírgula (ex.: 0, 2). Se nenhuma, responda 'nenhuma'."
    )
    resposta = GeminiLLM().ask(prompt, system=RELATES_PROMPT).lower()

    escolhidos = {int(n) for n in re.findall(r"\d+", resposta)}
    return [candidates[i][0] for i in escolhidos if 0 <= i < len(candidates)]


# Instrução para estruturar uma captura crua numa nota organizada.
# Nível "médio": título, texto limpo, tags e frontmatter — SEM inventar conteúdo.
STRUCTURE_PROMPT = (
    "Você organiza uma anotação pessoal em uma nota Markdown limpa para o Obsidian. "
    "Regras:\n"
    "- Comece com frontmatter YAML entre '---' contendo: 'tipo' (uma palavra: ideia, "
    "tarefa, reuniao, pessoa, referencia, etc.), 'data' (use exatamente a data fornecida) "
    "e 'tags' (lista curta de 1 a 4 palavras-chave em minúsculas, sem '#').\n"
    "- Depois um título de nível 1 (# ) curto e descritivo.\n"
    "- Depois o corpo: o texto do usuário limpo (pontuação, maiúsculas, quebras), "
    "organizado em frases ou tópicos se ajudar.\n"
    "IMPORTANTE: NÃO invente fatos nem adicione informação que o usuário não deu. "
    "Mantenha as palavras e o sentido dele. Responda só o Markdown, sem comentários."
)


def structure_note(text: str, date_str: str) -> str:
    """Transforma uma anotação crua numa nota Markdown estruturada.

    date_str é a data de criação (ex.: '2026-07-06'), usada no frontmatter —
    passada de fora para manter este módulo sem lógica de tempo.
    """
    text = text.strip()
    if not text:
        raise ValueError("Não há texto para estruturar.")
    prompt = f"Data de hoje: {date_str}\n\nAnotação do usuário:\n{text}"
    return GeminiLLM().ask(prompt, system=STRUCTURE_PROMPT).strip()
