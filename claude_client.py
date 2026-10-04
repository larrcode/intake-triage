"""
Single responsibility: send intake text to Claude, get back a
structured suggestion. Nothing in this file ever writes to the
database or shows anything to the user directly, that's main.py's job.
Keeping this isolated means the AI call can be swapped, mocked for
testing, or pointed at a different model without touching storage or
the UI at all.
"""

import os
import json
from config import load_categories

try:
    import anthropic
except ImportError:
    anthropic = None


class SuggestionError(Exception):
    """Raised when Claude can't be reached or returns something unusable.
    main.py should catch this and let the human type the category and
    response manually, the tool should degrade, not block someone's work."""
    pass


SYSTEM_PROMPT_TEMPLATE = """You triage incoming requests for a community organization's intake desk.

Given the request text, respond with ONLY a JSON object, no other text:
{{"category": "<one of: {categories}>", "response": "<a short, polite draft reply, 2-3 sentences>"}}

The response you draft is a STARTING POINT for a staff member to edit, not a final answer.
Do not promise anything specific (dates, dollar amounts, guarantees) you cannot verify from the request text alone."""


def get_suggestion(request_text, api_key=None):
    """
    Returns {"category": str, "response": str}.
    Raises SuggestionError on any failure, the caller decides what to
    do when the AI step fails, this function doesn't decide for them.
    """
    if anthropic is None:
        raise SuggestionError("The anthropic package isn't installed. Run: pip install anthropic")

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SuggestionError("No ANTHROPIC_API_KEY found. Set it in your .env file.")

    categories = load_categories()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(categories=", ".join(categories))

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": request_text}],
        )
    except Exception as e:
        raise SuggestionError(f"Claude API call failed: {e}")

    raw_text = message.content[0].text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        raise SuggestionError(f"Claude didn't return valid JSON: {raw_text[:200]}")

    if "category" not in parsed or "response" not in parsed:
        raise SuggestionError(f"Claude's response is missing expected fields: {parsed}")

    return parsed


def get_suggestion_mock(request_text):
    """
    A stand-in that doesn't call the API at all, for testing the rest
    of the app without spending money or needing a key configured.
    Not used by main.py directly, just available for development.
    """
    categories = load_categories()
    return {
        "category": categories[0],
        "response": "Thank you for reaching out. A staff member will review your request and follow up shortly.",
    }
