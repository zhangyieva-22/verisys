"""Optional OpenAI SDK adapter. Callers decide what leaves this boundary: discovery sends normalized
architecture and selection context; the opt-in understanding layer sends selected, redacted excerpts."""
import os

from pydantic import ConfigDict, Field, SecretStr, ValidationError
from verisys.models.base import DomainModel
from .contracts import DiscoveryError, StructuredGenerationResult
from .normalize import canonical


class OpenAIConfig(DomainModel):
    model_config = ConfigDict(frozen=True)
    model: str = Field(min_length=1, max_length=128)
    api_key: SecretStr | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_output_tokens: int = Field(default=2048, ge=128, le=8192)


class OpenAIClient:
    provider = "openai"

    def __init__(self, config: OpenAIConfig, *, sdk_client=None):
        self.config = config
        self.model = config.model
        self._sdk_client = sdk_client

    def generate(self, *, instructions, structured_input, response_schema):
        key = self.config.api_key.get_secret_value() if self.config.api_key else os.getenv("OPENAI_API_KEY")
        if not key and self._sdk_client is None:
            raise DiscoveryError("configuration_missing_api_key")
        try:
            import openai
        except ImportError:
            raise DiscoveryError("configuration_missing_sdk") from None
        client = self._sdk_client or openai.OpenAI(api_key=key, timeout=self.config.timeout_seconds, max_retries=0)
        try:
            raw = client.responses.with_raw_response.parse(
                model=self.model, text_format=response_schema,
                input=[{"role": "developer", "content": instructions},
                       {"role": "user", "content": canonical(structured_input.model_dump(mode="json"))}],
                tools=[], store=False, truncation="disabled",
                max_output_tokens=self.config.max_output_tokens,
                timeout=self.config.timeout_seconds,
            )
            # Inspect transport status before SDK parsing: incomplete JSON may not
            # parse, but must remain an incomplete response rather than bad selection.
            envelope = raw.http_response.json()
            usage = envelope.get("usage") or {}
            metadata = dict(request_id=raw.headers.get("x-request-id"),
                            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))
            if any(content.get("type") == "refusal"
                   for item in envelope.get("output", []) for content in item.get("content", [])):
                return StructuredGenerationResult(status="REFUSED", **metadata)
            if envelope.get("status") != "completed":
                return StructuredGenerationResult(status="INCOMPLETE", **metadata)
            response = raw.parse()
            if response.output_parsed is None:
                return StructuredGenerationResult(status="INVALID", **metadata)
            return StructuredGenerationResult(payload=response.output_parsed.model_dump(mode="json"), **metadata)
        except openai.APITimeoutError:
            raise DiscoveryError("provider_timeout") from None
        except openai.APIError:
            raise DiscoveryError("provider_unavailable") from None
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise DiscoveryError("invalid_structured_output") from None
        finally:
            if self._sdk_client is None:
                client.close()
