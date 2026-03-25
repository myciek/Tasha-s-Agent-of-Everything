"""Configuration for D&D Note Generation Agent."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\kinga\Documents\Tashas-Notes-of-Everything"))
TEMPLATES_PATH = VAULT_PATH / "Assets" / "Templates"

# OpenRouter API (supports free models)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct")

# Note type to template mapping
TEMPLATE_FILES = {
    "npc": TEMPLATES_PATH / "NPC.md",
    "locale": TEMPLATES_PATH / "LOCALE.md",
    "object": TEMPLATES_PATH / "OBJECT.md",
    "organization": TEMPLATES_PATH / "ORGANIZATION.md",
}

# Output paths for each note type
NOTE_OUTPUT_PATHS = {
    "npc": "Compendium/NPC's",
    "locale": "Compendium/Atlas",
    "object": "Compendium/Lore/Objects",
    "organization": "Compendium/Lore/Organizations",
}

# Session notes path
SESSION_NOTES_PATH = VAULT_PATH / "Session Notes"

# Agent settings
AGENT_CONFIG = {
    "temperature": 0.7,
    "max_output_tokens": 2048,
}
