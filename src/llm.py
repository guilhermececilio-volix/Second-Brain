"""
Wrapper de chat (LLM) do Gemini.

Isola o SDK google-genai do resto do projeto: se um dia trocarmos de
provedor (OpenAI, Anthropic, modelo local), só este arquivo muda.

Uso:
    from src.llm import GeminiLLM

    llm = GeminiLLM()
    print(llm.ask("O que é um second brain?"))

    # Ou com histórico (conversa):
    chat = llm.start_chat()
    chat.send("Oi, meu nome é Gui.")
    chat.send("Qual é o meu nome?")  # ele lembra
"""

from google import genai

from src.config import settings


class ChatSession:
    """Conversa com histórico mantido pelo SDK."""

    def __init__(self, client: genai.Client, model: str):
        self._chat = client.chats.create(model=model)

    def send(self, message: str) -> str:
        """Envia uma mensagem e retorna o texto da resposta."""
        resp = self._chat.send_message(message)
        return (resp.text or "").strip()


class GeminiLLM:
    """Cliente de chat do Gemini com a configuração do projeto."""

    def __init__(self, model: str | None = None):
        self.model = model or settings.chat_model
        self._client = genai.Client(api_key=settings.require_api_key())

    def ask(self, prompt: str, system: str | None = None) -> str:
        """Pergunta única, sem histórico. Opcionalmente com instrução de sistema."""
        config = None
        if system:
            config = genai.types.GenerateContentConfig(system_instruction=system)
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return (resp.text or "").strip()

    def start_chat(self) -> ChatSession:
        """Inicia uma conversa com memória de contexto."""
        return ChatSession(self._client, self.model)
