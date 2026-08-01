"""
A LangChain-compatible ChatModel that routes every call through
generation.gemini_client.generate() instead of instantiating
langchain_google_genai.ChatGoogleGenerativeAI directly.

Why this exists: RAGAS's LLM-judge (used to score faithfulness,
answer_relevancy, context_precision, context_recall) needs a LangChain
BaseChatModel. If we handed it a raw ChatGoogleGenerativeAI, RAGAS's judge
calls would completely bypass this project's free-tier guardrails --
ALLOWED_MODELS (the model whitelist) and the capped 429 backoff in
generation/gemini_client.py. Wrapping generate() instead means judge calls
get the exact same protections as the answer-generation path (Stage 5).
Never swap this out for ChatGoogleGenerativeAI for this project.
"""
from typing import Any, List, Optional

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from generation.gemini_client import DEFAULT_MODEL, generate


class WhitelistedGeminiChatModel(BaseChatModel):
    """model must be one of generation.gemini_client.ALLOWED_MODELS --
    generate() enforces this and raises DisallowedModelError otherwise, so
    there's no separate check needed here."""

    model: str = DEFAULT_MODEL

    @property
    def _llm_type(self) -> str:
        return "whitelisted-gemini"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # RAGAS sends a single-turn prompt per judge call (system + human
        # turn, no multi-turn back-and-forth) -- flattening to plain text is
        # safe here and matches what generate() expects (a string, not a
        # LangChain message list). If RAGAS ever sends genuine multi-turn
        # conversations through this model, this flattening would need to
        # become role-aware instead.
        prompt = "\n\n".join(
            m.content for m in messages if isinstance(m.content, str)
        )
        response = generate(self.model, prompt)
        message = AIMessage(content=response.text)
        return ChatResult(generations=[ChatGeneration(message=message)])
