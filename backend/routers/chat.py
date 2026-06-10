from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import traceback
import sqlite3
from pathlib import Path
from agent.core import AgentCore

router = APIRouter()
agent = AgentCore()

DB_PATH = Path.home() / "sana-server" / "data" / "sana.db"

class ChatRequest(BaseModel):
    message: str
    user_id: str = "krishna"
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        conv_id = request.conversation_id
        if conv_id == "string":
            conv_id = None
        result = await agent.chat(
            user_id=request.user_id,
            message=request.message,
            conversation_id=conv_id
        )
        return ChatResponse(**result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{user_id}")
async def get_conversations(user_id: str):
    return agent.memory.get_conversations(user_id)

@router.get("/history/{user_id}/{conversation_id}")
async def get_conversation(user_id: str, conversation_id: str):
    return agent.memory.get_history(user_id, conversation_id)

@router.delete("/history/{user_id}/{conversation_id}")
async def delete_conversation(user_id: str, conversation_id: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
            conn.commit()
        return {"status": "deleted", "conversation_id": conversation_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history/{user_id}")
async def delete_all_conversations(user_id: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT id FROM conversations WHERE user_id = ?", (user_id,)).fetchall()
            conv_ids = [r[0] for r in rows]
            for conv_id in conv_ids:
                conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            conn.commit()
        return {"status": "deleted_all", "count": len(conv_ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
