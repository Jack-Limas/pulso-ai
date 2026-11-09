import json
from typing import Any, Protocol

from google import genai
from google.genai import types


class LanguageModel(Protocol):
    def generate_json(self, prompt: str) -> Any: ...


class GeminiModel:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate_json(self, prompt: str) -> Any:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text or "null")
