"""
Pipeline de ingestão: vault do Obsidian → chunks → embeddings → banco.

SOMENTE LEITURA do vault — o projeto nunca escreve nas notas.

É incremental: guarda o hash de cada arquivo no banco e só re-embeda notas
que mudaram (ou que sumiram, para removê-las). Assim não se paga API à toa
a cada re-ingestão.

Uso (via camada de código):
    from src.ingest import ingest_vault
    resumo = ingest_vault()          # usa OBSIDIAN_VAULT_PATH do .env
    print(resumo)

Normalmente chamado pelo comando de linha: python scripts/ingest.py
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.config import settings
from src.db import Database
from src.embeddings import GeminiEmbeddings

# Tamanho aproximado do chunk. Sem tokenizer exato aqui: usamos caracteres como
# proxy (~4 chars por token → ~500 tokens ≈ 2000 chars) com sobreposição para
# não cortar ideias no meio. Simples e suficiente para notas em Markdown.
CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200

# Quantos textos mandar por chamada de embedding (equilíbrio custo/limites da API).
EMBED_BATCH_SIZE = 50


@dataclass
class IngestSummary:
    """Resultado de uma rodada de ingestão, para reportar ao usuário."""

    notes_seen: int = 0
    notes_ingested: int = 0
    notes_skipped: int = 0  # não mudaram desde a última vez
    notes_deleted: int = 0  # sumiram do vault
    chunks_written: int = 0

    def __str__(self) -> str:
        return (
            f"{self.notes_seen} notas no vault | "
            f"{self.notes_ingested} (re)ingeridas, "
            f"{self.notes_skipped} inalteradas, "
            f"{self.notes_deleted} removidas | "
            f"{self.chunks_written} chunks gravados"
        )


def _require_vault() -> Path:
    """Retorna o caminho do vault ou encerra com mensagem clara se faltar."""
    if not settings.obsidian_vault_path:
        raise SystemExit(
            "OBSIDIAN_VAULT_PATH não configurado.\n"
            "Aponte para a pasta do seu vault do Obsidian no .env."
        )
    vault = Path(settings.obsidian_vault_path)
    if not vault.is_dir():
        raise SystemExit(f"Vault não encontrado: {vault}")
    return vault


def _file_hash(text: str) -> str:
    """Hash estável do conteúdo — muda só quando o texto da nota muda."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_text(text: str) -> list[str]:
    """Divide o texto em pedaços de ~CHUNK_SIZE_CHARS com sobreposição."""
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    step = CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE_CHARS].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def ingest_vault(vault_path: str | None = None) -> IngestSummary:
    """Sincroniza o vault com o banco. Retorna um resumo do que mudou."""
    vault = Path(vault_path) if vault_path else _require_vault()

    db = Database()
    db.init_schema()
    embedder = GeminiEmbeddings()

    known_hashes = db.note_hashes()  # {note_path: file_hash} já no banco
    summary = IngestSummary()
    seen_paths: set[str] = set()

    for md_file in sorted(vault.rglob("*.md")):
        # Caminho relativo ao vault: identifica a nota de forma estável.
        note_path = md_file.relative_to(vault).as_posix()
        seen_paths.add(note_path)
        summary.notes_seen += 1

        content = md_file.read_text(encoding="utf-8", errors="replace")
        current_hash = _file_hash(content)

        # Incremental: se o hash bate com o do banco, a nota não mudou.
        if known_hashes.get(note_path) == current_hash:
            summary.notes_skipped += 1
            continue

        chunks = chunk_text(content)
        if not chunks:
            # Nota vazia: garante que não sobre lixo de uma versão anterior.
            db.delete_note(note_path)
            continue

        embeddings = _embed_all(embedder, chunks)
        db.replace_note_chunks(note_path, current_hash, chunks, embeddings)
        summary.notes_ingested += 1
        summary.chunks_written += len(chunks)
        print(f"  ingerida: {note_path} ({len(chunks)} chunks)")

    # Notas que estavam no banco mas sumiram do vault: remover.
    for gone in set(known_hashes) - seen_paths:
        db.delete_note(gone)
        summary.notes_deleted += 1
        print(f"  removida (sumiu do vault): {gone}")

    return summary


def _embed_all(embedder: GeminiEmbeddings, chunks: list[str]) -> list[list[float]]:
    """Embeda todos os chunks respeitando o tamanho de lote da API."""
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectors.extend(embedder.embed_batch(batch))
    return vectors
