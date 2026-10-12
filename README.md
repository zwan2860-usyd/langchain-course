# LangChain Course: Gemini with ADC

This branch keeps the course's prompt and LCEL chain, using Gemini through
Vertex AI rather than an OpenAI API key.

## Setup

Install the project dependencies with `uv sync --locked`. If `uv` is not on your
terminal's PATH, use `~/.local/bin/uv` instead.

Reuse your existing Google Application Default Credentials (ADC). Only if ADC
is missing, run this command yourself and complete the browser login:

```bash
gcloud auth application-default login
```

An ordinary `gcloud auth login` is not a substitute for ADC. Do not create a
service-account key or copy the local ADC credential file into this repository.
Your account needs access to a Google Cloud project with billing and the Vertex AI
API enabled, including permission to invoke the model. This example does not
change your global gcloud project or ADC quota-project configuration.

Create a local `.env` using `.env.example` as the template and replace the
placeholder project ID. The only settings needed are:

- `GOOGLE_CLOUD_PROJECT`: your authorized Google Cloud project.
- `GOOGLE_CLOUD_LOCATION`: defaults to `global`.
- `GEMINI_MODEL`: defaults to `gemini-3.8-flash`.

No OpenAI, Gemini, or Google API key is needed. The code explicitly passes ADC
credentials and selects the Vertex backend. Shell environment variables take
precedence over the local `.env`.

## Run and Test

```bash
uv run main.py
uv run python -m unittest test_main -v
```

Running `main.py` sends the example prompt to Google and incurs model usage
charges. Unit tests are offline and do not use your credentials. Gemini 3.8 Flash
uses temperature 1.0; the example prints plain response text, not content blocks
or authentication details.

## Secret Protection

Install Gitleaks (`brew install gitleaks` on macOS), ensure it is on PATH, then
install the local commit hook:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
gitleaks dir . --redact
gitleaks git --log-opts=--all --redact
```

The pinned Gitleaks hook checks staged changes before a normal `git commit`.
The directory scan checks current files; the Git scan checks the reachable
history of every local branch and remote-tracking branch. Keep scanner output
redacted and never paste raw credentials into issues, logs, or pull requests.

Local `.env` variants, credential JSON, auth directories, and private keys are
ignored; `.env.example` contains placeholders only and is safe to track. Never
put real credentials in source code or force-add ignored files. Ignore rules do
not remove files or secrets that were already committed. If a scan finds an
exposed credential, revoke or rotate it before deciding how to clean history.

Hooks must be installed in each clone, require Gitleaks on PATH, and can be
bypassed. This configuration belongs to this course branch; other branches need
the same safeguards. Automated scans reduce risk but cannot guarantee detection
of every kind of sensitive information.
