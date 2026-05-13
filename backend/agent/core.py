import httpx
from typing import Optional
from agent.memory import MemoryManager

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

SYSTEM_PROMPT = """You are SANA, a personal AI assistant running privately on a local server.
You help the user with:
- Scheduling and calendar management
- Task and appointment planning
- General questions and planning
- Reminders and follow-ups

You are concise, efficient, and proactive. When the user mentions dates, times, or tasks,
you identify them and offer to add them to their calendar or task list.
Always respond in a helpful, natural tone.
"""


class AgentCore:
    def __init__(self):
        self.memory = MemoryManager()

    async def chat(self, user_id: str, message: str, conversation_id: Optional[str] = None) -> dict:
        history = self.memory.get_history(user_id, conversation_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OLLAMA_URL, json={
                "model": MODEL,
                "messages": messages,
                "stream": False
            })
            response.raise_for_status()
            data = response.json()

        assistant_message = data["message"]["content"]
        conv_id = self.memory.save_message(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=message,
            assistant_message=assistant_message
        )
        return {"response": assistant_message, "conversation_id": conv_id}
