from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routers import chat, calendar, tasks, health

app = FastAPI(
    title="SANA - Personal AI Agent",
    description="Your private PA running on Jetson Orin Nano",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
