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

# Teto de distância de cosseno para um chunk ser considerado relevante o bastante
# para virar contexto/fonte. Acima disso, o chunk é descartado — evita que notas
# fracas (ex.: 'Teste', 'Olá') poluam as fontes só para completar a cota de top_k.
# Calibrado com o eval: as notas boas ficam ~0.35 e as triviais ~0.39+.
MAX_HIT_DISTANCE = 0.38

# Instrução de sistema: o modelo responde SÓ com base no contexto recuperado
# e cita as notas de origem. Evita "alucinar" conhecimento que não está nas notas.
# A data de hoje é injetada no prompt (ver _build_prompt) porque o modelo não tem
# noção de tempo: sem isso, ele lê 'data: 2026-07-06' numa nota e chama de "hoje".
SYSTEM_PROMPT = (
    "Você é o assistente de um 'second brain' pessoal. Responda à pergunta usando "
    "APENAS os trechos de notas fornecidos no contexto. Se a resposta não estiver "
    "no contexto, diga com honestidade que as notas não cobrem isso — não invente. "
    "Cada nota tem uma 'data' no frontmatter: use a DATA DE HOJE informada para "
    "situar no tempo (o que já passou, o que é hoje, o que é futuro). NÃO trate a "
    "data de uma nota como 'hoje' a menos que ela coincida com a data de hoje. "
    "Responda em português, de forma direta e natural. Pode usar Markdown (negrito, "
    "listas) quando ajudar a organizar. NÃO cite o caminho nem o nome do arquivo das "
    "notas no meio da resposta — as fontes são mostradas separadamente pela interface."
)


@dataclass
class Answer:
    """Resposta do RAG com as fontes que a embasaram."""

    text: str
    sources: list[str]  # caminhos das notas usadas, sem repetição
    hits: list[SearchHit]  # chunks recuperados (para depuração/UI)


def _build_prompt(question: str, hits: list[SearchHit], today: str | None) -> str:
    """Monta o prompt final: data de hoje + trechos de contexto + a pergunta."""
    blocos = []
    for hit in hits:
        blocos.append(f"[Nota: {hit.note_path}]\n{hit.chunk_text}")
    contexto = "\n\n---\n\n".join(blocos)
    cabecalho = f"Data de hoje: {today}\n\n" if today else ""
    return (
        f"{cabecalho}Contexto (trechos das suas notas):\n\n{contexto}\n\n"
        f"Pergunta: {question}"
    )


def answer(
    question: str,
    top_k: int = DEFAULT_TOP_K,
    today: str | None = None,
) -> Answer:
    """Responde a uma pergunta sobre as notas via RAG.

    today (ex.: '08/07/2026') é passado de fora para o modelo situar no tempo —
    este módulo não lê o relógio (mesma regra de structure_note). Sem today, o
    modelo perde a noção temporal e pode chamar a data de uma nota antiga de "hoje".
    """
    question = question.strip()
    if not question:
        raise ValueError("A pergunta está vazia.")

    embedder = GeminiEmbeddings()
    db = Database()
    llm = GeminiLLM()

    query_vector = embedder.embed(question)
    hits = db.search(query_vector, top_k=top_k)

    # Descarta chunks fracos: só o que está de fato próximo vira contexto e fonte.
    hits = [h for h in hits if h.distance <= MAX_HIT_DISTANCE]

    if not hits:
        return Answer(
            text="Suas notas não cobrem isso — não encontrei nada relevante.",
            sources=[],
            hits=[],
        )

    prompt = _build_prompt(question, hits, today)
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
# Modelo de "hub": a nota de perfil/biografia é o centro que conecta os gostos e
# admirações da pessoa; gostos DIFERENTES entre si (música x futebol) NÃO se ligam.
RELATES_PROMPT = (
    "Você decide se duas notas merecem ser ligadas por um link, como no grafo do "
    "Obsidian. Todas as notas são de uma mesma pessoa (o dono do caderno); "
    "'eu/meu/minha' se referem sempre a ela. Ligue quando:\n"
    "- uma nota é o PERFIL/BIOGRAFIA da pessoa (quem ela é no geral) e a outra é um "
    "gosto, preferência, ídolo ou admiração dela → LIGAR (o perfil é o centro que "
    "conecta os gostos).\n"
    "- ambas são sobre o MESMO SUJEITO CONCRETO: o mesmo projeto, trabalho, lugar, "
    "evento ou item específico → LIGAR.\n"
    "NÃO ligue dois gostos/admirações DIFERENTES entre si (ex.: música e futebol, "
    "jogo e artista) — eles só se conectam através do perfil, não um ao outro. "
    "NÃO ligue quando uma é sobre a pessoa (perfil/gostos) e a outra sobre uma "
    "atividade/projeto que ela faz. NÃO ligue projetos diferentes entre si, nem "
    "notas só por serem da mesma categoria."
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


# --- Decidir: a anotação nova atualiza uma nota existente, ou é assunto novo? ---

# Resultado da decisão. action é 'criar', 'atualizar' ou 'duvida'.
@dataclass
class SaveAction:
    action: str
    note_path: str | None = None  # preenchido em 'atualizar' e 'duvida'


DECIDE_PROMPT = (
    "Você recebe uma ANOTAÇÃO NOVA e uma lista de NOTAS EXISTENTES da mesma pessoa. "
    "Decida o que fazer com a anotação nova.\n\n"
    "REGRA PRINCIPAL: só 'atualizar' quando a anotação nova é sobre EXATAMENTE A "
    "MESMA COISA ESPECÍFICA de uma nota — o mesmo item concreto que mudou de estado "
    "ou ganhou um detalhe. Pertencer à mesma CATEGORIA não basta.\n\n"
    "Exemplos:\n"
    "- Nota: 'estou no pity 72 na Nicole'. Nova: 'agora pity 74 na Nicole' → "
    "atualizar (é o MESMO pity, mudou o número).\n"
    "- Nota: 'reunião do Hunter sexta às 14h'. Nova: 'reunião às 15h com o time de "
    "IA' → criar (são reuniões DIFERENTES: outro assunto, outro horário; só serem "
    "'reuniões' não torna a mesma).\n"
    "- Duas ideias diferentes, dois projetos diferentes, dois eventos diferentes → "
    "sempre criar.\n\n"
    "Responda em uma linha, só isso:\n"
    "- 'atualizar N' se é a mesma coisa específica da nota N.\n"
    "- 'criar' se é assunto/item novo (na dúvida entre criar e atualizar, prefira criar).\n"
    "- 'duvida N' só se for realmente ambíguo se é a mesma coisa da nota N."
)


def decide_save_action(text: str, candidates: list[tuple[str, str]]) -> SaveAction:
    """Decide se a anotação cria, atualiza ou está em dúvida sobre uma nota.

    candidates é uma lista de (note_path, texto). Sem candidatos → sempre 'criar'.
    """
    if not candidates:
        return SaveAction("criar")

    blocos = []
    for i, (_id, texto) in enumerate(candidates):
        blocos.append(f"[{i}]\n{texto[:_RELATES_MAX_CHARS]}")
    lista = "\n\n".join(blocos)
    prompt = (
        f"ANOTAÇÃO NOVA:\n{text[:_RELATES_MAX_CHARS]}\n\n"
        f"NOTAS EXISTENTES:\n{lista}\n\nO que fazer?"
    )
    resposta = GeminiLLM().ask(prompt, system=DECIDE_PROMPT).lower().strip()

    numeros = re.findall(r"\d+", resposta)
    idx = int(numeros[0]) if numeros else -1
    valido = 0 <= idx < len(candidates)

    if resposta.startswith("atualizar") and valido:
        return SaveAction("atualizar", candidates[idx][0])
    if resposta.startswith("duvida") and valido:
        return SaveAction("duvida", candidates[idx][0])
    return SaveAction("criar")


# Instrução para mesclar a novidade numa nota existente SEM perder informação.
MERGE_PROMPT = (
    "Você atualiza uma nota Markdown existente com uma informação nova. "
    "REGRA CRÍTICA: preserve TODO o conteúdo atual — frontmatter, título e corpo — "
    "e apenas incorpore a novidade no lugar certo (ex.: troque um número que mudou, "
    "acrescente um fato). NÃO apague nem resuma o que já existe. Não invente. "
    "Se a nota tem uma seção '## Relacionadas' com links, mantenha-a intacta no fim. "
    "Responda só o Markdown completo da nota atualizada, sem comentários."
)


def merge_note(current_markdown: str, new_info: str) -> str:
    """Reescreve a nota existente incorporando a informação nova, preservando o resto."""
    prompt = (
        f"NOTA ATUAL:\n{current_markdown}\n\n"
        f"INFORMAÇÃO NOVA A INCORPORAR:\n{new_info}\n\nNota atualizada:"
    )
    return GeminiLLM().ask(prompt, system=MERGE_PROMPT).strip()
