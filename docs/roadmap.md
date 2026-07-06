# Roadmap

## Sprint 1 — Fundação ✅ (esta versão)

Objetivo: estrutura do projeto pronta e API do Gemini validada.

- [x] Estrutura de pastas (`src/`, `scripts/`, `docs/`, `data/`)
- [x] `src/config.py` — configuração central via `.env`
- [x] `src/llm.py` — wrapper de chat (Gemini 2.5 Flash)
- [x] `src/embeddings.py` — wrapper de embeddings (gemini-embedding-001, 768 dims)
- [x] `scripts/test_gemini.py` — valida chave, chat e embeddings
- [x] `scripts/chat.py` — chat interativo com histórico
- [x] Documentação: README, ARCHITECTURE.md, CLAUDE.md

**Critério de pronto:** `python scripts/test_gemini.py` roda sem erro.

## Sprint 2 — RAG funcionando (MVP)

Objetivo: perguntar sobre as próprias notas e receber resposta com fontes.

- [ ] Subir PostgreSQL com pgvector (Docker recomendado)
- [ ] `src/db.py` — conexão + schema (tabela de chunks com vetor 768d, índice HNSW)
- [ ] `src/ingest.py` — ler vault do Obsidian → chunking (~500 tokens, com overlap) → embeddings → banco; incremental por hash do arquivo
- [ ] `src/query.py` — pergunta → embedding → top-K por similaridade → prompt com contexto → resposta citando notas
- [ ] `scripts/ingest.py` e `scripts/ask.py` — comandos de linha
- [ ] Interface Streamlit (`app.py`) — caixa de pergunta + resposta + fontes

**Critério de pronto:** ingerir o vault real e obter resposta correta citando a nota de origem.

## Depois (fora do MVP)

- Multiusuário (autenticação, coluna `owner` já prevista no schema)
- Sincronização automática do vault (watcher)
- Avaliação de qualidade do retrieval
