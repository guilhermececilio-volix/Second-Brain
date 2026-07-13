# 🧠 Colinha — Second Brain (reunião)

> Ordem de fala: **o que é → o problema → a sacada → o nome disso (RAG) → o que roda por baixo**.
> Regra de ouro: **analogia primeiro, termo técnico depois.**

---

## 1. O que é (abertura, 1 frase)

> "É um assistente que **leu todas as minhas anotações** do Obsidian. Eu pergunto e ele responde com base no que eu escrevi; eu falo um pensamento novo e ele organiza e guarda."

- Chat único (tipo WhatsApp): o sistema sozinho entende se é **pergunta** ou **anotação**.
- O "cérebro" é o **Gemini** (IA do Google).

---

## 2. O problema (por que não é só "jogar no ChatGPT")

> "A IA é inteligente, mas ela **nunca viu o meu caderno**. Se eu perguntar 'o que anotei sobre o projeto X?', ela não faz ideia."

**Analogia do advogado:** advogado brilhante, mas que acabou de chegar no caso. Sabe de leis, não conhece os *meus* documentos. Solução: **separo as páginas certas** e entrego junto com a pergunta.

---

## 3. A sacada — como ele "acha as páginas certas"

> "Ele não procura **palavras iguais** (Ctrl+F). Ele procura **significado parecido**."

**Analogia da batalha naval** 🚢 *(a que mais funciona)*:
- Batalha naval localiza algo com **2 coordenadas** (letra + número).
- Aqui cada texto vira um endereço com **768 coordenadas** — um "tabuleiro" de 768 eixos.
- O que importa é a **distância**: perto = mesmo assunto, longe = assuntos diferentes.
- Por isso acha "produtividade" mesmo eu perguntando "como ser mais focado". Palavras diferentes, endereços próximos.

> Ancorar o termo: **"esse endereço de 768 números chama-se _embedding_."**

- Os 768 não têm nada de mágico — é só o tamanho que o modelo do Google (`gemini-embedding-001`) produz.

---

## 4. O nome disso tudo: **RAG**

> "Esse caminho todo — achar os trechos certos e deixar a IA responder com base neles — tem um nome: **RAG** (Retrieval-Augmented Generation)."

| | O que é | Quem faz |
|---|---|---|
| **R** — achar | busca pela batalha naval (embeddings) | Gemini vira os números + **pgvector** compara |
| **A** — aumentar | cola os trechos achados junto da pergunta | o código monta o prompt |
| **G** — gerar | escreve a resposta em texto | **Gemini** |

Frase de fechamento:
> "**RAG = achar (busca semântica) + a IA respondendo com base no que achou.** Por isso a resposta vem sempre das minhas notas, citando a fonte — e se não estiver nas notas, ele avisa, não inventa."

⚠️ **Se perguntarem:** os 768 números **não são o RAG** — são a régua que o **R** usa pra medir proximidade. O **Gemini aparece 2x** (uma pra fazer os números no R, outra pra escrever no G). Não é erro no diagrama, são papéis diferentes.

---

## 5. O que roda por baixo (só se for público técnico / perguntarem)

| Peça | Papel |
|---|---|
| **Next.js + React** | a tela (frontend) |
| **FastAPI + Uvicorn** | a recepção que coordena (backend) |
| **Gemini** (`google-genai`) | decide, faz embeddings e escreve respostas |
| **pgvector + PostgreSQL** | o "mapa de significados" — busca por proximidade |
| **Docker** | o porão onde o banco roda escondido (não entra no caminho da mensagem) |
| **Obsidian** | dono das notas de verdade; app só cria em `Capturas/` e adiciona links |

- Regra de arquitetura: **cada dependência externa tem 1 módulo só** — trocar Gemini ou banco = mexer em 1 arquivo.
- Escrita no vault é **append-only**: nunca reescreve/apaga o que você já tinha, só adiciona `[[links]]`.

---

## 6. Perguntas prováveis (respostas de bolso)

- **"E se a resposta não estiver nas notas?"** → Ele avisa que não sabe. Não inventa (o prompt força responder só com o contexto).
- **"Meus dados vão pra nuvem?"** → As notas ficam no seu PC (Obsidian + banco no Docker local). Só o texto necessário vai ao Gemini pra gerar a resposta.
- **"Por que não usar busca normal por palavra-chave?"** → Perde sinônimos e ideias parecidas. A busca por significado acha mesmo com palavras diferentes.
- **"Isso escala pra várias pessoas?"** → MVP é single-user; multiusuário está no roadmap.
- **"Por que 768?"** → É o tamanho do embedding do modelo do Google. Poderia ser outro; é equilíbrio entre precisão e velocidade.

---

*Guia visual completo (fluxograma): o artifact "arquitetura" no Claude.*
