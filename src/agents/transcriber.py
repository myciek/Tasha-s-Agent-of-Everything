"""Transcriber Agent - extracts entities from raw transcripts to shared JSON."""

import json
import re
from datetime import datetime
from pathlib import Path

from langchain_ollama import ChatOllama

from src.config import AGENT_CONFIG, SHARED_DATA_PATH, EXTRACTED_ENTITIES_FILE, VAULT_PATH, DEFAULT_MODEL
from src.logging_config import logger


class TranscriberAgent:
    """Agent that extracts entities from session transcripts."""
    
    def __init__(self, model: str = DEFAULT_MODEL):
        self.llm = ChatOllama(
            model=model,
            temperature=AGENT_CONFIG["temperature"],
        )
        logger.info(f"Transcriber Agent initialized with model: {model}")
    
    def run(self, transcript_path: str, session_id: str = None) -> dict:
        """Extract entities from a transcript and save to shared JSON."""
        logger.info(f"Transcriber processing: {transcript_path}")
        
        # Read the transcript
        content = self._read_transcript(transcript_path)
        if not content:
            return {"success": False, "error": f"Could not read: {transcript_path}"}
        
        # Generate session ID if not provided
        if not session_id:
            session_id = Path(transcript_path).stem
        
        # Extract entities using LLM
        entities = self._extract_entities(content)
        
        # Build the shared data structure
        shared_data = {
            "session_id": session_id,
            "source_file": transcript_path,
            "timestamp": datetime.now().isoformat(),
            "entities": entities,
            "metadata": {
                "total_npcs": len(entities.get("npcs", [])),
                "total_locales": len(entities.get("locales", [])),
                "total_objects": len(entities.get("objects", [])),
                "total_organizations": len(entities.get("organizations", [])),
            }
        }
        
        # Save to shared storage
        self._save_to_shared(shared_data)
        
        total = (
            len(entities.get("npcs", [])) +
            len(entities.get("locales", [])) +
            len(entities.get("objects", [])) +
            len(entities.get("organizations", []))
        )
        
        logger.info(f"Extracted {total} entities from {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "entities": entities,
            "total_extracted": total,
            "output_file": str(EXTRACTED_ENTITIES_FILE),
        }
    
    def _read_transcript(self, path: str) -> str:
        """Read transcript from various possible paths."""
        search_paths = [
            Path(path),
            Path.cwd() / path,
            VAULT_PATH / path,
            Path.cwd() / "Session Notes" / path,
            VAULT_PATH / "Session Notes" / path,
        ]
        
        for p in search_paths:
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")
        return ""
    
    def _extract_entities(self, content: str) -> dict:
        """Use LLM to extract entities from transcript."""
        prompt = f"""You are a D&D world-building assistant. Read the session transcript and extract ALL entities.

For each entity type, output in this exact format:

[NPCS]
name: <name>, description: <brief description>

[LOCALES]
name: <name>, description: <brief description>

[OBJECTS]
name: <name>, description: <brief description>

[ORGANIZATIONS]
name: <name>, description: <brief description>

Rules:
- Be thorough - extract every NPC, location, item, and organization mentioned
- Use the EXACT format shown above
- One entity per line
- If a type has no entities, just write "[<TYPE>]" with nothing after
- Be specific with names (e.g., "Grimtooth the Merchant" not just "Grimtooth")

TRANSCRIPT:
{content}

Extract all entities now:"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])
        
        return self._parse_entities(response.content)
    
    def _parse_entities(self, content: str) -> dict:
        """Parse LLM output into structured dictionary."""
        entities = {
            "npcs": [],
            "locales": [],
            "objects": [],
            "organizations": []
        }
        
        current_type = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line.startswith('[NPCS]') or line.startswith('[NPC]'):
                current_type = "npcs"
            elif line.startswith('[LOCALES]') or line.startswith('[LOCALE]'):
                current_type = "locales"
            elif line.startswith('[OBJECTS]') or line.startswith('[OBJECT]'):
                current_type = "objects"
            elif line.startswith('[ORGANIZATIONS]') or line.startswith('[ORGANIZATION]'):
                current_type = "organizations"
            elif current_type and line and ':' in line:
                # Parse "name: X, description: Y"
                entity = self._parse_entity_line(line)
                if entity:
                    entities[current_type].append(entity)
        
        return entities
    
    def _parse_entity_line(self, line: str) -> dict:
        """Parse a single entity line like 'name: Grimtooth, description: A sneaky goblin'."""
        try:
            # Handle "name: X, description: Y" format
            parts = line.split(',', 1)
            if len(parts) < 2:
                return None
            
            name_part = parts[0].strip()
            desc_part = parts[1].strip()
            
            if not name_part.startswith('name:'):
                return None
            
            name = name_part[5:].strip()
            description = ""
            
            if desc_part.startswith('description:'):
                description = desc_part[12:].strip()
            
            if not name:
                return None
            
            return {"name": name, "description": description}
        except Exception as e:
            logger.warning(f"Failed to parse entity line: {line} - {e}")
            return None
    
    def _save_to_shared(self, data: dict) -> bool:
        """Save extracted entities to shared JSON file."""
        try:
            SHARED_DATA_PATH.mkdir(parents=True, exist_ok=True)
            EXTRACTED_ENTITIES_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info(f"Saved entities to {EXTRACTED_ENTITIES_FILE}")
            return True
        except Exception as e:
            logger.error(f"Failed to save entities: {e}")
            return False
