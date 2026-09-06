"""
Thin wrapper so the rest of the harness can call any of the three providers
through one interface: client.send(messages) -> str.

messages is a plain list of {"role": "user"|"assistant", "content": str} dicts,
carried across turns so each provider sees the full conversation, including
your earlier code and the test-failure feedback you fed back to it.

Install what you need:
    pip install openai anthropic google-genai
"""

import os
from harness.config import ModelConfig

# Shared across all three providers so the token budget doesn't confound the
# model comparison. Generous enough that a reasoning model (e.g. gpt-5) can
# spend tokens on hidden reasoning and still have room left to emit code --
# 4096 was observed to let GPT-5 exhaust the entire budget on reasoning for
# a hard task, returning zero characters of actual output.
MAX_OUTPUT_TOKENS = 16000


class ModelClient:
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg
        api_key = os.environ.get(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing API key for {cfg.name}: set env var {cfg.api_key_env}"
            )
        self.api_key = api_key
        self._client = self._build_client()

    def _build_client(self):
        if self.cfg.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key)
        elif self.cfg.provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=self.api_key)
        elif self.cfg.provider == "google":
            from google import genai
            return genai.Client(api_key=self.api_key)
        else:
            raise ValueError(f"Unknown provider: {self.cfg.provider}")

    def send(self, messages: list[dict]) -> str:
        """messages: [{"role": "user"/"assistant", "content": "..."}], oldest first."""
        if self.cfg.provider == "openai":
            resp = self._client.chat.completions.create(
                model=self.cfg.model_id,
                messages=messages,
                max_completion_tokens=MAX_OUTPUT_TOKENS,
            )
            return resp.choices[0].message.content

        elif self.cfg.provider == "anthropic":
            # Anthropic API takes system separately; no system prompt needed here.
            resp = self._client.messages.create(
                model=self.cfg.model_id,
                max_tokens=MAX_OUTPUT_TOKENS,
                messages=messages,
            )
            return "".join(block.text for block in resp.content if block.type == "text")

        elif self.cfg.provider == "google":
            # Google GenAI SDK expects a single content string or turn history;
            # flatten messages into one alternating-turn call.
            from google.genai import types
            contents = []
            for m in messages:
                role = "user" if m["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
            resp = self._client.models.generate_content(
                model=self.cfg.model_id,
                contents=contents,
                config=types.GenerateContentConfig(max_output_tokens=MAX_OUTPUT_TOKENS),
            )
            return resp.text

        raise ValueError(f"Unknown provider: {self.cfg.provider}")
