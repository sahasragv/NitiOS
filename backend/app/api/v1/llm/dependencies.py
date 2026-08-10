"""FastAPI dependencies for LLM application services."""

from fastapi import Request

from app.modules.llm.application.generation import LLMGenerationService


def get_llm_generation_service(request: Request) -> LLMGenerationService:
    """Resolve the lifespan-managed generation service from application state."""
    return request.app.state.llm_generation_service
