"""Thin HTTP controller for provider-neutral LLM generation."""

from fastapi import APIRouter, Depends, Header

from app.api.v1.llm.dependencies import get_llm_generation_service
from app.api.v1.llm.schemas import GenerateRequestDTO, GenerateResponseDTO, UsageDTO
from app.common.responses import ResponseMeta, SuccessResponse
from app.modules.llm.application.generation import GenerateLLMCommand, LLMGenerationService
from app.modules.llm.domain.models import GenerationConfig, LLMCapability, LLMMessage, ResponseFormat


router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


@router.post("/generate", response_model=SuccessResponse[GenerateResponseDTO])
async def generate(
    body: GenerateRequestDTO,
    service: LLMGenerationService = Depends(get_llm_generation_service),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> SuccessResponse[GenerateResponseDTO]:
    """Delegate a generation use case to the application service."""
    result = await service.generate(
        GenerateLLMCommand(
            capability=LLMCapability(body.capability),
            messages=[LLMMessage(**message.model_dump()) for message in body.messages],
            generation=GenerationConfig(**body.generation.model_dump()) if body.generation else GenerationConfig(),
            response_format=ResponseFormat(**body.response_format.model_dump()) if body.response_format else ResponseFormat(),
            request_id=request_id,
        )
    )
    return SuccessResponse(
        message="LLM generation completed.",
        data=GenerateResponseDTO(
            content=result.content,
            finish_reason=result.finish_reason,
            usage=UsageDTO(**result.usage.model_dump()),
            request_id=result.request_id,
        ),
        meta=ResponseMeta(request_id=result.request_id, version="v1"),
    )
