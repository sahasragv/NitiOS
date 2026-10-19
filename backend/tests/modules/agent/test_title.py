"""Tests for conversation title generation."""

from __future__ import annotations

import unittest

from app.modules.agent.application.title import ConversationTitleService
from app.modules.llm.domain.models import LLMMessage, LLMResponse
from app.modules.llm.gateway.generation import LLMGateway
from tests.modules.agent.test_chat import ScriptedProvider


class FakeGenerateProvider(ScriptedProvider):
    """Serve non-streaming responses for the title use case."""

    async def generate(self, request):  # type: ignore[override]
        self.requests.append(request)
        return self.responses.pop(0)


def _response(content: str, finish_reason: str = "stop") -> LLMResponse:
    return LLMResponse(content=content, provider="scripted", model="test", finish_reason=finish_reason)


class ConversationTitleServiceTests(unittest.IsolatedAsyncioTestCase):
    """Verify prompting and cleanup of model-written titles."""

    async def test_returns_cleaned_model_title(self) -> None:
        provider = FakeGenerateProvider([_response('Title: "Booking Train Tickets in Telugu."\nExtra line')])
        title = await ConversationTitleService(LLMGateway(provider)).suggest_title("say how to book a train ticket in telugu")
        self.assertEqual(title, "Booking Train Tickets in Telugu")
        request = provider.requests[0]
        self.assertEqual(request.tools, [])
        self.assertEqual(request.generation.max_tokens, 64)
        self.assertIsInstance(request.messages[0], LLMMessage)

    async def test_falls_back_to_message_when_model_returns_nothing(self) -> None:
        provider = FakeGenerateProvider([_response("  ")])
        self.assertEqual(await ConversationTitleService(LLMGateway(provider)).suggest_title("hi there"), "hi there")

    def test_clean_caps_length_on_a_word_boundary(self) -> None:
        title = ConversationTitleService.clean("A very long title that keeps going well past the sixty character limit set")
        self.assertLessEqual(len(title), 60)
        self.assertTrue(title.endswith("…"))

    async def test_truncated_title_drops_partial_word(self) -> None:
        provider = FakeGenerateProvider([_response("తెలుగులో రైల్వే ట", finish_reason="length")])
        title = await ConversationTitleService(LLMGateway(provider)).suggest_title("telugu train ticket")
        self.assertEqual(title, "తెలుగులో రైల్వే")
