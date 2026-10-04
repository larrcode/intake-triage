"""
Categories live here, not hardcoded into claude_client.py or main.py.
Every organization's intake categories are different; a real deployment
means editing this one file and nothing else, not hunting through the
UI code or the AI prompt to change what "categories" even means.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "categories.json"

DEFAULT_CATEGORIES = [
    "General question",
    "Volunteer inquiry",
    "Service request",
    "Donation inquiry",
    "Complaint or concern",
    "Other",
]


def load_categories():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return DEFAULT_CATEGORIES


def save_categories(categories):
    with open(CONFIG_PATH, "w") as f:
        json.dump(categories, f, indent=2)
