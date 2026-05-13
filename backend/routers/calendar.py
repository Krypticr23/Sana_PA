from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_events():
    # TODO: Google Calendar integration (Week 3)
    return {"message": "Calendar integration coming in Week 3"}
