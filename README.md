# Second Brain

Um "segundo cérebro" pessoal com IA: lê suas notas (vault do Obsidian) e responde
perguntas sobre elas usando RAG (busca semântica + LLM).

> Fase atual: MVP de uso pessoal. Futuro: multiusuário com colaboradores.

## Stack

Python · Obsidian (fonte) · PostgreSQL + pgvector · LlamaIndex · Gemini (embeddings + chat) · Streamlit

Detalhes em [`ARCHITECTURE.md`](ARCHITECTURE.md). Contexto para agentes de IA em [`CLAUDE.md`](CLAUDE.md).

## Estrutura

```
Second-Brain/
├── CLAUDE.md            # contexto para Cowork / Claude Code
├── ARCHITECTURE.md      # decisões de arquitetura
├── README.md
├── requirements.txt
├── .env.example         # copie para .env e coloque a chave
├── .gitignore
├── docs/
│   └── roadmap.md       # as duas sprints
├── scripts/
│   └── test_gemini.py   # teste rápido da API (chat + embeddings)
├── src/
│   ├── config.py        # carrega variáveis do .env
│   ├── embeddings.py    # wrapper de embeddings (Gemini)
│   ├── llm.py           # wrapper de chat (Gemini)
│   ├── db.py            # conexão + schema do pgvector  [TODO sprint 2]
│   ├── ingest.py        # vault do Obsidian -> embeddings -> banco  [TODO sprint 2]
│   └── query.py         # RAG: busca + resposta  [TODO sprint 2]
└── data/                # espaço de trabalho local (ou aponte para o vault)
```

## Como começar

```powershell
# ambiente virtual
python -m venv venv
venv\Scripts\activate

# dependências
pip install -r requirements.txt

# chave: copie o exemplo e cole sua chave do Google AI Studio
copy .env.example .env
notepad .env

# testar se a API responde
python scripts\test_gemini.py
```

Se o teste passar, o próximo passo é a Sprint 2 — passo a passo em [`docs/next-steps.md`](docs/next-steps.md).

## Segurança

A chave de API **nunca** vai no código nem no Git — só no `.env` (já ignorado pelo Git).