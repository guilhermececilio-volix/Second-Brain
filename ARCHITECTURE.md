# Arquitetura — Second Brain

## Visão geral

O Second Brain responde perguntas sobre suas notas pessoais usando **RAG**
(Retrieval-Augmented Generation). A ideia central: em vez de esperar que o LLM
"saiba" o conteúdo das suas notas, nós **buscamos** os trechos relevantes e os
entregamos ao modelo junto com a pergunta.

O fluxo completo tem duas fases:

```
FASE 1 — INGESTÃO (roda quando as notas mudam)

  Vault Obsidian (.md)
        │  ler e dividir em chunks (pedaços de ~500 tokens)
        ▼
  Chunks de texto
        │  gemini-embedding-001 transforma cada chunk em vetor
        ▼
  Vetores (768 dims)
        │  gravar no PostgreSQL
        ▼
  pgvector (tabela: chunk, vetor, metadados da nota)


FASE 2 — CONSULTA (roda a cada pergunta)

  Pergunta do usuário
        │  mesma embedding transforma a pergunta em vetor
        ▼
  Vetor da pergunta
        │  busca por similaridade (cosseno) no pgvector
        ▼
  Top-K chunks mais parecidos
        │  montar prompt: "Contexto: <chunks>. Pergunta: <pergunta>"
        ▼
  gemini-2.5-flash gera a resposta
        ▼
  Resposta citando as notas de origem
```

## Por que cada peça

**Obsidian como fonte.** Suas notas já vivem lá, em Markdown puro. O projeto
apenas lê os arquivos do vault — nunca escreve neles. Zero lock-in.

**Embeddings (gemini-embedding-001).** Um embedding converte texto em um vetor
onde textos de significado parecido ficam geometricamente próximos. É isso que
permite achar "notas sobre produtividade" mesmo quando a nota nunca usa essa
palavra. Usamos 768 dimensões (o modelo suporta até 3072): bom equilíbrio entre
qualidade da busca e custo de armazenamento/velocidade no banco.

**PostgreSQL + pgvector.** O banco guarda os chunks e seus vetores, e faz a
busca por similaridade com índice próprio (HNSW). Escolhido em vez de um vector
DB dedicado (Pinecone, Chroma) porque Postgres é um banco completo: quando o
projeto virar multiusuário, usuários, permissões e notas ficam no mesmo lugar.

**LlamaIndex.** Framework que orquestra o pipeline de RAG (leitura do vault,
chunking, ingestão, retrieval, montagem do prompt). Evita reescrever
encanamento que já existe pronto e bem testado.

**Gemini para chat.** `gemini-2.5-flash`: rápido, barato e suficiente para
sintetizar respostas a partir de contexto recuperado. O wrapper em `src/llm.py`
isola o SDK — trocar de provedor no futuro afeta um arquivo só.

**Streamlit.** Interface web em Python puro para o MVP. Sem frontend separado.

## Camadas do código

```
scripts/          entrada do usuário (testes, chat, futuramente ingestão)
   │
src/llm.py        ┐
src/embeddings.py │  wrappers de IA — únicos arquivos que conhecem o SDK google-genai
   │              ┘
src/config.py     configuração — único arquivo que lê o .env
   │
src/db.py         [Sprint 2] — único arquivo que conhece SQL/pgvector
src/ingest.py     [Sprint 2] — pipeline vault -> chunks -> vetores -> banco
src/query.py      [Sprint 2] — pipeline pergunta -> retrieval -> resposta
```

Regra de ouro: **cada dependência externa (SDK, banco, .env) é conhecida por
exatamente um módulo**. O resto do código importa os wrappers.

## Decisões registradas

1. **Chunks de ~500 tokens com overlap** (Sprint 2): notas inteiras são grandes
   demais para busca precisa; frases soltas perdem contexto.
2. **Ingestão incremental por hash do arquivo** (Sprint 2): só re-embeddar
   notas que mudaram, para não pagar API à toa.
3. **Multiusuário fica para depois**: o schema do banco já nasce com coluna
   `owner` para facilitar a migração, mas autenticação não entra no MVP.
4. **Chave de API só no `.env`**: nunca em código, nunca no Git.
