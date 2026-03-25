"""Tools for the D&D Note Generation Agent.

These tools are used by the agents to interact with the file system.
"""

import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from src.config import VAULT_PATH, SESSION_NOTES_PATH, NOTE_OUTPUT_PATHS, PROJECT_ROOT
from src.logging_config import logger


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file.
    
    Use this to read session notes or any markdown files.
    
    Args:
        file_path: Path to the file. Can be:
           - Absolute path
           - Relative to the project root (where you run the app)
           - Relative to the Obsidian vault
           - Just a filename (will search in both locations)
        
    Returns:
        The contents of the file as a string
    """
    # Clean up the path
    file_path = file_path.strip()
    
    # Try different locations
    search_paths = [
        Path(file_path),  # Absolute or current directory
        PROJECT_ROOT / file_path,  # Project root
        VAULT_PATH / file_path,  # Vault path
        SESSION_NOTES_PATH / file_path,  # Session notes
    ]
    
    # If just a filename, search in common locations
    if not os.path.dirname(file_path):
        search_paths.extend([
            PROJECT_ROOT / "Session Notes" / file_path,
            PROJECT_ROOT / file_path,
            VAULT_PATH / "Session Notes" / file_path,
            SESSION_NOTES_PATH / file_path,
        ])
    
    # Try each path
    for path in search_paths:
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                logger.debug(f"Read file: {path}")
                return content
            except Exception as e:
                logger.error(f"Error reading file {path}: {e}")
                return f"Error reading file: {e}"
    
    # File not found
    logger.error(f"File not found: {file_path}")
    return f"Error: File not found: {file_path}\n\nSearched in:\n" + "\n".join(f"  - {p}" for p in search_paths)


@tool
def write_note(note_type: str, name: str, content: str, dry_run: bool = False) -> str:
    """Write a note to the Obsidian vault.
    
    Creates a markdown file in the appropriate directory based on note type.
    
    Args:
        note_type: Type of note (npc, locale, object, organization)
        name: Name of the note (without .md extension)
        content: Markdown content for the note
        dry_run: If True, only return what would be written without creating the file
        
    Returns:
        Confirmation message with the path where the note was/would be written
    """
    if note_type not in NOTE_OUTPUT_PATHS:
        available_types = ", ".join(NOTE_OUTPUT_PATHS.keys())
        return f"Error: Unknown note type '{note_type}'. Available types: {available_types}"
    
    # Build output path
    output_dir = VAULT_PATH / NOTE_OUTPUT_PATHS[note_type]
    output_path = output_dir / f"{name}.md"
    
    if dry_run:
        logger.info(f"[DRY RUN] Would write: {output_path}")
        return f"[DRY RUN] Would create: {output_path}\n\nContent preview:\n{content[:500]}..."
    
    try:
        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Created note: {output_path}")
        return f"Successfully created: {output_path}"
    except Exception as e:
        logger.error(f"Error writing note {output_path}: {e}")
        return f"Error writing note: {e}"


@tool
def list_notes(
    note_type: Optional[str] = None,
    directory: Optional[str] = None
) -> str:
    """List notes in the vault.
    
    Args:
        note_type: Filter by note type (npc, locale, object, organization)
        directory: Specific directory to list (relative to vault)
        
    Returns:
        List of note names and paths
    """
    if note_type and note_type in NOTE_OUTPUT_PATHS:
        search_dir = VAULT_PATH / NOTE_OUTPUT_PATHS[note_type]
    elif directory:
        search_dir = VAULT_PATH / directory
    else:
        search_dir = VAULT_PATH
    
    if not search_dir.exists():
        return f"Directory not found: {search_dir}"
    
    try:
        notes = []
        for path in search_dir.rglob("*.md"):
            # Get path relative to vault
            rel_path = path.relative_to(VAULT_PATH)
            notes.append(str(rel_path))
        
        if not notes:
            return f"No notes found in {search_dir}"
        
        notes.sort()
        result = f"Found {len(notes)} notes:\n\n"
        result += "\n".join(f"- {n}" for n in notes)
        return result
    except Exception as e:
        logger.error(f"Error listing notes: {e}")
        return f"Error listing notes: {e}"


@tool
def note_exists(name: str, note_type: str) -> bool:
    """Check if a note already exists.
    
    Args:
        name: Name of the note (without .md extension)
        note_type: Type of note (npc, locale, object, organization)
        
    Returns:
        True if the note exists, False otherwise
    """
    if note_type not in NOTE_OUTPUT_PATHS:
        return False
    
    output_dir = VAULT_PATH / NOTE_OUTPUT_PATHS[note_type]
    note_path = output_dir / f"{name}.md"
    
    return note_path.exists()
