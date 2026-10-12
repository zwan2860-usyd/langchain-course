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
            temperature=1.0,
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
