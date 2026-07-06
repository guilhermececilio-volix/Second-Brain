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
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.config import settings
from src.db import Database
from src.embeddings import GeminiEmbeddings
from src.query import filter_related

# Subpasta do cofre onde vão as capturas rápidas (notas criadas pelo app,
# não escritas à mão no Obsidian). Mantém as capturas separadas e deixa
# claro que a escrita do app se limita a esta pasta.
CAPTURE_SUBDIR = "Capturas"

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


def _title_slug(text: str) -> str:
    """Gera um trecho curto e seguro para o nome do arquivo.

    Prefere o título '# ...' (nota estruturada); senão, a primeira linha de
    conteúdo, ignorando frontmatter YAML.
    """
    linhas = [l.strip() for l in text.strip().splitlines()]
    base = "nota"
    # 1) título markdown '# ...'
    for l in linhas:
        if l.startswith("# "):
            base = l[2:]
            break
    else:
        # 2) primeira linha que não seja frontmatter/marcador
        for l in linhas:
            if l and l != "---" and not l.startswith("#"):
                base = l
                break

    slug = re.sub(r"[^\w\s-]", "", base).strip()
    slug = re.sub(r"\s+", "-", slug)
    return slug[:40] or "nota"


def capture(text: str, vault_path: str | None = None) -> str:
    """Guarda um texto no cérebro: cria um .md no cofre e o indexa.

    Escreve APENAS na subpasta de capturas do cofre — o Obsidian continua a
    fonte da verdade, e a nota fica visível/editável lá. Retorna o caminho
    relativo da nota criada.
    """
    text = text.strip()
    if not text:
        raise ValueError("Não há texto para guardar.")

    vault = Path(vault_path) if vault_path else _require_vault()
    capturas = vault / CAPTURE_SUBDIR
    capturas.mkdir(parents=True, exist_ok=True)  # única escrita no vault

    # Nome único por data/hora + trecho do conteúdo, sem colidir.
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    filename = f"{stamp}-{_title_slug(text)}.md"
    md_file = capturas / filename

    md_file.write_text(text + "\n", encoding="utf-8")

    note_path = md_file.relative_to(vault).as_posix()
    ingest_note(md_file, note_path)
    _autolink(vault, md_file, note_path, text)
    return note_path


def update_capture(note_path: str, text: str, vault_path: str | None = None) -> None:
    """Regrava o conteúdo de uma captura e re-indexa (para o botão Editar)."""
    text = text.strip()
    if not text:
        raise ValueError("Não há texto para salvar.")
    vault = Path(vault_path) if vault_path else _require_vault()
    md_file = vault / note_path
    md_file.write_text(text + "\n", encoding="utf-8")
    ingest_note(md_file, note_path)


def delete_capture(note_path: str, vault_path: str | None = None) -> None:
    """Apaga uma captura do cofre e do banco (para o botão Desfazer)."""
    vault = Path(vault_path) if vault_path else _require_vault()
    md_file = vault / note_path
    if md_file.is_file():
        md_file.unlink()
    Database().delete_note(note_path)


# Marca a seção de links que o app gerencia. Só mexemos dentro dela — o texto
# que o usuário escreveu acima nunca é tocado.
RELATED_HEADER = "## Relacionadas"

# Auto-link em dois estágios: o embedding pré-seleciona os candidatos mais
# próximos (barato) e o Gemini decide, par a par, se há relação real (ver
# query.relates). Assim não dependemos de um "corte mágico" de distância, que
# não escala conforme o número de notas cresce.
CANDIDATES_TOP_K = 8  # quantos vizinhos o embedding sugere para o Gemini julgar


def _note_name(note_path: str) -> str:
    """Nome do wikilink [[...]] do Obsidian: basename sem a extensão .md."""
    return Path(note_path).stem


def _add_link(md_file: Path, target_note: str) -> bool:
    """Acrescenta um [[link]] para target_note na seção Relacionadas da nota.

    Append-only: preserva todo o conteúdo existente e não duplica links.
    Retorna True se o arquivo mudou.
    """
    link = f"[[{_note_name(target_note)}]]"
    content = md_file.read_text(encoding="utf-8", errors="replace")

    if link in content:  # já linkado — nada a fazer
        return False

    if RELATED_HEADER in content:
        # Seção já existe: acrescenta o link logo após o cabeçalho.
        content = content.replace(RELATED_HEADER, f"{RELATED_HEADER}\n- {link}", 1)
    else:
        # Cria a seção no fim da nota.
        sep = "" if content.endswith("\n") else "\n"
        content = f"{content}{sep}\n{RELATED_HEADER}\n- {link}\n"

    md_file.write_text(content, encoding="utf-8")
    return True


def _autolink(vault: Path, md_file: Path, note_path: str, text: str) -> list[str]:
    """Conecta a nota recém-criada às mais parecidas, com links nos dois sentidos.

    Insere links para as relacionadas na nota nova e um backlink em cada
    relacionada. Só acrescenta (nunca reescreve o que já existia) e re-indexa
    as notas alteradas para o banco não dessincronizar. Retorna os note_path
    das notas relacionadas.
    """
    embedder = GeminiEmbeddings()
    db = Database()
    candidatos = db.related_notes(
        embedder.embed(text),
        exclude_note=note_path,
        top_k=CANDIDATES_TOP_K,
    )
    if not candidatos:
        return []

    # Lê o texto de cada candidato existente e deixa o Gemini decidir todos de
    # uma vez (uma única chamada, para não estourar o limite por minuto).
    pares: list[tuple[str, str]] = []
    for rel_path, _distance in candidatos:
        rel_file = vault / rel_path
        if rel_file.is_file():
            pares.append((rel_path, rel_file.read_text(encoding="utf-8", errors="replace")))

    linked = filter_related(text, pares)

    for rel_path in linked:
        # Links nos dois sentidos (append-only). Re-indexa quem mudou.
        _add_link(md_file, rel_path)
        if _add_link(vault / rel_path, note_path):
            ingest_note(vault / rel_path, rel_path)

    if linked:
        # A nota nova ganhou a seção Relacionadas -> re-indexa.
        ingest_note(md_file, note_path)
    return linked


def _strip_related(md_file: Path) -> None:
    """Remove a seção '## Relacionadas' (e tudo abaixo dela) de uma nota.

    Só apaga a seção gerenciada pelo app — o texto que o usuário escreveu acima
    fica intacto. Usado para regerar os links do zero.
    """
    content = md_file.read_text(encoding="utf-8", errors="replace")
    if RELATED_HEADER not in content:
        return
    antes = content.split(RELATED_HEADER, 1)[0].rstrip() + "\n"
    md_file.write_text(antes, encoding="utf-8")


def rebuild_links(vault_path: str | None = None) -> int:
    """Regenera as seções Relacionadas de todas as notas do zero.

    Apaga os links existentes e recria: embedding pré-seleciona candidatos e o
    Gemini decide cada par. Útil após mudar o método/critério de relação.
    Retorna quantas notas ficaram com pelo menos um link.
    """
    vault = Path(vault_path) if vault_path else _require_vault()
    md_files = sorted(vault.rglob("*.md"))

    # 1) Limpa todas as seções e re-indexa o conteúdo sem os links antigos.
    for md_file in md_files:
        _strip_related(md_file)
        ingest_note(md_file, md_file.relative_to(vault).as_posix())

    # 2) Para cada nota, pré-seleciona candidatos e deixa o Gemini julgar.
    embedder = GeminiEmbeddings()
    db = Database()
    com_links = set()
    for md_file in md_files:
        note_path = md_file.relative_to(vault).as_posix()
        texto = md_file.read_text(encoding="utf-8", errors="replace")
        if not texto.strip():  # nota vazia: nada a relacionar (e embed rejeita vazio)
            continue
        candidatos = db.related_notes(
            embedder.embed(texto), exclude_note=note_path, top_k=CANDIDATES_TOP_K
        )
        pares = []
        for rel_path, _dist in candidatos:
            rel_file = vault / rel_path
            if rel_file.is_file():
                pares.append((rel_path, rel_file.read_text(encoding="utf-8", errors="replace")))

        # Uma única chamada julga todos os candidatos desta nota.
        for rel_path in filter_related(texto, pares):
            # Dois sentidos explícitos.
            _add_link(md_file, rel_path)
            _add_link(vault / rel_path, note_path)
            com_links.add(note_path)
            com_links.add(rel_path)

    # 3) Re-indexa o resultado final (notas agora com os links novos).
    for md_file in md_files:
        ingest_note(md_file, md_file.relative_to(vault).as_posix())

    return len(com_links)


def ingest_note(md_file: Path, note_path: str) -> int:
    """Indexa uma única nota no banco. Retorna quantos chunks gravou."""
    content = md_file.read_text(encoding="utf-8", errors="replace")
    chunks = chunk_text(content)

    db = Database()
    db.init_schema()

    if not chunks:
        db.delete_note(note_path)
        return 0

    embedder = GeminiEmbeddings()
    embeddings = _embed_all(embedder, chunks)
    db.replace_note_chunks(note_path, _file_hash(content), chunks, embeddings)
    return len(chunks)


def _embed_all(embedder: GeminiEmbeddings, chunks: list[str]) -> list[list[float]]:
    """Embeda todos os chunks respeitando o tamanho de lote da API."""
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectors.extend(embedder.embed_batch(batch))
    return vectors
