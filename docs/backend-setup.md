# Backend accounts and addresses

A backend in the dropdown is an available integration, not an already configured account.
You only need credentials for the services you choose to use. An OpenRouter account
can access models offered through OpenRouter without separate direct-provider accounts.
A direct OpenAI, Anthropic, Groq, Together, or Azure backend needs its own credentials
and any required billing/model permissions. An OpenRouter key cannot authenticate those APIs.

| Backend | Base URL in Agent Playpen | Setup needed |
| --- | --- | --- |
| OpenRouter | `https://openrouter.ai/api/v1` | OpenRouter key and sufficient account access/credits |
| OpenAI | `https://api.openai.com/v1` | OpenAI API key and API billing/access |
| Anthropic | `https://api.anthropic.com` | Anthropic API key and API billing/access |
| Groq | `https://api.groq.com/openai/v1` | Groq API key and model access/quota |
| Together | `https://api.together.ai/v1` | Together API key and billing/model access |
| Azure OpenAI | `https://YOUR-RESOURCE.openai.azure.com` | Actual resource endpoint, Azure key, and deployment name in Model |
| LM Studio | `http://localhost:1234/v1` | Running local server with an available model; authentication if enabled there |
| Ollama (local) | `http://localhost:11434` | Running Ollama with a downloaded local model; no local API key |

The Azure example is a placeholder: replace it with your resource's endpoint.
The Model field must contain your Azure deployment name, which may differ from the underlying model ID.
Azure deployment discovery is not implemented in this dashboard; example names are not deployed resources.
The form endpoint/deployment are used when supplied; environment settings remain a fallback.

Ollama's adapter adds the appropriate API paths to the root URL. Use the installed
Ollama model ID from Load, not an OpenRouter or Together model ID. Direct Ollama
cloud access is a separate configuration and is not the local backend described here.

Save cloud keys through Maintenance or the credential manager; saved keys use the existing
encrypted OS credential store. Then press Load. The dashboard distinguishes missing keys,
rejected catalog access, rate limits, unreachable local servers, and empty local model lists.
Provider switches remember the model and local endpoint separately for each backend during
that page session. Fixed cloud endpoints are read-only because their adapters use those endpoints.

A model price or fallback example does not establish account access. OpenRouter's public
catalog can load without authenticating; a successful catalog request does not verify that
inference will work, that credits remain, or that every listed model is enabled.

Verified against official documentation on 2026-10-29:
- [Together OpenAI compatibility](https://docs.together.ai/docs/inference/openai-compatibility)
- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [Ollama API URLs](https://docs.ollama.com/api/introduction)
- [LM Studio OpenAI compatibility](https://lmstudio.ai/docs/developer/openai-compat)
- [Azure endpoint configuration](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/switching-endpoints?view=foundry-classic)


## November 17 integration update

All selected agent tools now execute through the shared Universal Agent Control Plane gateway. The [universal tool guide](universal-tools.md) documents typed contracts, readiness, the direct console, native/prompt model adapters, MCP exposure/connections, execution records, replay and timeout limits. The [issue register](issues-and-resolutions.md) distinguishes observed problems, implemented resolutions and remaining limits; [credits and sources](credits-and-sources.md) acknowledges the upstream creators. Historical study outputs and baseline-v1 scoring remain unchanged. A successful tool operation does not establish final-answer faithfulness or general model reliability.
