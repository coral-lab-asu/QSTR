import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

try:
    from transformers import pipeline  # type: ignore
except Exception:
    pipeline = None  # type: ignore


@dataclass
class InferenceConfig:
    provider: str
    model: str
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 20000
    request_timeout_s: float = 120.0
    log_dir: Optional[str] = "logs"
    run_id: Optional[str] = None


@dataclass
class InferenceResponse:
    text: str
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None
    error: Optional[str] = None


class InferenceService:
    def __init__(self, config: InferenceConfig):
        self.config = config
        self.provider = (config.provider or "").lower().strip()
        self.client = self._build_client()
        self._counter = 0
        self._log_root = self._init_log_dir(config.log_dir, config.run_id)

    def _init_log_dir(self, log_dir: Optional[str], run_id: Optional[str]) -> Optional[str]:
        if not log_dir:
            return None
        rid = run_id or time.strftime("run_%Y%m%d_%H%M%S")
        root = os.path.join(log_dir, rid)
        os.makedirs(root, exist_ok=True)
        return root

    def _build_client(self):
        api_key = self._resolve_api_key()
        base_url = self._resolve_base_url()

        if self.provider in ("google", "gemini", "google_genai", "genai"):
            if genai is None:
                raise RuntimeError("google-generativeai not installed")
            if not api_key:
                raise RuntimeError("Missing GEMINI_API_KEY or --api-key for Gemini provider")
            genai.configure(api_key=api_key)
            return genai.GenerativeModel(self.config.model)

        if self.provider in ("openai", "openai_compat", "deepinfra", "deep-infra"):
            if OpenAI is None:
                raise RuntimeError("openai not installed")
            if not api_key:
                raise RuntimeError("Missing API key for OpenAI-compatible provider")
            return OpenAI(api_key=api_key, base_url=base_url)

        if self.provider in ("local", "hf", "transformers"):
            if pipeline is None:
                raise RuntimeError("transformers not installed")
            return pipeline("text-generation", model=self.config.model)

        raise ValueError(f"Unknown provider: {self.provider}")

    def _resolve_api_key(self) -> str:
        explicit = (self.config.api_key or "").strip()
        if explicit:
            return explicit

        if self.provider in ("google", "gemini", "google_genai", "genai"):
            return os.getenv("GEMINI_API_KEY", "").strip()
        if self.provider in ("deepinfra", "deep-infra"):
            return os.getenv("DEEPINFRA_API_KEY", "").strip()
        if self.provider in ("openai", "openai_compat"):
            return os.getenv("OPENAI_API_KEY", "").strip()
        return ""

    def _resolve_base_url(self) -> Optional[str]:
        if self.provider in ("google", "gemini", "google_genai", "genai"):
            return None
        base_url = (self.config.base_url or "").strip()
        return base_url or None

    def _safe_id(self, sample_id: str) -> str:
        s = (sample_id or "").strip() or f"sample_{self._counter}"
        s = s.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return s

    def _log_sample(self, sample_id: str, record: Dict[str, Any]) -> None:
        if not self._log_root:
            return
        sid = self._safe_id(sample_id)
        path = os.path.join(self._log_root, f"{sid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

    def _stringify_gemini_attr(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
        try:
            return str(value)
        except Exception:
            return repr(value)

    def _gemini_response_metadata(self, resp: Any) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}

        prompt_feedback = getattr(resp, "prompt_feedback", None)
        if prompt_feedback is not None:
            meta["prompt_feedback"] = self._stringify_gemini_attr(prompt_feedback)

        usage_meta = getattr(resp, "usage_metadata", None)
        if usage_meta is not None:
            meta["usage_metadata"] = {
                "prompt_token_count": getattr(usage_meta, "prompt_token_count", None),
                "candidates_token_count": getattr(usage_meta, "candidates_token_count", None),
                "total_token_count": getattr(usage_meta, "total_token_count", None),
            }

        candidates_meta = []
        for idx, candidate in enumerate(getattr(resp, "candidates", None) or []):
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            part_types = []
            for part in parts:
                if getattr(part, "text", None) is not None:
                    part_types.append("text")
                else:
                    part_types.append(type(part).__name__)

            candidates_meta.append(
                {
                    "index": idx,
                    "finish_reason": self._stringify_gemini_attr(getattr(candidate, "finish_reason", None)),
                    "finish_message": getattr(candidate, "finish_message", None),
                    "safety_ratings": self._stringify_gemini_attr(getattr(candidate, "safety_ratings", None)),
                    "citation_metadata": self._stringify_gemini_attr(getattr(candidate, "citation_metadata", None)),
                    "part_types": part_types,
                    "text_part_count": sum(1 for part in parts if getattr(part, "text", None) is not None),
                }
            )

        if candidates_meta:
            meta["candidates"] = candidates_meta

        return meta

    def _extract_gemini_text(self, resp: Any) -> Tuple[str, Optional[str]]:
        accessor_error: Optional[str] = None
        try:
            text = resp.text if hasattr(resp, "text") else ""
            if isinstance(text, str) and text.strip():
                return text, None
        except Exception as exc:
            accessor_error = f"{type(exc).__name__}: {exc}"

        text_parts = []
        for candidate in getattr(resp, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            candidate_parts = []
            for part in parts:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text:
                    candidate_parts.append(part_text)
            if candidate_parts:
                text_parts.append("".join(candidate_parts))

        if text_parts:
            return "\n".join(text_parts), accessor_error

        if accessor_error:
            return "", accessor_error
        return "", "Gemini response did not contain any text parts."

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        sample_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InferenceResponse:
        temp = self.config.temperature if temperature is None else temperature
        max_toks = self.config.max_tokens if max_tokens is None else max_tokens
        usage: Dict[str, Any] = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        sample_key = sample_id or f"sample_{self._counter}"
        self._counter += 1
        provider_response_metadata: Dict[str, Any] = {}
        try:
            if self.provider in ("google", "gemini", "google_genai", "genai"):
                stitched = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"
                resp = self.client.generate_content(
                    stitched,
                    generation_config={
                        "temperature": temp,
                        "max_output_tokens": max_toks,
                        "response_mime_type": "application/json",
                    },
                )
                provider_response_metadata = self._gemini_response_metadata(resp)
                text, text_warning = self._extract_gemini_text(resp)
                try:
                    meta = getattr(resp, "usage_metadata", None)
                    if meta is not None:
                        usage["input_tokens"] = getattr(meta, "prompt_token_count", None)
                        usage["output_tokens"] = getattr(meta, "candidates_token_count", None)
                        usage["total_tokens"] = getattr(meta, "total_token_count", None)
                except Exception:
                    pass
                raw = resp
                resp_obj = InferenceResponse(text=text, usage=usage, raw=raw, error=text_warning if not text else None)

            elif self.provider in ("openai", "openai_compat", "deepinfra", "deep-infra"):
                resp = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                    max_tokens=max_toks,
                    timeout=self.config.request_timeout_s,
                )
                text = resp.choices[0].message.content or ""
                try:
                    u = getattr(resp, "usage", None)
                    if u is not None:
                        usage["input_tokens"] = getattr(u, "prompt_tokens", None)
                        usage["output_tokens"] = getattr(u, "completion_tokens", None)
                        usage["total_tokens"] = getattr(u, "total_tokens", None)
                except Exception:
                    pass
                raw = resp
                resp_obj = InferenceResponse(text=text, usage=usage, raw=raw)

            elif self.provider in ("local", "hf", "transformers"):
                stitched = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"
                gen = self.client(
                    stitched,
                    max_new_tokens=max_toks,
                    temperature=temp,
                    do_sample=temp > 0,
                )
                text = gen[0]["generated_text"] if gen else ""
                raw = gen
                resp_obj = InferenceResponse(text=text, usage=usage, raw=raw)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            log_record = {
                "provider": self.provider,
                "model": self.config.model,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_text": text,
                "usage": usage,
                "metadata": metadata or {},
                "provider_response_metadata": provider_response_metadata,
                "timestamp": time.time(),
            }
            if resp_obj.error:
                log_record["error"] = resp_obj.error
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            resp_obj = InferenceResponse(text="", usage=usage, raw=None, error=error_msg)
            log_record = {
                "provider": self.provider,
                "model": self.config.model,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_text": "",
                "usage": usage,
                "metadata": metadata or {},
                "provider_response_metadata": provider_response_metadata,
                "timestamp": time.time(),
                "error": error_msg,
            }

        self._log_sample(sample_key, log_record)
        return resp_obj
