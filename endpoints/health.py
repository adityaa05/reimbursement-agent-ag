from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    return {
        "status": "running",
        "service": "Reimbursement Bot",
        "version": "1.0.0",
        "phase": "development",
    }
