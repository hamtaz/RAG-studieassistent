"""Content moderation for generation input/output via Azure AI Content Safety.

Optional feature: ingestion and retrieval never call this, and a Content
Safety resource may not be provisioned yet, so a missing configuration is a
pass-through (logged once), not a hard failure - see check_text().

Prompt Shields (jailbreak / prompt-injection detection) is deliberately not
used here: as of azure-ai-contentsafety 1.0.0 (and its only other release,
1.0.0b1), ContentSafetyClient exposes only analyze_text/analyze_image - no
shield_prompt method exists in any published version of the Python SDK, it's
REST-only today. Prompt-injection defense instead lives in the system prompt
(src/generation.py) plus behavioral tests (scripts/check_prompt_injection.py).
Revisit if Prompt Shields ships in a future SDK release.
"""

import logging
from functools import lru_cache

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions
from azure.core.credentials import AzureKeyCredential

from src.config import get_settings

logger = logging.getLogger(__name__)

# Content Safety severity is 0/2/4/6 (or 0-7 in eight-level mode, unused
# here). 2 is "low" - rejecting at or above it is a deliberately strict
# default for a study assistant with no adult audience to weigh against it.
SEVERITY_THRESHOLD = 2


def is_flagged(categories: list[dict]) -> bool:
    """True if any category's severity meets SEVERITY_THRESHOLD.

    Pure function over analyze_text's categories_analysis, shaped as
    [{"category": ..., "severity": int}, ...] - unit-testable without a live
    Content Safety resource.
    """
    return any(category["severity"] >= SEVERITY_THRESHOLD for category in categories)


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.content_safety_endpoint and settings.content_safety_key)


@lru_cache
def _get_client() -> ContentSafetyClient:
    """Build (and cache) the ContentSafetyClient. Only call once is_configured() is True."""
    settings = get_settings()
    assert settings.content_safety_endpoint and settings.content_safety_key
    return ContentSafetyClient(
        settings.content_safety_endpoint, AzureKeyCredential(settings.content_safety_key)
    )


def check_text(text: str) -> bool:
    """True if `text` is safe to use. Pass-through (True) if unconfigured."""
    if not is_configured():
        logger.warning("Content Safety not configured - skipping moderation check.")
        return True

    client = _get_client()
    result = client.analyze_text(AnalyzeTextOptions(text=text))
    categories = [{"category": c.category, "severity": c.severity} for c in result.categories_analysis]
    return not is_flagged(categories)
