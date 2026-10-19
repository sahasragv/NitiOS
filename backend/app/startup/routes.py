"""Route registration for the NitiOS application."""

from fastapi import APIRouter, FastAPI

from app.api.v1.agent.router import router as agent_router
from app.api.v1.llm.router import router as llm_router


router = APIRouter()
"""Router containing platform-level routes."""


@router.get("/")
def get_service_status() -> dict[str, str]:
    """Return the service availability status."""
    return {"service": "NitiOS", "status": "running"}


def register_routes(app: FastAPI) -> None:
    """Register the platform routers on ``app``."""
    app.include_router(router)
    app.include_router(llm_router)
    app.include_router(agent_router)
