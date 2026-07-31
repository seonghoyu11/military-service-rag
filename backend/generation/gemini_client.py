"""
Guarded wrapper around the google-genai SDK.

This project must never incur paid usage (see docs/devlog.md, "5단계 LLM
전환"). Two things enforce that here: a hardcoded free-tier-only model
whitelist (never configurable via env/config, so a typo or a later edit
can't silently point at a paid model), and a capped, backed-off retry that
stops on rate-limit errors instead of hammering the API.
"""
import time

from google import genai
from google.genai import errors

import config

# Free-tier-eligible Flash models only, as of 2026-07-31 (checked directly
# against the Google AI Studio / Gemini API console free-tier list). Pro-tier
# models (e.g. gemini-3.1-pro) left the free tier entirely on 2026-04-01 and
# must never be added here, along with any image/video generation models.
# This list tracks a moving target (model generations turn over) -- re-check
# the console before adding or removing an entry.
ALLOWED_MODELS = {
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
}

# Frontier-grade Flash tier, free-tier eligible as of 2026-07-31. NOTE: of the
# 6 whitelisted models, live smoke-testing on this project's API key that day
# found gemini-2.5-flash returns 404 ("no longer available to new users") and
# gemini-2.0-flash returns 429 with a hard 0 free-tier quota -- both are
# effectively dead for this account despite being nominally free-tier models.
# gemini-3.5-flash (non-lite) consistently returned 503 "high demand" across
# repeated retries, so it isn't used as the default either even though it's
# in the whitelist. gemini-3.6-flash, gemini-3.5-flash-lite, and
# gemini-3.1-flash-lite all responded successfully in that same test --
# gemini-3.6-flash is the newest/most capable of the three that actually
# work, so it's the default.
DEFAULT_MODEL = "gemini-3.6-flash"

# Free-tier rate limits vary by model (roughly 10-15 requests/min, 1,000-1,500
# requests/day) and are enforced server-side -- exceeding them should fail
# with 429, never silently upgrade to paid usage. A capped retry (not
# unbounded) keeps a burst of 429s from turning into a hammering loop.
MAX_RETRIES = 2
RETRY_BASE_DELAY_SECONDS = 1


class DisallowedModelError(ValueError):
    """Raised when a caller asks for a model outside ALLOWED_MODELS."""


def _get_client():
    # vertexai=False is explicit here, not just relied on as the default --
    # Vertex AI is a billing-enabled path and this project must never touch
    # it. Only the Google AI Studio (API key) path is allowed.
    return genai.Client(api_key=config.GOOGLE_API_KEY, vertexai=False)


def generate(model, contents, generation_config=None):
    """
    Calls Gemini's generateContent with the model whitelist enforced and a
    capped, exponential-backoff retry on 429 (rate limit/quota) errors only
    -- any other error (auth, invalid request, server error) surfaces
    immediately rather than being retried.

    NOTE (data privacy, not a cost/billing concern): prompts and responses
    sent through the free tier may be used by Google to improve their
    products. The statutory text itself isn't sensitive, but if this chatbot
    ever starts accepting questions that contain a user's real personal
    information, that's a reason to revisit this before any real-user
    deployment.
    """
    if model not in ALLOWED_MODELS:
        raise DisallowedModelError(
            f"{model!r} is not in the free-tier model whitelist {sorted(ALLOWED_MODELS)}"
        )

    client = _get_client()
    attempt = 0
    while True:
        try:
            return client.models.generate_content(
                model=model, contents=contents, config=generation_config
            )
        except errors.ClientError as e:
            if e.code != 429 or attempt >= MAX_RETRIES:
                raise
            time.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))
            attempt += 1
