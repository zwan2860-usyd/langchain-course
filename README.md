# LangChain Course: Gemini and Kimi

This branch keeps the course's prompt and LCEL chain, using Gemini through
Vertex AI with ADC or Kimi through Moonshot's OpenAI-compatible API.

## Setup

Install the project dependencies with `uv sync --locked`. If `uv` is not on your
terminal's PATH, use `~/.local/bin/uv` instead.

Gemini is selected by default (`LLM_PROVIDER=gemini`). The Google setup below
applies only to Gemini; Kimi does not require a Google project or ADC.

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

Gemini needs no OpenAI, Gemini, or Google API key. The code explicitly passes ADC
credentials and selects the Vertex backend. Shell environment variables take
precedence over the local `.env`.

## Try Kimi

Add these settings to your ignored local `.env`, replacing the key placeholder
with your real Moonshot API key only in that local file:

```dotenv
LLM_PROVIDER=kimi
MOONSHOT_API_KEY=your-api-key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k3
```

The model defaults to `kimi-k3`; use a model available to your account. This
example reuses the existing `langchain-openai` dependency and uses Chat
Completions. The endpoint defaults to `https://api.moonshot.cn/v1`; international
open-platform keys require `https://api.moonshot.ai/v1`. It does not require an
OpenAI key. Provider-specific reasoning fields are not preserved by this wrapper.
Kimi's default generation settings are used rather than copying Gemini's
temperature. There is no automatic fallback between providers.

Kimi Code subscription keys are separate from open-platform keys. For a Code
key created in `www.kimi.com/code/console`, use these local settings instead:

```dotenv
KIMI_BASE_URL=https://api.kimi.com/coding/v1
KIMI_MODEL=k3
```

The overseas Code endpoint is `https://api.kimi.ai/coding/v1`. Code model IDs
differ from open-platform IDs: K3 is `k3`, not `kimi-k3`. K3 requires an eligible
subscription; use `kimi-for-coding` only if that model is included in your plan.
The code accepts only official endpoints to avoid sending keys to arbitrary hosts.

Code subscriptions are restricted to personal interactive use. Follow the
provider's terms; use the open platform for batch processing or product/API
services. Keep the client's real identity: do not spoof User-Agent to bypass
client restrictions. If your client is rejected, use an approved client or
contact Kimi support. This example does not verify your plan's model access.

To try Kimi without changing `LLM_PROVIDER` in your local file:

```bash
LLM_PROVIDER=kimi uv run main.py
```

Set `LLM_PROVIDER=gemini` to switch back. Never put a real key in `.env.example`.

## Run and Test

```bash
uv run main.py
uv run python -m unittest test_main -v
```

Running `main.py` sends the example prompt to the selected provider and consumes
API usage or subscription quota. Unit tests are offline and do not use your credentials.
The example prints plain response text, not content blocks or authentication
details.

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

The directory scan can also detect keys in ignored local files such as `.env`.
A finding in an ignored, untracked file is not by itself evidence of a Git leak;
check tracking and history before drawing that conclusion. Do not disable the
staged or history scan rules to hide these local-only findings.

Local `.env` variants, credential JSON, auth directories, and private keys are
ignored; `.env.example` contains placeholders only and is safe to track. Never
put real credentials in source code or force-add ignored files. Ignore rules do
not remove files or secrets that were already committed. If a scan finds an
exposed credential, revoke or rotate it before deciding how to clean history.

Hooks must be installed in each clone, require Gitleaks on PATH, and can be
bypassed. This configuration belongs to this course branch; other branches need
the same safeguards. Automated scans reduce risk but cannot guarantee detection
of every kind of sensitive information.
