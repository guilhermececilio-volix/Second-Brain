"""
Wrapper de embeddings do Gemini.

Transforma texto em vetores numéricos — a peça central do RAG.
Na Sprint 2, esses vetores serão gravados no PostgreSQL (pgvector)
e comparados por similaridade para achar as notas relevantes.

Uso:
    from src.embeddings import GeminiEmbeddings

    emb = GeminiEmbeddings()
    vetor = emb.embed("Minha primeira memória.")
    vetores = emb.embed_batch(["nota 1", "nota 2"])
"""

from google import genai

from src.config import settings

# gemini-embedding-001 aceita saída de 128 a 3072 dimensões.
# 768 é um bom equilíbrio entre qualidade e custo de armazenamento no pgvector.
DEFAULT_DIMENSIONS = 768


class GeminiEmbeddings:
    """Cliente de embeddings do Gemini com a configuração do projeto."""

    def __init__(self, model: str | None = None, dimensions: int = DEFAULT_DIMENSIONS):
        self.model = model or settings.embedding_model
        self.dimensions = dimensions
        self._client = genai.Client(api_key=settings.require_api_key())

    def embed(self, text: str) -> list[float]:
        """Gera o vetor de um único texto."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Gera vetores de vários textos em uma chamada (mais eficiente)."""
        resp = self._client.models.embed_content(
            model=self.model,
            contents=texts,
            config=genai.types.EmbedContentConfig(
                output_dimensionality=self.dimensions,
            ),
        )
        return [e.values for e in resp.embeddings]
