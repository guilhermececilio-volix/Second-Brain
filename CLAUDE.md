# Contexto para agentes de IA (Cowork / Claude Code)

## O que é este projeto

Second Brain pessoal: lê o vault do Obsidian do usuário e responde perguntas
sobre as notas usando RAG (pgvector + Gemini). MVP single-user; multiusuário no futuro.

Leia `ARCHITECTURE.md` antes de mexer no código. Roadmap em `docs/roadmap.md`.

## Estado atual

Sprint 1 concluída: config, wrappers de LLM/embeddings e scripts de teste.
Sprint 2 pendente: `src/db.py`, `src/ingest.py`, `src/query.py`, Streamlit.

## Regras do projeto

- **Segredos só no `.env`** — nunca hardcode de chave, nunca commitar `.env`.
- **Um módulo por dependência externa**: só `src/llm.py` e `src/embeddings.py`
  importam `google.genai`; só `src/config.py` lê o `.env`; só `src/db.py`
  (futuro) fala SQL. Não vaze SDKs para outros arquivos.
- **Escrita no vault é sempre append-only** — o app lê todas as notas; cria
  novas em `Capturas/` e, ao guardar, acrescenta uma seção `## Relacionadas`
  com `[[links]]` (nos dois sentidos) tanto na nota nova quanto nas parecidas.
  Nunca reescreve nem apaga o texto que o usuário já tinha — só adiciona links.
- Embeddings com **768 dimensões** (definido em `src/embeddings.py`). Se mudar,
  o schema do pgvector muda junto.
- Idioma do código: identificadores em inglês, docstrings/comentários em pt-BR.
- Rodar scripts a partir da raiz: `python scripts/test_gemini.py`.

## Ambiente

- Windows + PowerShell, Python com venv em `venv/`.
- Chave do Google AI Studio em `.env` (`GEMINI_API_KEY`).
- Modelos padrão: `gemini-3.1-flash-lite` (chat — 500 req/dia no free tier, bem
  acima dos 20/dia do 2.5-flash), `gemini-embedding-001` (embeddings).
