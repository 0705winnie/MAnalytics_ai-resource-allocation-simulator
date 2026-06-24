from __future__ import annotations

"""
LLM client wrapper.

Controls which provider is used via the LLM_PROVIDER environment variable:
    LLM_PROVIDER=azure   →  call Azure OpenAI  (default)
    LLM_PROVIDER=mock    →  return scripted responses (no API key needed)

Azure credentials (required when LLM_PROVIDER=azure):
    AZURE_OPENAI_ENDPOINT    — e.g. https://my-resource.openai.azure.com/
    AZURE_OPENAI_API_KEY     — your Azure OpenAI API key
    AZURE_OPENAI_DEPLOYMENT  — deployment name, e.g. "gpt-4o-mini"
    AZURE_OPENAI_API_VERSION — API version, e.g. "2024-02-01"
"""

import os
from abc import ABC, abstractmethod

from app.services.prompt_templates import build_system_prompt


class LLMError(Exception):
    """Raised when an LLM call fails in a way the API endpoint should handle."""


# ---------------------------------------------------------------------------
# Shared interface — both clients must implement this
# ---------------------------------------------------------------------------

class BaseLLMClient(ABC):
    @abstractmethod
    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
    ) -> dict:
        """
        Parameters
        ----------
        message  : The student's current message.
        history  : Prior conversation turns, each {"role": ..., "content": ...}.
        context  : Optional dashboard state (month, capacity, last results).

        Returns
        -------
        {"content": str, "provider": str}
        """


# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------

class AzureLLMClient(BaseLLMClient):
    """Calls Azure OpenAI using the official openai Python package."""

    def __init__(self) -> None:
        endpoint   = os.environ.get("AZURE_OPENAI_ENDPOINT",   "").strip()
        api_key    = os.environ.get("AZURE_OPENAI_API_KEY",    "").strip()
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01").strip()

        if not endpoint:
            raise LLMError(
                "AZURE_OPENAI_ENDPOINT is not set. "
                "Add it to your .env file, or set LLM_PROVIDER=mock to run locally."
            )
        if not api_key:
            raise LLMError(
                "AZURE_OPENAI_API_KEY is not set. "
                "Add it to your .env file, or set LLM_PROVIDER=mock to run locally."
            )

        try:
            from openai import AzureOpenAI
        except ImportError as e:
            raise LLMError(
                "The 'openai' package is not installed. "
                "Run: pip install openai"
            ) from e

        self._client     = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self._deployment = deployment

    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
    ) -> dict:
        system_prompt = build_system_prompt(context)

        # Build the message list: system prompt, then conversation history, then new message
        messages = [{"role": "system", "content": system_prompt}]
        for turn in (history or []):
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": message})

        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                max_tokens=600,
                temperature=0.7,
            )
        except Exception as e:
            raise LLMError(f"Azure OpenAI API call failed: {e}") from e

        content = response.choices[0].message.content or ""
        return {"content": content.strip(), "provider": "azure"}


# ---------------------------------------------------------------------------
# Mock client  —  no API key required
# ---------------------------------------------------------------------------

# Keyword → scripted response. Checked in order; first match wins.
_MOCK_RESPONSES: list[tuple[str, str]] = [
    (
        "vip",
        "VIP requests carry the highest unit price ($12/unit) and tend to be "
        "shorter jobs, so they free up cluster capacity quickly after completion.\n\n"
        "**Question to think about:** If your clusters are at 80% capacity and a "
        "VIP arrives alongside an economy request, which should you admit first — "
        "and does it matter which cluster you route each one to? Why?"
    ),
    (
        "economy",
        "Economy requests have the lowest price ($4/unit) and tend to hold "
        "capacity for longer. This creates an **opportunity cost**: an economy "
        "job occupying 6 units for many hours may block a VIP job worth 3× as "
        "much per unit.\n\n"
        "What capacity threshold would you use to decide when to stop admitting "
        "economy requests? How did you arrive at that number?"
    ),
    (
        "reject",
        "The always-reject policy earns $0 — it's a sanity check, not a "
        "strategy. A simple upgrade is **greedy first-fit**: admit every "
        "feasible request to the first cluster that has room.\n\n"
        "That earns revenue, but can you think of a case where greedy first-fit "
        "hurts you compared to a smarter policy?"
    ),
    (
        "cluster",
        "You have 3 clusters, each with 100 units. Routing matters because "
        "sending every request to Cluster 1 fills it up while Clusters 2 and 3 "
        "sit idle — future requests may be forced to take suboptimal clusters.\n\n"
        "Two common routing strategies:\n"
        "- **Least-loaded**: send to the cluster with the most remaining capacity.\n"
        "- **Best-fit**: send to the cluster that leaves the smallest nonnegative "
        "remaining capacity after admission.\n\n"
        "Which do you think performs better here, and why?"
    ),
    (
        "def ",
        "I can see you're sharing policy code. A few things to verify:\n\n"
        "1. **Return type** — must be an `int`: `1`, `2`, or `3` (cluster id) "
        "or `0` (reject). Returning `None` or a string triggers auto-reject.\n"
        "2. **Feasibility check** — before returning a cluster id, confirm:\n"
        "   ```python\n"
        "   state['remaining_capacity'][cluster_id] >= request['required_units']\n"
        "   ```\n"
        "   Returning an infeasible cluster also triggers auto-reject with a warning.\n"
        "3. **State keys** — use `state['remaining_capacity']`, a dict keyed by "
        "cluster id (integers 1, 2, 3).\n\n"
        "Share the specific error message if you're stuck and I'll help trace it."
    ),
    (
        "month",
        "To interpret your monthly results, focus on:\n\n"
        "- **Admission rate by type** — are you rejecting too many VIPs? "
        "That usually means economy requests are filling your clusters first.\n"
        "- **Unfinished requests at month-end** — jobs that don't complete earn "
        "$0. A high unfinished count suggests you're admitting long-duration "
        "jobs close to month-end.\n\n"
        "Which of these is the bigger issue in your current results?"
    ),
    (
        "capacity",
        "`state['remaining_capacity']` gives you the free units per cluster, "
        "updated after every admission and departure.\n\n"
        "A simple pattern:\n"
        "```python\n"
        "feasible = [\n"
        "    (n, rem) for n, rem in state['remaining_capacity'].items()\n"
        "    if rem >= request['required_units']\n"
        "]\n"
        "if not feasible:\n"
        "    return 0  # reject\n"
        "# pick the cluster with the most remaining capacity\n"
        "return max(feasible, key=lambda x: x[1])[0]\n"
        "```\n"
        "What would you change in this snippet to implement a different rule?"
    ),
]

_DEFAULT_MOCK = (
    "Good question to think through.\n\n"
    "At each arrival you're making an **online decision** without knowing what "
    "requests will come next. The core tension is:\n"
    "- **Accept now** → earn revenue if the job completes, but capacity is locked "
    "until the job departs.\n"
    "- **Reject now** → preserve capacity for a potentially higher-value request later.\n\n"
    "What aspect of your policy are you most uncertain about — the admission "
    "threshold, the routing rule, or how to handle specific request types?"
)


class MockLLMClient(BaseLLMClient):
    """Returns scripted responses based on keywords. No API key required."""

    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
    ) -> dict:
        msg_lower = message.lower()

        content = _DEFAULT_MOCK
        for keyword, response in _MOCK_RESPONSES:
            if keyword in msg_lower:
                content = response
                break

        if context and context.get("current_month"):
            month = context["current_month"]
            content = f"*(Month {month} · mock mode)*\n\n{content}"

        return {"content": content, "provider": "mock"}


# ---------------------------------------------------------------------------
# Factory — returns the right client based on LLM_PROVIDER env var
# ---------------------------------------------------------------------------

def get_llm_client() -> BaseLLMClient:
    """
    Read LLM_PROVIDER and return the matching client.
    Defaults to Azure if LLM_PROVIDER is not set.
    """
    provider = os.environ.get("LLM_PROVIDER", "azure").strip().lower()

    if provider == "mock":
        return MockLLMClient()

    if provider == "azure":
        return AzureLLMClient()  # raises LLMError if credentials are missing

    raise LLMError(
        f"Unknown LLM_PROVIDER='{provider}'. Valid values: 'azure', 'mock'."
    )
