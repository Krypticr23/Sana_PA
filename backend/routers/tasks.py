from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_tasks():
    # TODO: Google Tasks / Notion integration (Week 3)
    return {"message": "Tasks integration coming in Week 3"}
