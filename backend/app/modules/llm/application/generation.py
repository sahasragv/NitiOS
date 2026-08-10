"""Application service for the LLM generation use case."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.exceptions.base import BaseApplicationException
from app.modules.llm.domain.models import GenerationConfig, LLMCapability, LLMMessage, ResponseFormat
from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError
from app.modules.llm.gateway.generation import LLMGateway, LLMGatewayRequestError
from app.modules.llm.domain.models import LLMRequest, LLMUsage, RequestMetadata


class GenerateLLMCommand(BaseModel):
    """Application input for a single provider-neutral generation operation."""

    capability: LLMCapability
    messages: list[LLMMessage] = Field(min_length=1)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    response_format: ResponseFormat = Field(default_factory=ResponseFormat)
    request_id: str | None = None


class GenerateLLMResult(BaseModel):
    """Application result deliberately excluding provider and model selection details."""

    content: str | None = None
    finish_reason: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    request_id: str


class LLMGenerationRequestError(BaseApplicationException):
    """Expected failure caused by an invalid generation use-case input."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="LLM_GENERATION_REQUEST_INVALID", status_code=422)


class LLMGenerationFailedError(BaseApplicationException):
    """Expected failure while executing generation through the gateway."""

    def __init__(self) -> None:
        super().__init__("LLM generation is currently unavailable.", error_code="LLM_GENERATION_FAILED", status_code=502)


class LLMGenerationService:
    """Orchestrate a generation request without exposing provider implementation details."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway
        self._logger = get_logger(__name__)

    async def generate(self, command: GenerateLLMCommand) -> GenerateLLMResult:
        """Construct the domain request, execute it, and map its public application result."""
        request_id = command.request_id or str(uuid4())
        started_at = perf_counter()
        try:
            response = await self._gateway.generate(
                LLMRequest(
                    capability=command.capability,
                    messages=command.messages,
                    generation=command.generation,
                    response_format=command.response_format,
                    metadata=RequestMetadata(request_id=request_id),
                )
            )
            self._log_outcome(request_id, command.capability, (perf_counter() - started_at) * 1000, success=True)
            return GenerateLLMResult(
                content=response.content,
                finish_reason=response.finish_reason,
                usage=response.usage,
                request_id=request_id,
            )
        except LLMGatewayRequestError as error:
            self._log_outcome(request_id, command.capability, (perf_counter() - started_at) * 1000, success=False)
            raise LLMGenerationRequestError(str(error)) from error
        except LLMProviderInfrastructureError as error:
            self._log_outcome(request_id, command.capability, (perf_counter() - started_at) * 1000, success=False)
            raise LLMGenerationFailedError() from error

    def _log_outcome(self, request_id: str, capability: LLMCapability, latency_ms: float, *, success: bool) -> None:
        """Log safe service telemetry without request inputs or generated content."""
        (self._logger.info if success else self._logger.error)(
            "LLM generation service completed" if success else "LLM generation service failed",
            extra={"request_id": request_id, "capability": capability.value, "latency_ms": round(latency_ms, 2), "success": success},
        )
