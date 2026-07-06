# Próximos passos — Sprint 2 (RAG / MVP)

Visão geral das sprints em [`roadmap.md`](roadmap.md). Aqui está o passo a passo prático, na ordem.

## Passo 0 — Validar a Sprint 1 (manual, na sua máquina)

```powershell
copy .env.example .env    # cole sua chave do Google AI Studio
python scripts\test_gemini.py
```

Só siga adiante se este teste passar.

## Passo 1 — Subir PostgreSQL + pgvector ✅ (compose pronto)

O `docker-compose.yml` já existe na raiz (imagem `pgvector/pgvector:pg17`).
Instale o Docker Desktop, depois, da raiz do projeto:

```powershell
docker compose up -d
```

E preencha `DATABASE_URL` no `.env` (o valor de exemplo já bate com o compose).

## Passo 2 — `src/db.py` ✅ (implementado)

Conexão com o banco + criação do schema, via `psycopg` + `pgvector`:

- Tabela `chunks`: id, `owner`, caminho da nota, hash do arquivo, índice do
  chunk, texto e vetor `vector(768)`
- Índice HNSW para busca por similaridade de cosseno
- Única camada do projeto que fala SQL

## Passo 3 — `src/ingest.py` + `scripts/ingest.py` ✅ (implementado)

Pipeline vault → banco:

- Lê `.md` do vault (`OBSIDIAN_VAULT_PATH` no `.env`) — **somente leitura**
- Chunking com overlap (proxy por caracteres, ~500 tokens)
- Incremental: compara hash do arquivo e só re-embeda o que mudou; remove
  do banco notas que sumiram do vault
- Gera embeddings em lote (`embed_batch`) e grava

Rodar: `python scripts/ingest.py`

## Passo 4 — `src/query.py` + `scripts/ask.py` ✅ (implementado)

Pipeline pergunta → resposta:

- Embedding da pergunta → top-K chunks por similaridade
- Monta prompt com contexto + pergunta; instrução de sistema restringe a
  resposta ao contexto (não inventa) e pede citação das notas
- Resposta do Gemini citando as notas de origem

Rodar: `python scripts/ask.py "sua pergunta"` (ou sem argumento p/ modo interativo)

## Passo 5 — Interface Streamlit (`app.py`)

Caixa de pergunta, resposta e lista de fontes. `streamlit run app.py`.

## Critério de pronto do MVP

Ingerir o vault real e obter resposta correta citando a nota de origem.
