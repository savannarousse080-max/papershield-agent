import json
import io
import os
import unittest
import urllib.error
from unittest.mock import patch

from agent.llm import LLMSettings, MockLLMClient, OpenAICompatibleClient, ProviderConfigError, settings_from_env


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


class LLMTests(unittest.TestCase):
    def test_mock_provider_does_not_inject_fixed_opening_sentence(self):
        client = MockLLMClient()

        result = client.complete([{"role": "user", "content": "请润色以下段落：\n\n此外，数据安全问题需要完善[1]。"}])

        self.assertNotIn("问题并不轻", result)
        self.assertIn("[1]", result)
        self.assertIn("数据安全", result)

    def test_mock_provider_strips_prompt_draft_markers(self):
        client = MockLLMClient()

        result = client.complete([
            {
                "role": "user",
                "content": "请润色以下段落：\n\nBEGIN_DRAFT\n此外，数据安全问题需要完善[1]。\nEND_DRAFT",
            }
        ])

        self.assertNotIn("BEGIN_DRAFT", result)
        self.assertNotIn("END_DRAFT", result)
        self.assertIn("[1]", result)

    def test_openai_compatible_client_retries_transient_url_error(self):
        settings = LLMSettings(provider="openai", model="demo", api_key="key", max_retries=1)
        client = OpenAICompatibleClient(settings)
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request, timeout))
            if len(calls) == 1:
                raise urllib.error.URLError("temporary network issue")
            return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.complete([{"role": "user", "content": "hello"}])

        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    def test_openai_compatible_client_retries_transient_http_503(self):
        settings = LLMSettings(provider="openai", model="demo", api_key="key", max_retries=1)
        client = OpenAICompatibleClient(settings)
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request, timeout))
            if len(calls) == 1:
                body = b'{"error":{"code":503,"message":"high demand","status":"UNAVAILABLE"}}'
                raise urllib.error.HTTPError(
                    request.full_url,
                    503,
                    "Service Unavailable",
                    hdrs=None,
                    fp=io.BytesIO(body),
                )
            return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.complete([{"role": "user", "content": "hello"}])

        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    def test_openai_compatible_client_rejects_unsafe_base_url(self):
        unsafe_urls = [
            "http://api.example.com/v1",
            "https://127.0.0.1:9",
            "https://localhost:8000",
            "file:///tmp/provider",
        ]

        for base_url in unsafe_urls:
            with self.subTest(base_url=base_url):
                settings = LLMSettings(provider="openai", model="demo", base_url=base_url, api_key="key")
                with self.assertRaises(ProviderConfigError):
                    OpenAICompatibleClient(settings)

    def test_settings_from_env_reads_timeout_and_retry_values(self):
        env = {
            "PAPERSHIELD_LLM_PROVIDER": "mock",
            "PAPERSHIELD_LLM_TIMEOUT": "12",
            "PAPERSHIELD_LLM_MAX_RETRIES": "3",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = settings_from_env()

        self.assertEqual(settings.timeout, 12)
        self.assertEqual(settings.max_retries, 3)
        self.assertEqual(settings.model, "mock")


if __name__ == "__main__":
    unittest.main()
