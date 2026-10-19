"""Application service that names a conversation from its opening exchange."""

from __future__ import annotations

import re
from uuid import uuid4

from app.modules.agent.application.chat import AgentChatFailedError
from app.modules.llm.domain.interfaces import LLMProviderInfrastructureError
from app.modules.llm.domain.models import GenerationConfig, LLMCapability, LLMMessage, LLMRequest, RequestMetadata
from app.modules.llm.gateway.generation import LLMGateway


TITLE_SYSTEM_PROMPT = (
    "You name chat conversations. Reply with a short title of 2 to 6 words that summarizes what the user wants, "
    "in the same language as the user. Reply with the title only: no quotes, no trailing punctuation, no prefix."
)
_MAX_INPUT_CHARS = 1000
# Indian scripts take several tokens per word, so leave room for six words in any language.
_MAX_TITLE_TOKENS = 64
_MAX_TITLE_CHARS = 60


class ConversationTitleService:
    """Ask the model for a concise conversation title."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def suggest_title(self, message: str, reply: str | None = None) -> str:
        """Return a cleaned 2–6 word title for a conversation that starts with ``message``."""
        prompt = f"User message:\n{message[:_MAX_INPUT_CHARS]}"
        if reply:
            prompt += f"\n\nAssistant reply (for context):\n{reply[:_MAX_INPUT_CHARS]}"
        try:
            response = await self._gateway.generate(
                LLMRequest(
                    capability=LLMCapability.SUMMARIZATION,
                    messages=[LLMMessage(role="system", content=TITLE_SYSTEM_PROMPT), LLMMessage(role="user", content=prompt)],
                    generation=GenerationConfig(temperature=0.2, max_tokens=_MAX_TITLE_TOKENS),
                    metadata=RequestMetadata(request_id=str(uuid4())),
                )
            )
        except LLMProviderInfrastructureError as error:
            raise AgentChatFailedError.from_provider_error(error) from error
        raw = response.content or ""
        if response.finish_reason == "length" and " " in raw.strip():
            # The model ran out of tokens mid-word; drop the partial last word.
            raw = raw.strip().rsplit(" ", 1)[0]
        return self.clean(raw) or self.clean(message)

    @staticmethod
    def clean(raw: str) -> str:
        """Keep the first line, strip labels, quotes and trailing punctuation, and cap the length."""
        line = next((part for part in raw.strip().splitlines() if part.strip()), "")
        line = re.sub(r"^(title|chat title)\s*[:\-]\s*", "", line.strip(), flags=re.IGNORECASE)
        line = line.strip(" \"'`*#").rstrip(" .!?:;,")
        if len(line) > _MAX_TITLE_CHARS:
            line = line[: _MAX_TITLE_CHARS - 1].rsplit(" ", 1)[0] + "…"
        return line
