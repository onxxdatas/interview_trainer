from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """Raised when Gemini fails to return usable structured output after retries."""


class GeminiClient:
    """Thin wrapper around google-genai with structured-output + validation + one repair retry."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        raw_text = await self._call(system_prompt, user_prompt, schema)
        try:
            return schema.model_validate_json(raw_text)
        except ValidationError as exc:
            logger.warning("Gemini returned invalid structured output, retrying once: %s", exc)
            repair_prompt = (
                f"{user_prompt}\n\nYour previous response was invalid JSON for the "
                f"required schema. Validation error: {exc}. Return ONLY valid JSON "
                "matching the schema, nothing else."
            )
            raw_text = await self._call(system_prompt, repair_prompt, schema)
            try:
                return schema.model_validate_json(raw_text)
            except ValidationError as exc2:
                raise GeminiClientError(f"Gemini failed to produce valid structured output: {exc2}") from exc2

    async def _call(self, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.4,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=config,
            )
        except Exception as exc:  # network/API failure
            raise GeminiClientError(f"Gemini API call failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise GeminiClientError("Gemini returned an empty response")
        return text


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
