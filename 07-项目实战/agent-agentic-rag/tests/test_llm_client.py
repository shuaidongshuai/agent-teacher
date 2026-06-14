from __future__ import annotations

import json
import unittest

from app.llm_client import LLMClient


class GeminiClientHelpersTest(unittest.TestCase):
    def test_build_gemini_payload_from_messages(self) -> None:
        client = LLMClient(
            provider="gemini_vertex",
            model="gemini-2.5-flash",
            gemini_project="demo-project",
            gemini_location="global",
        )

        payload = client._build_gemini_payload(
            [
                {"role": "system", "content": "你是助手"},
                {"role": "user", "content": "你好"},
            ]
        )

        self.assertEqual(
            payload["system_instruction"]["parts"][0]["text"],
            "你是助手",
        )
        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "你好")

    def test_extract_gemini_text(self) -> None:
        client = LLMClient(
            provider="gemini_vertex",
            model="gemini-2.5-flash",
            gemini_project="demo-project",
            gemini_location="global",
        )

        response = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "第一段"},
                                {"text": "第二段"},
                            ]
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )

        self.assertEqual(client._extract_gemini_text(response), "第一段第二段")


if __name__ == "__main__":
    unittest.main()
