import json
from dataclasses import dataclass
from typing import Any

from smart_agent.config import settings


@dataclass
class LLMResponse:
    text: str
    parsed: dict[str, Any] | None = None
    tokens_used: int = 0


class BedrockLLMClient:
    def __init__(self):
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            config=Config(read_timeout=300, connect_timeout=10),
        )

    def call_flash(
        self,
        prompt: str,
        *,
        response_schema: type | None = None,
        temperature: float = 0.2,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        return self._call(
            model=settings.bedrock_light_model,
            prompt=prompt,
            response_schema=response_schema,
            temperature=temperature,
            system_instruction=system_instruction,
        )

    def call_pro(
        self,
        prompt: str,
        *,
        response_schema: type | None = None,
        temperature: float = 0.4,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        return self._call(
            model=settings.bedrock_heavy_model,
            prompt=prompt,
            response_schema=response_schema,
            temperature=temperature,
            system_instruction=system_instruction,
        )

    def _call(
        self,
        model: str,
        prompt: str,
        *,
        response_schema: type | None = None,
        temperature: float = 0.3,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        system_parts = []
        if system_instruction:
            system_parts.append({"text": system_instruction})

        if response_schema is not None:
            schema_instruction = (
                "You MUST respond with valid JSON only, no other text. "
                f"Follow this schema: {json.dumps(response_schema.model_json_schema())}"
            )
            system_parts.append({"text": schema_instruction})

        messages = [{"role": "user", "content": [{"text": prompt}]}]

        request_body: dict[str, Any] = {
            "messages": messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": 4096,
            },
        }

        if system_parts:
            request_body["system"] = system_parts

        response = self._client.converse(
            modelId=model,
            **request_body,
        )

        text = ""
        if response.get("output", {}).get("message", {}).get("content"):
            for block in response["output"]["message"]["content"]:
                if "text" in block:
                    text += block["text"]

        tokens_used = 0
        if response.get("usage"):
            usage = response["usage"]
            tokens_used = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)

        parsed = None
        if response_schema is not None:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                clean = text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                try:
                    parsed = json.loads(clean)
                except json.JSONDecodeError:
                    parsed = None

        return LLMResponse(text=text, parsed=parsed, tokens_used=tokens_used)


class GeminiLLMClient:
    def __init__(self):
        from google import genai

        self._client = genai.Client(api_key=settings.google_api_key)

    def call_flash(
        self,
        prompt: str,
        *,
        response_schema: type | None = None,
        temperature: float = 0.2,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        return self._call(
            model=settings.gemini_flash_model,
            prompt=prompt,
            response_schema=response_schema,
            temperature=temperature,
            system_instruction=system_instruction,
        )

    def call_pro(
        self,
        prompt: str,
        *,
        response_schema: type | None = None,
        temperature: float = 0.4,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        return self._call(
            model=settings.gemini_pro_model,
            prompt=prompt,
            response_schema=response_schema,
            temperature=temperature,
            system_instruction=system_instruction,
        )

    def _call(
        self,
        model: str,
        prompt: str,
        *,
        response_schema: type | None = None,
        temperature: float = 0.3,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        from google.genai import types

        config_kwargs: dict[str, Any] = {"temperature": temperature}

        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        config = types.GenerateContentConfig(**config_kwargs)

        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        text = response.text or ""
        tokens_used = 0
        if response.usage_metadata:
            tokens_used = response.usage_metadata.total_token_count or 0

        parsed = None
        if response_schema is not None:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None

        return LLMResponse(text=text, parsed=parsed, tokens_used=tokens_used)


def create_llm_client() -> BedrockLLMClient | GeminiLLMClient:
    if settings.llm_provider == "bedrock":
        return BedrockLLMClient()
    return GeminiLLMClient()


llm_client = create_llm_client()
