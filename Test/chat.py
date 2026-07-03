"""
Chat interativo com o Gemini.
Rode no terminal:  python chat.py
Digite suas mensagens. Para sair: 'sair', 'exit' ou Ctrl+C.
O histórico é mantido, entao o modelo lembra do que voce falou antes.
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("Defina GEMINI_API_KEY no arquivo .env antes de rodar.")

client = genai.Client(api_key=api_key)
chat = client.chats.create(model="gemini-2.5-flash")

print("Chat com Gemini (2.5-flash). Digite 'sair' para encerrar.\n")

while True:
    try:
        msg = input("Voce: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAte mais!")
        break

    if not msg:
        continue
    if msg.lower() in ("sair", "exit", "quit"):
        print("Ate mais!")
        break

    resp = chat.send_message(msg)
    print(f"\nGemini: {resp.text.strip()}\n")
