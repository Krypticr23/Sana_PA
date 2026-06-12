from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import traceback
from agent.core import AgentCore

router = APIRouter()
agent = AgentCore()


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
    ok = agent.memory.delete_conversation(user_id, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "conversation_id": conversation_id}


@router.delete("/history/{user_id}")
async def delete_all_conversations(user_id: str):
    count = agent.memory.delete_all_conversations(user_id)
    return {"status": "deleted", "count": count}
