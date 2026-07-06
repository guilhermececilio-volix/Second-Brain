"""
Camada de banco de dados — única parte do projeto que fala SQL/pgvector.

Guarda os chunks das notas e seus vetores de embedding, e faz a busca por
similaridade de cosseno. Nenhum outro módulo importa psycopg ou escreve SQL:
ingest.py e query.py chamam as funções daqui.

Uso:
    from src.db import Database

    db = Database()
    db.init_schema()                     # cria tabela + índice (idempotente)
    db.replace_note_chunks(...)          # regrava os chunks de uma nota
    resultados = db.search(vetor, top_k=5)
"""

from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector

from src.config import settings
from src.embeddings import DEFAULT_DIMENSIONS

# Dono padrão dos chunks. O schema já nasce multiusuário (coluna owner),
# mas no MVP single-user usamos sempre este valor.
DEFAULT_OWNER = "me"


@dataclass(frozen=True)
class SearchHit:
    """Um chunk recuperado pela busca por similaridade."""

    note_path: str
    chunk_text: str
    distance: float  # distância de cosseno (0 = idêntico, 2 = oposto)


class Database:
    """Acesso ao PostgreSQL + pgvector com a configuração do projeto."""

    def __init__(self, dsn: str | None = None, dimensions: int = DEFAULT_DIMENSIONS):
        self.dsn = dsn or self._require_dsn()
        self.dimensions = dimensions

    @staticmethod
    def _require_dsn() -> str:
        """Retorna a DATABASE_URL ou encerra com mensagem clara se faltar."""
        if not settings.database_url:
            raise SystemExit(
                "DATABASE_URL não configurada.\n"
                "Suba o banco com 'docker compose up -d' e preencha DATABASE_URL no .env "
                "(o valor de exemplo já bate com o docker-compose.yml)."
            )
        return settings.database_url

    @contextmanager
    def _connect(self, with_vector: bool = True):
        """Abre uma conexão e fecha ao final.

        with_vector=True registra o tipo `vector` do pgvector — só funciona se a
        extensão já existir no banco. init_schema() usa False porque é ele quem
        cria a extensão (senão vira problema do ovo e da galinha na 1ª execução).
        """
        with psycopg.connect(self.dsn) as conn:
            if with_vector:
                register_vector(conn)
            yield conn

    def init_schema(self) -> None:
        """Cria a extensão, a tabela de chunks e o índice HNSW. Idempotente."""
        with self._connect(with_vector=False) as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    owner       TEXT    NOT NULL DEFAULT '{DEFAULT_OWNER}',
                    note_path   TEXT    NOT NULL,
                    file_hash   TEXT    NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text  TEXT    NOT NULL,
                    embedding   vector({self.dimensions}) NOT NULL
                );
                """
            )
            # Índice HNSW para busca aproximada por distância de cosseno.
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
                ON chunks USING hnsw (embedding vector_cosine_ops);
                """
            )
            # Acelera o passo incremental (buscar hash atual por nota).
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS chunks_note_path_idx
                ON chunks (owner, note_path);
                """
            )
            conn.commit()

    def note_hashes(self, owner: str = DEFAULT_OWNER) -> dict[str, str]:
        """Mapa {note_path: file_hash} já ingerido — base da ingestão incremental."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT note_path, file_hash FROM chunks WHERE owner = %s;",
                (owner,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    def replace_note_chunks(
        self,
        note_path: str,
        file_hash: str,
        chunks: list[str],
        embeddings: list[list[float]],
        owner: str = DEFAULT_OWNER,
    ) -> None:
        """Regrava todos os chunks de uma nota numa transação (apaga e reinsere)."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks e embeddings devem ter o mesmo tamanho.")

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chunks WHERE owner = %s AND note_path = %s;",
                (owner, note_path),
            )
            for i, (text, vector) in enumerate(zip(chunks, embeddings)):
                cur.execute(
                    """
                    INSERT INTO chunks
                        (owner, note_path, file_hash, chunk_index, chunk_text, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (owner, note_path, file_hash, i, text, vector),
                )
            conn.commit()

    def delete_note(self, note_path: str, owner: str = DEFAULT_OWNER) -> None:
        """Remove todos os chunks de uma nota (ex.: arquivo apagado no vault)."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chunks WHERE owner = %s AND note_path = %s;",
                (owner, note_path),
            )
            conn.commit()

    def search(
        self, query_vector: list[float], top_k: int = 5, owner: str = DEFAULT_OWNER
    ) -> list[SearchHit]:
        """Retorna os top_k chunks mais próximos do vetor da pergunta (cosseno)."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT note_path, chunk_text, embedding <=> %s::vector AS distance
                FROM chunks
                WHERE owner = %s
                ORDER BY distance
                LIMIT %s;
                """,
                (query_vector, owner, top_k),
            )
            return [SearchHit(row[0], row[1], row[2]) for row in cur.fetchall()]

    def related_notes(
        self,
        query_vector: list[float],
        exclude_note: str,
        top_k: int = 8,
        max_distance: float = 0.5,
        owner: str = DEFAULT_OWNER,
    ) -> list[tuple[str, float]]:
        """Pré-seleciona candidatos a link por proximidade de embedding.

        Não decide o link sozinha — só reduz o universo às notas mais próximas
        (teto frouxo, para descartar o claramente distante). Quem decide se há
        relação de verdade é o Gemini (ver query.relates). Agrupa por nota (menor
        distância entre os chunks), exclui a própria nota-fonte. Lista de
        (note_path, distância), da mais parecida para a menos.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT note_path, MIN(embedding <=> %s::vector) AS distance
                FROM chunks
                WHERE owner = %s AND note_path <> %s
                GROUP BY note_path
                HAVING MIN(embedding <=> %s::vector) <= %s
                ORDER BY distance
                LIMIT %s;
                """,
                (query_vector, owner, exclude_note, query_vector, max_distance, top_k),
            )
            return [(row[0], row[1]) for row in cur.fetchall()]
