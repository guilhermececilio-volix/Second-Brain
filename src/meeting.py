"""
Ingestão de reuniões: transcrição → pontos importantes → notas no vault.

A ideia: você cola/sobe a transcrição de uma reunião e o sistema extrai os
pontos que importam (decisões, tarefas, datas, contexto), cria uma NOTA-MÃE da
reunião e uma NOTA-FILHA por ponto, todas linkadas entre si — reaproveitando
toda a "última milha" que já existe (structure_note, capture, auto-link).

Este módulo só faz a parte NOVA — a extração (transcrição → lista de pontos).
A criação das notas em si é orquestrada aqui usando as funções de ingest/query
que já existem. Segue a regra do projeto: não conhece SDK nem SQL diretamente.

Fluxo:
    extract_points(transcricao)  → MeetingExtraction (mãe + pontos), para o preview
    save_meeting(extraction)     → grava tudo no vault e devolve os caminhos

Uso via API: POST /meeting/extract (preview) e POST /meeting/save (grava).
"""

import io
import json
import re
from dataclasses import dataclass, field

from src.llm import GeminiLLM


def transcript_from_docx(data: bytes) -> str:
    """Extrai o texto de uma transcrição em .docx (Word/Teams).

    Recebe os bytes do arquivo enviado e devolve o texto puro, um parágrafo por
    linha. O import de python-docx fica contido aqui — é a única parte do
    projeto que lê .docx.
    """
    from docx import Document  # local: dependência isolada nesta função

    doc = Document(io.BytesIO(data))
    linhas = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not linhas:
        raise ValueError("O .docx não tem texto legível.")
    return "\n".join(linhas)

# Tipos de ponto que o sistema extrai (definido com o usuário).
TIPOS_VALIDOS = ("decisao", "tarefa", "data", "contexto")

# Instrução de extração: o coração da qualidade. Pede JSON estruturado e é
# explícito sobre NÃO inventar — numa transcrição, alucinar um dono de tarefa
# ou uma decisão que não houve é o erro mais caro.
EXTRACT_PROMPT = (
    "Você recebe a TRANSCRIÇÃO de uma reunião e extrai apenas os PONTOS QUE "
    "IMPORTAM, descartando conversa fiada. Responda SOMENTE um objeto JSON válido "
    "(sem cercas de código, sem comentários), no formato:\n"
    "{\n"
    '  "titulo": "título curto e descritivo da reunião",\n'
    '  "resumo": "2-3 frases resumindo o que foi tratado",\n'
    '  "participantes": ["nomes citados, se houver"],\n'
    '  "pontos": [\n'
    '    {"tipo": "decisao|tarefa|data|contexto", "texto": "o ponto em uma frase clara",\n'
    '     "responsavel": "nome ou null", "prazo": "quando ou null",\n'
    '     "data_iso": "YYYY-MM-DDTHH:MM:SS ou null"}\n'
    "  ]\n"
    "}\n\n"
    "Regras:\n"
    "- 'decisao': algo que ficou decidido/definido.\n"
    "- 'tarefa': uma ação a fazer; preencha 'responsavel' e 'prazo' se ditos.\n"
    "- 'data': reunião futura, marco ou deadline mencionado.\n"
    "- 'contexto': fato/informação relevante que não é decisão nem tarefa.\n"
    "- 'data_iso': SÓ quando houver uma data/hora concreta (reunião, deadline). "
    "Resolva relativos ('sexta que vem', 'amanhã') a partir da DATA DE HOJE e devolva "
    "em ISO 8601. Se só a data for dita (sem hora), use T09:00:00. Sem data concreta, null.\n"
    "- NÃO invente pontos, donos ou prazos. Se não foi dito, use null. Se a reunião "
    "não tem nada relevante de um tipo, simplesmente não gere pontos daquele tipo.\n"
    "- Cada ponto deve ser autossuficiente: quem ler a frase entende sem a transcrição."
)


@dataclass
class MeetingPoint:
    """Um ponto extraído da reunião."""

    tipo: str
    texto: str
    responsavel: str | None = None
    prazo: str | None = None
    data_iso: str | None = None  # data/hora ISO, quando o ponto tem quando concreto


@dataclass
class MeetingExtraction:
    """Resultado da extração — o que o usuário revisa antes de salvar."""

    titulo: str
    resumo: str
    participantes: list[str] = field(default_factory=list)
    pontos: list[MeetingPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializa para JSON (usado pela API e pelo preview no frontend)."""
        return {
            "titulo": self.titulo,
            "resumo": self.resumo,
            "participantes": self.participantes,
            "pontos": [
                {"tipo": p.tipo, "texto": p.texto, "responsavel": p.responsavel,
                 "prazo": p.prazo, "data_iso": p.data_iso}
                for p in self.pontos
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MeetingExtraction":
        """Reconstrói a partir do JSON (o frontend devolve isto, possivelmente editado)."""
        pontos = []
        for p in d.get("pontos", []):
            tipo = p.get("tipo", "contexto")
            if tipo not in TIPOS_VALIDOS:
                tipo = "contexto"
            texto = (p.get("texto") or "").strip()
            if not texto:
                continue  # descarta ponto vazio (usuário pode ter apagado no preview)
            pontos.append(
                MeetingPoint(
                    tipo=tipo,
                    texto=texto,
                    responsavel=(p.get("responsavel") or None),
                    prazo=(p.get("prazo") or None),
                    data_iso=(p.get("data_iso") or None),
                )
            )
        return cls(
            titulo=(d.get("titulo") or "Reunião").strip(),
            resumo=(d.get("resumo") or "").strip(),
            participantes=[s for s in d.get("participantes", []) if s],
            pontos=pontos,
        )


def _extract_json(texto: str) -> dict:
    """Extrai o objeto JSON da resposta do LLM, tolerando cercas de código."""
    # Remove cercas ```json ... ``` se o modelo insistir em usá-las.
    limpo = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    # Pega do primeiro { ao último } — robusto a texto extra em volta.
    inicio, fim = limpo.find("{"), limpo.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError("O modelo não retornou JSON reconhecível.")
    return json.loads(limpo[inicio : fim + 1])


def extract_points(transcricao: str, today: str | None = None) -> MeetingExtraction:
    """Extrai os pontos importantes de uma transcrição. NÃO grava nada.

    today (ex.: '08/07/2026') é passado de fora para o modelo resolver datas
    relativas ('sexta que vem', 'dia 20') no ano/contexto certo — sem isso ele
    chuta um ano errado. Este módulo não lê o relógio (regra do projeto).
    """
    transcricao = transcricao.strip()
    if not transcricao:
        raise ValueError("Transcrição vazia.")

    prompt = f"Data de hoje: {today}\n\nTRANSCRIÇÃO:\n{transcricao}" if today else transcricao
    resposta = GeminiLLM().ask(prompt, system=EXTRACT_PROMPT)
    dados = _extract_json(resposta)
    return MeetingExtraction.from_dict(dados)


def proposed_events(extraction: MeetingExtraction) -> list[dict]:
    """Pontos com data/hora concreta viram eventos PROPOSTOS para a agenda.

    Não cria nada — só monta a lista que o usuário vai revisar e confirmar. Cada
    evento: {texto, data_iso, duracao_min}. Considera pontos 'data' (ou qualquer
    ponto que o extrator tenha marcado com data_iso).
    """
    eventos = []
    for p in extraction.pontos:
        if p.data_iso:
            eventos.append(
                {
                    "titulo": p.texto if len(p.texto) <= 80 else p.texto[:77] + "...",
                    "data_iso": p.data_iso,
                    "duracao_min": 60,  # padrão; o usuário ajusta no preview
                }
            )
    return eventos


# --- Conversão de pontos em Markdown de nota ------------------------------

_TIPO_LABEL = {
    "decisao": "Decisão",
    "tarefa": "Tarefa",
    "data": "Data / próximo passo",
    "contexto": "Contexto",
}


def _mother_markdown(extraction: MeetingExtraction, date_str: str) -> str:
    """Markdown da nota-mãe da reunião: resumo, participantes e os pontos listados."""
    linhas = [
        "---",
        "tipo: reuniao",
        f"data: {date_str}",
        "tags: [reuniao]",
        "---",
        "",
        f"# {extraction.titulo}",
        "",
        extraction.resumo,
    ]
    if extraction.participantes:
        linhas += ["", "**Participantes:** " + ", ".join(extraction.participantes)]
    if extraction.pontos:
        linhas += ["", "## Pontos"]
        for p in extraction.pontos:
            sufixo = ""
            if p.responsavel:
                sufixo += f" _(resp.: {p.responsavel}"
                sufixo += f", prazo: {p.prazo})_" if p.prazo else ")_"
            elif p.prazo:
                sufixo += f" _(prazo: {p.prazo})_"
            linhas.append(f"- **{_TIPO_LABEL.get(p.tipo, p.tipo)}:** {p.texto}{sufixo}")
    return "\n".join(linhas) + "\n"


def _point_markdown(point: MeetingPoint, meeting_title: str, date_str: str) -> str:
    """Markdown de uma nota-filha (um ponto)."""
    tags = f"[{point.tipo}, reuniao]"
    corpo = [point.texto]
    if point.responsavel:
        corpo.append(f"\n**Responsável:** {point.responsavel}")
    if point.prazo:
        corpo.append(f"**Prazo:** {point.prazo}")
    titulo = point.texto if len(point.texto) <= 60 else point.texto[:57] + "..."
    return (
        f"---\ntipo: {point.tipo}\ndata: {date_str}\ntags: {tags}\n"
        f"origem: {meeting_title}\n---\n\n# {titulo}\n\n" + "\n".join(corpo) + "\n"
    )
