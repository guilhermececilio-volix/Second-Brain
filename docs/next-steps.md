# Próximos passos — Sprint 2 (RAG / MVP)

Visão geral das sprints em [`roadmap.md`](roadmap.md). Aqui está o passo a passo prático, na ordem.

## Passo 0 — Validar a Sprint 1 (manual, na sua máquina)

```powershell
copy .env.example .env    # cole sua chave do Google AI Studio
python scripts\test_gemini.py
```

Só siga adiante se este teste passar.

## Passo 1 — Subir PostgreSQL + pgvector (manual)

Instalar Docker Desktop e criar um `docker-compose.yml` na raiz com a imagem
`pgvector/pgvector:pg17`. Depois:

```powershell
docker compose up -d
```

E preencher `DATABASE_URL` no `.env`.

## Passo 2 — `src/db.py`

Conexão com o banco + criação do schema:

- Tabela `chunks`: id, caminho da nota, hash do arquivo, texto do chunk,
  vetor `vector(768)`, coluna `owner` (preparo para multiusuário)
- Índice HNSW para busca por similaridade de cosseno
- Única camada do projeto que fala SQL

## Passo 3 — `src/ingest.py` + `scripts/ingest.py`

Pipeline vault → banco:

- Ler `.md` do vault (`OBSIDIAN_VAULT_PATH` no `.env`) — **somente leitura**
- Chunking: ~500 tokens com overlap
- Incremental: comparar hash do arquivo e só re-embeddar o que mudou
- Gerar embeddings em lote (`embed_batch`) e gravar

## Passo 4 — `src/query.py` + `scripts/ask.py`

Pipeline pergunta → resposta:

- Embedding da pergunta → top-K chunks por similaridade
- Montar prompt com contexto + pergunta
- Resposta do Gemini citando as notas de origem

## Passo 5 — Interface Streamlit (`app.py`)

Caixa de pergunta, resposta e lista de fontes. `streamlit run app.py`.

## Critério de pronto do MVP

Ingerir o vault real e obter resposta correta citando a nota de origem.
