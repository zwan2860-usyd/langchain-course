import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

import main as course


class GeminiConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=True
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.dotenv = patch.object(course, "load_dotenv", return_value=False)
        self.load_dotenv = self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

    def test_explicit_adc_and_vertex_defaults(self):
        credentials = AnonymousCredentials()
        with (
            patch.object(
                course.google.auth, "default", return_value=(credentials, None)
            ) as adc,
            patch.object(course, "ChatGoogleGenerativeAI") as model,
        ):
            self.assertIs(course.build_llm(), model.return_value)
        adc.assert_called_once_with(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.load_dotenv.assert_called_once_with(
            Path(course.__file__).with_name(".env")
        )
        model.assert_called_once_with(
            model="gemini-3.8-flash",
            vertexai=True,
            project="test-project",
            location="global",
            credentials=credentials,
            api_key=None,
            temperature=0,
            max_retries=2,
        )

    def test_model_and_location_overrides(self):
        os.environ.update(GEMINI_MODEL="gemini-3.5-flash", GOOGLE_CLOUD_LOCATION="us")
        with (
            patch.object(
                course.google.auth,
                "default",
                return_value=(AnonymousCredentials(), None),
            ),
            patch.object(course, "ChatGoogleGenerativeAI") as model,
        ):
            course.build_llm()
        self.assertEqual(model.call_args.kwargs["model"], "gemini-3.5-flash")
        self.assertEqual(model.call_args.kwargs["location"], "us")

    def test_missing_project_has_actionable_error(self):
        os.environ["GOOGLE_CLOUD_PROJECT"] = " "
        with patch.object(course.google.auth, "default") as adc:
            with self.assertRaisesRegex(RuntimeError, "Set GOOGLE_CLOUD_PROJECT"):
                course.build_llm()
        adc.assert_not_called()

    def test_missing_adc_has_login_guidance(self):
        with patch.object(
            course.google.auth, "default", side_effect=DefaultCredentialsError()
        ):
            with self.assertRaisesRegex(
                RuntimeError, "gcloud auth application-default login"
            ):
                course.build_llm()

    def test_real_adapter_uses_adc_despite_environment_api_keys(self):
        credentials = AnonymousCredentials()
        os.environ.update(
            GOOGLE_API_KEY="not-a-real-key",
            GEMINI_API_KEY="also-not-a-real-key",
            GOOGLE_GENAI_USE_VERTEXAI="false",
        )
        with patch.object(
            course.google.auth, "default", return_value=(credentials, None)
        ):
            model = course.build_llm()
        try:
            self.assertTrue(model.client.vertexai)
            self.assertIs(model.client._api_client._credentials, credentials)
            self.assertIsNone(model.client._api_client.api_key)
        finally:
            model.client.close()

    def test_kimi_does_not_require_google_configuration_or_adc(self):
        os.environ.clear()
        os.environ.update(LLM_PROVIDER="kimi", MOONSHOT_API_KEY="test-only-key")
        with (
            patch.object(course.google.auth, "default") as adc,
            patch.object(course, "ChatOpenAI") as model,
            patch.object(course, "ChatGoogleGenerativeAI") as gemini,
        ):
            self.assertIs(course.build_llm(), model.return_value)
        adc.assert_not_called()
        gemini.assert_not_called()
        model.assert_called_once_with(
            model="kimi-k3",
            base_url="https://api.moonshot.cn/v1",
            api_key="test-only-key",
            use_responses_api=False,
            timeout=120,
            max_retries=2,
        )

    def test_kimi_model_override_and_provider_normalization(self):
        os.environ.update(
            LLM_PROVIDER=" KIMI ",
            MOONSHOT_API_KEY="test-only-key",
            KIMI_MODEL="kimi-k2.6",
        )
        with patch.object(course, "ChatOpenAI") as model:
            course.build_llm()
        self.assertEqual(model.call_args.kwargs["model"], "kimi-k2.6")

    def test_kimi_missing_or_placeholder_key_has_safe_error(self):
        os.environ["LLM_PROVIDER"] = "kimi"
        with (
            patch.object(course, "ChatOpenAI") as model,
            patch.object(course.google.auth, "default") as adc,
        ):
            for key in ["", " ", "your-api-key"]:
                with self.subTest(key=key):
                    os.environ["MOONSHOT_API_KEY"] = key
                    with self.assertRaisesRegex(RuntimeError, "Set MOONSHOT_API_KEY"):
                        course.build_llm()
        model.assert_not_called()
        adc.assert_not_called()

    def test_kimi_code_endpoint_and_model_override(self):
        os.environ.update(
            LLM_PROVIDER="kimi",
            MOONSHOT_API_KEY="test-only-key",
            KIMI_BASE_URL="https://api.kimi.com/coding/v1/",
            KIMI_MODEL="k3",
        )
        with (
            patch.object(course, "ChatOpenAI") as model,
            patch.object(course.google.auth, "default") as adc,
        ):
            course.build_llm()
        self.assertEqual(
            model.call_args.kwargs["base_url"], "https://api.kimi.com/coding/v1"
        )
        self.assertEqual(model.call_args.kwargs["model"], "k3")
        self.assertNotIn("default_headers", model.call_args.kwargs)
        adc.assert_not_called()

    def test_kimi_international_endpoints(self):
        os.environ.update(LLM_PROVIDER="kimi", MOONSHOT_API_KEY="test-only-key")
        for base_url in [
            "https://api.moonshot.ai/v1",
            "https://api.kimi.ai/coding/v1",
        ]:
            with self.subTest(base_url=base_url):
                os.environ["KIMI_BASE_URL"] = base_url
                with patch.object(course, "ChatOpenAI") as model:
                    course.build_llm()
                self.assertEqual(model.call_args.kwargs["base_url"], base_url)

    def test_kimi_rejects_untrusted_endpoint_before_client_creation(self):
        os.environ.update(
            LLM_PROVIDER="kimi",
            MOONSHOT_API_KEY="test-only-key",
            KIMI_BASE_URL="https://untrusted.example/v1",
        )
        with patch.object(course, "ChatOpenAI") as model:
            with self.assertRaisesRegex(RuntimeError, "official Kimi API endpoint"):
                course.build_llm()
        model.assert_not_called()

    def test_unknown_provider_does_not_fall_back_to_gemini(self):
        os.environ["LLM_PROVIDER"] = "unknown"
        with (
            patch.object(course.google.auth, "default") as adc,
            patch.object(course, "ChatOpenAI") as kimi,
        ):
            with self.assertRaisesRegex(RuntimeError, "LLM_PROVIDER must be"):
                course.build_llm()
        adc.assert_not_called()
        kimi.assert_not_called()

    def test_ollama_uses_lan_model_without_cloud_credentials(self):
        os.environ.clear()
        os.environ.update(
            LLM_PROVIDER=" OLLAMA ",
            OLLAMA_BASE_URL="http://192.0.2.10:11434/",
            OLLAMA_MODEL="qwen3.8:27b-mlx",
        )
        with (
            patch.object(course, "ChatOllama") as model,
            patch.object(course.google.auth, "default") as adc,
            patch.object(course, "ChatOpenAI") as kimi,
            patch.object(course, "ChatGoogleGenerativeAI") as gemini,
        ):
            self.assertIs(course.build_llm(), model.return_value)
        model.assert_called_once_with(
            model="qwen3.8:27b-mlx",
            base_url="http://192.0.2.10:11434",
            temperature=0,
            reasoning=False,
            client_kwargs={"timeout": 120.0, "trust_env": False},
        )
        adc.assert_not_called()
        kimi.assert_not_called()
        gemini.assert_not_called()

    def test_ollama_defaults_to_localhost(self):
        os.environ.update(LLM_PROVIDER="ollama", OLLAMA_MODEL="test-model")
        with patch.object(course, "ChatOllama") as model:
            course.build_llm()
        self.assertEqual(model.call_args.kwargs["base_url"], "http://localhost:11434")

    def test_ollama_requires_model_without_cloud_fallback(self):
        os.environ["LLM_PROVIDER"] = "ollama"
        with (
            patch.object(course, "ChatOllama") as model,
            patch.object(course.google.auth, "default") as adc,
            patch.object(course, "ChatOpenAI") as kimi,
        ):
            with self.assertRaisesRegex(RuntimeError, "Set OLLAMA_MODEL"):
                course.build_llm()
        model.assert_not_called()
        adc.assert_not_called()
        kimi.assert_not_called()

    def test_ollama_connection_failure_does_not_use_cloud_models(self):
        os.environ.update(LLM_PROVIDER="ollama", OLLAMA_MODEL="test-model")
        with (
            patch.object(course, "ChatOllama", side_effect=ConnectionError),
            patch.object(course, "ChatOpenAI") as kimi,
            patch.object(course, "ChatGoogleGenerativeAI") as gemini,
        ):
            with self.assertRaises(ConnectionError):
                course.build_llm()
        kimi.assert_not_called()
        gemini.assert_not_called()

    def test_course_chain_prints_text_from_content_blocks(self):
        prompts = []

        def respond(prompt):
            prompts.append(prompt.to_string())
            return AIMessage(content=[{"type": "text", "text": "Example summary."}])

        with (
            patch.object(course, "build_llm", return_value=RunnableLambda(respond)),
            redirect_stdout(io.StringIO()) as output,
        ):
            course.main()
        self.assertEqual(len(prompts), 1)
        self.assertIn("two interesting facts", prompts[0])
        self.assertIn("Example summary.", output.getvalue())
        self.assertNotIn("'type': 'text'", output.getvalue())


if __name__ == "__main__":
    unittest.main()
