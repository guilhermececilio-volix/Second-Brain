"""
Avaliação da qualidade do RAG — mede o retrieval (e, opcionalmente, a resposta).

Motivação: sem medir, qualquer ajuste de chunking, top-K ou prompt é no escuro.
Este módulo roda um conjunto de casos {pergunta, nota_esperada/keyword} contra o
vault JÁ ingerido no banco e reporta métricas objetivas.

Duas camadas, medidas em separado de propósito (um número só esconderia onde está
a falha):

1. RETRIEVAL (barato, determinístico, sem LLM): para cada caso com `nota_esperada`,
   a nota certa apareceu entre os top-K chunks recuperados?
     - Hit@k: fração de casos em que a nota esperada entrou no top-K.
     - MRR:   média de 1/posição da nota esperada (rank 1 vale mais que rank 5).

2. RESPOSTA (mais caro, usa o LLM — só com grounding=True):
     - keyword: os termos esperados aparecem na resposta?
     - sem_evidencia: numa pergunta sem resposta no vault, o sistema RECUSA
       ("não cobrem isso") em vez de alucinar?

Uso (via código):
    from src.eval import run_eval, load_cases
    relatorio = run_eval(load_cases(), top_k=5, grounding=False)
    print(relatorio)

Normalmente chamado pela linha de comando: python scripts/eval.py
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.config import PROJECT_ROOT
from src.db import Database
from src.embeddings import GeminiEmbeddings

# Conjunto de casos padrão (versionado no repo).
DEFAULT_CASES_PATH = PROJECT_ROOT / "eval" / "cases.json"

# Trecho que o SYSTEM_PROMPT de query.py instrui o modelo a usar quando não há
# evidência. Mantido em sincronia com aquele prompt: se a frase de recusa mudar
# lá, atualize aqui. Comparação é frouxa (substring, minúsculas).
RECUSA_MARKERS = ("não cobrem", "nao cobrem", "não sei", "nao sei", "não encontrei", "nao encontrei")


@dataclass
class Case:
    """Um caso de teste do eval. Só 'pergunta' é obrigatória."""

    id: str
    pergunta: str
    nota_esperada: str | None = None
    keyword: list[str] = field(default_factory=list)
    sem_evidencia: bool = False


@dataclass
class CaseResult:
    """Resultado de um caso, com o que foi medido (campos None = não avaliado)."""

    case: Case
    rank: int | None = None          # posição (1-based) da nota esperada no top-K; None = não achou
    keyword_ok: bool | None = None   # todas as keywords apareceram na resposta?
    recusou: bool | None = None      # o sistema recusou (para sem_evidencia)?


def load_cases(path: Path | str = DEFAULT_CASES_PATH) -> list[Case]:
    """Lê os casos do arquivo JSON. Ignora chaves começando com '_' (comentários)."""
    dados = json.loads(Path(path).read_text(encoding="utf-8"))
    casos = []
    for i, bruto in enumerate(dados.get("casos", [])):
        casos.append(
            Case(
                id=str(bruto.get("id", f"caso-{i}")),
                pergunta=bruto["pergunta"],
                nota_esperada=bruto.get("nota_esperada"),
                keyword=bruto.get("keyword", []) or [],
                sem_evidencia=bool(bruto.get("sem_evidencia", False)),
            )
        )
    return casos


def _rank_da_nota(note_path: str, hit_paths: list[str]) -> int | None:
    """Posição 1-based da primeira ocorrência da nota nos hits; None se ausente.

    Os hits vêm ordenados por relevância e podem repetir a mesma nota (vários
    chunks); consideramos a melhor (primeira) posição em que a nota aparece.
    """
    for i, path in enumerate(hit_paths, start=1):
        if path == note_path:
            return i
    return None


def _avalia_resposta(case: Case, texto: str) -> tuple[bool | None, bool | None]:
    """Avalia a resposta do LLM: (keyword_ok, recusou). None quando não se aplica."""
    baixo = texto.lower()

    recusou = None
    if case.sem_evidencia:
        recusou = any(m in baixo for m in RECUSA_MARKERS)

    keyword_ok = None
    if case.keyword:
        keyword_ok = all(k.lower() in baixo for k in case.keyword)

    return keyword_ok, recusou


def run_eval(
    cases: list[Case],
    top_k: int = 5,
    grounding: bool = False,
) -> "EvalReport":
    """Roda o eval. grounding=True também chama o LLM para avaliar a resposta."""
    embedder = GeminiEmbeddings()
    db = Database()

    # answer() é importado aqui dentro para não pagar o custo se grounding=False
    # e para deixar explícito que a camada 1 (retrieval) não depende do LLM.
    answer = None
    if grounding:
        from src.query import answer as _answer
        answer = _answer

    resultados: list[CaseResult] = []
    for case in cases:
        res = CaseResult(case=case)

        # Camada 1 — retrieval (sempre que houver nota esperada).
        if case.nota_esperada:
            vetor = embedder.embed(case.pergunta)
            hits = db.search(vetor, top_k=top_k)
            res.rank = _rank_da_nota(case.nota_esperada, [h.note_path for h in hits])

        # Camada 2 — resposta (só com grounding, e só se houver o que medir).
        if grounding and (case.keyword or case.sem_evidencia):
            texto = answer(case.pergunta, top_k=top_k).text
            res.keyword_ok, res.recusou = _avalia_resposta(case, texto)

        resultados.append(res)

    return EvalReport(resultados=resultados, top_k=top_k, grounding=grounding)


@dataclass
class EvalReport:
    """Agrega os resultados e calcula as métricas."""

    resultados: list[CaseResult]
    top_k: int
    grounding: bool

    # --- Métricas de retrieval ---

    @property
    def _com_nota(self) -> list[CaseResult]:
        return [r for r in self.resultados if r.case.nota_esperada]

    @property
    def hit_at_k(self) -> float | None:
        """Fração de casos (com nota esperada) em que a nota entrou no top-K."""
        base = self._com_nota
        if not base:
            return None
        acertos = sum(1 for r in base if r.rank is not None)
        return acertos / len(base)

    @property
    def mrr(self) -> float | None:
        """Mean Reciprocal Rank: média de 1/posição (0 quando a nota não apareceu)."""
        base = self._com_nota
        if not base:
            return None
        soma = sum((1.0 / r.rank) if r.rank else 0.0 for r in base)
        return soma / len(base)

    # --- Métricas de resposta (só com grounding) ---

    @property
    def keyword_rate(self) -> float | None:
        base = [r for r in self.resultados if r.keyword_ok is not None]
        if not base:
            return None
        return sum(1 for r in base if r.keyword_ok) / len(base)

    @property
    def recusa_rate(self) -> float | None:
        base = [r for r in self.resultados if r.recusou is not None]
        if not base:
            return None
        return sum(1 for r in base if r.recusou) / len(base)

    def __str__(self) -> str:
        linhas = [f"Eval RAG — {len(self.resultados)} casos, top_k={self.top_k}", ""]

        # Detalhe por caso (retrieval).
        for r in self.resultados:
            if r.case.nota_esperada:
                if r.rank:
                    marca = f"✓ rank {r.rank}"
                else:
                    marca = f"✗ fora do top-{self.top_k}"
                linhas.append(f"  [{r.case.id}] retrieval: {marca}")
            if r.keyword_ok is not None:
                linhas.append(f"  [{r.case.id}] keyword: {'✓' if r.keyword_ok else '✗'}")
            if r.recusou is not None:
                linhas.append(f"  [{r.case.id}] recusa (sem evidência): {'✓' if r.recusou else '✗ ALUCINOU'}")

        linhas.append("")
        linhas.append("Retrieval:")
        if self.hit_at_k is not None:
            linhas.append(f"  Hit@{self.top_k}: {self.hit_at_k:.0%}  |  MRR: {self.mrr:.3f}")
        else:
            linhas.append("  (nenhum caso com 'nota_esperada')")

        if self.grounding:
            linhas.append("Resposta:")
            if self.keyword_rate is not None:
                linhas.append(f"  keyword presente: {self.keyword_rate:.0%}")
            if self.recusa_rate is not None:
                linhas.append(f"  recusa correta (sem evidência): {self.recusa_rate:.0%}")
            if self.keyword_rate is None and self.recusa_rate is None:
                linhas.append("  (nenhum caso com 'keyword' ou 'sem_evidencia')")
        else:
            linhas.append("Resposta: não avaliada (rode com --grounding para incluir o LLM)")

        return "\n".join(linhas)
