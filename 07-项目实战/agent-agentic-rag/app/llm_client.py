from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _parse_bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class LLMClient:
    """
    OpenAI 兼容 API 客户端。

    使用 urllib.request 直接调用，不依赖 openai SDK。
    与项目中其他 Agent 项目保持一致的实现方式。
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        gemini_project: str = "",
        gemini_location: str = "global",
        gemini_credentials_path: str = "",
        ssl_verify: bool | None = None,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.gemini_project = gemini_project
        self.gemini_location = gemini_location
        self.gemini_credentials_path = gemini_credentials_path
        if ssl_verify is None:
            ssl_verify = _parse_bool_env(os.getenv("SSL_VERIFY"), default=False)
        self.ssl_verify = ssl_verify
        self._call_count = 0
        self._gemini_credentials = None

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> str:
        """生成文本回复。"""
        if self.provider == "gemini_vertex":
            return self._generate_gemini(messages)

        return self._generate_openai(messages, temperature=temperature, max_tokens=max_tokens)

    def _generate_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        self._log_request(payload=payload)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=60, context=self._build_ssl_context()) as resp:
            raw_body = resp.read().decode("utf-8")
            self._log_response(body=raw_body)
            result = json.loads(raw_body)

        self._call_count += 1
        content = result["choices"][0]["message"]["content"].strip()
        logger.debug("LLM 响应 (%d 字符): %s...", len(content), content[:100])
        return content

    def _generate_gemini(self, messages: List[Dict[str, str]]) -> str:
        url = self._build_gemini_url()
        payload = self._build_gemini_payload(messages)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._fetch_gemini_access_token()}",
        }

        self._log_request(payload=payload)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=300, context=self._build_ssl_context()) as resp:
                body = resp.read().decode("utf-8")
                self._log_response(body=body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            self._log_response(body=error_body, is_error=True)
            raise RuntimeError(f"Gemini API returned HTTP {e.code}: {error_body}") from e

        self._call_count += 1
        content = self._extract_gemini_text(body)
        logger.debug("Gemini 响应 (%d 字符): %s...", len(content), content[:100])
        return content

    def _build_gemini_url(self) -> str:
        if not self.gemini_project:
            raise ValueError("使用 Gemini Vertex 时必须配置 GEMINI_PROJECT")
        if self.gemini_location == "global":
            return (
                "https://aiplatform.googleapis.com/v1/projects/"
                f"{self.gemini_project}/locations/global/publishers/google/models/{self.model}:generateContent"
            )
        return (
            f"https://{self.gemini_location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.gemini_project}/locations/{self.gemini_location}/publishers/google/models/{self.model}:generateContent"
        )

    def _build_gemini_payload(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        system_prompt = ""
        contents: List[Dict[str, Any]] = []

        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "system":
                system_prompt = f"{system_prompt}\n{content}".strip() if system_prompt else content
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})

        payload: Dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": ""}]}]}
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    def _extract_gemini_text(self, response_body: str) -> str:
        result = json.loads(response_body)
        for candidate in result.get("candidates", []):
            content = candidate.get("content", {})
            text_parts = []
            for part in content.get("parts", []):
                text = part.get("text")
                if text and text.strip():
                    text_parts.append(text)
            if text_parts:
                return "".join(text_parts).strip()

        feedback = result.get("promptFeedback", {})
        block_msg = feedback.get("blockReasonMessage") or "No text generated"
        raise RuntimeError(f"Gemini Chat returned no text: {block_msg}")

    def _fetch_gemini_access_token(self) -> str:
        credentials = self._load_gemini_credentials()
        if not getattr(credentials, "valid", False):
            request = self._build_google_auth_request()
            credentials.refresh(request)
        token = getattr(credentials, "token", None)
        if not token:
            raise RuntimeError("无法获取 Gemini access token")
        return token

    def _load_gemini_credentials(self):
        if self._gemini_credentials is not None:
            return self._gemini_credentials

        scope = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials_path = self.gemini_credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

        try:
            if credentials_path:
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=scope,
                )
            else:
                import google.auth

                credentials, _ = google.auth.default(scopes=scope)
        except ImportError as e:
            raise RuntimeError("缺少 google-auth 依赖，请先安装 requirements.txt") from e

        self._gemini_credentials = credentials
        return credentials

    def _build_google_auth_request(self):
        try:
            from google.auth.transport.requests import Request
        except ImportError as e:
            raise RuntimeError("缺少 google-auth 依赖，请先安装 requirements.txt") from e
        return Request()

    def _build_ssl_context(self):
        if self.ssl_verify:
            return None
        logger.warning("SSL certificate verification is disabled for LLM requests")
        return ssl._create_unverified_context()

    def _log_request(self, payload: Dict[str, Any]) -> None:
        logger.debug(
            "LLM_REQUEST %s",
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

    def _log_response(self, body: str, is_error: bool = False) -> None:
        logger.debug(
            "LLM_RESPONSE %s",
            json.dumps(
                {"is_error": is_error, "body": body},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
    ) -> Dict[str, Any]:
        """生成 JSON 格式回复，自动解析。"""
        content = self.generate(messages, temperature=temperature)

        # 尝试提取 JSON（处理 markdown code block 包裹的情况）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        return json.loads(content)
