"""Transcriber Agent - extracts entities from raw transcripts to shared JSON."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from langchain_ollama import ChatOllama

from src.config import AGENT_CONFIG, SHARED_DATA_PATH, EXTRACTED_ENTITIES_FILE, VAULT_PATH, DEFAULT_MODEL
from src.logging_config import logger

# Generic terms to filter out - these are not specific named entities
GENERIC_NPC_NAMES = {
    # Generic races/classes (not specific characters)
    "elf", "dwarf", "human", "halfling", "orc", "goblin", "dragon", 
    "lich", "spirit", "ghost", "wraith", "skeleton", "zombie",
    "npc", "character", "person", "guy", "man", "woman", "boy", "girl",
    "member", "party member", "you", "narrator", "dm", "dm narrator",
    # Player characters that are just player placeholders
    "player", "druid", "paladin", "ranger", "mage", "cleric", "rogue", "warrior",
    # Generic descriptors
    "elf", "the elf", "the dwarf", "the human", "old man", "old woman",
    # Polish terms
    "książka", "biblioteka", "król", "królowa", "książę", "wojewoda",
}

GENERIC_LOCALE_PATTERNS = {
    # Generic rooms/features
    "library", "biblioteka", "book", "books", "table", "stool", "chair", "shelf", "shelves",
    "room", "rooms", "floor", "ceiling", "wall", "walls", "door", "window",
    # Generic descriptions
    "a sauna", "a room with books", "the library", "somewhere", "place",
    # Single common words
    "castle", "building", "area", "location",
    # Polish terms
    "zamek", "dom", "miasto", "wioska", "wieś", "pałac", "karczma", "gospoda",
}

GENERIC_OBJECT_PATTERNS = {
    # Generic items
    "book", "books", "item", "items", "object", "objects", "food", "table", 
    "stool", "chair", "weapon", "armor", "scroll", "potion", "note", "notes",
    # Overly generic descriptions
    "a book", "an item", "the book", "something", "anything",
    # Incomplete/partial
    "notes named", "book made of",
    # Polish terms
    "książka", "jedzenie", "broń", "zbroja", "mikstura",
}

GENERIC_ORG_PATTERNS = {
    # Too vague
    "order", "group", "faction", "guild", "organization",
}


class TranscriberAgent:
    """Agent that extracts entities from session transcripts."""
    
    def __init__(self, model: str = DEFAULT_MODEL):
        self.llm = ChatOllama(
            model=model,
            temperature=0.1,  # Low temp for consistent structured output
        )
        logger.info(f"Transcriber Agent initialized with model: {model}")
    
    def run(self, transcript_path: str, session_id: str = None, 
            ask_confirmation: Optional[Callable] = None) -> dict:
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
        
        # Filter out generic entities
        entities = self._filter_entities(entities)
        logger.info(f"After filtering: {len(entities['npcs'])} NPCs, {len(entities['locales'])} locales, {len(entities['objects'])} objects, {len(entities['organizations'])} orgs")
        
        # Ask user to confirm uncertain entities
        if ask_confirmation and entities:
            confirmed_entities = self._confirm_entities(entities, ask_confirmation)
        else:
            confirmed_entities = entities
        
        # Build the shared data structure
        shared_data = {
            "session_id": session_id,
            "source_file": transcript_path,
            "timestamp": datetime.now().isoformat(),
            "entities": confirmed_entities,
            "metadata": {
                "total_npcs": len(confirmed_entities.get("npcs", [])),
                "total_locales": len(confirmed_entities.get("locales", [])),
                "total_objects": len(confirmed_entities.get("objects", [])),
                "total_organizations": len(confirmed_entities.get("organizations", [])),
            }
        }
        
        # Save to shared storage
        self._save_to_shared(shared_data)
        
        total = (
            len(confirmed_entities.get("npcs", [])) +
            len(confirmed_entities.get("locales", [])) +
            len(confirmed_entities.get("objects", [])) +
            len(confirmed_entities.get("organizations", []))
        )
        
        logger.info(f"Extracted {total} entities from {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "entities": confirmed_entities,
            "total_extracted": total,
            "output_file": str(EXTRACTED_ENTITIES_FILE),
        }
    
    def _confirm_entities(self, entities: dict, ask_confirmation: Callable) -> dict:
        """Ask user to confirm uncertain entities with rename option."""
        confirmed = {
            "npcs": [],
            "locales": [],
            "objects": [],
            "organizations": []
        }
        
        all_entities = []
        entity_types = {
            "npc": ("npcs", "NPC"),
            "locale": ("locales", "Location"),
            "object": ("objects", "Object"),
            "organization": ("organizations", "Organization"),
        }
        
        # Collect all entities with their types
        for etype, (key, label) in entity_types.items():
            for entity in entities.get(key, []):
                all_entities.append({
                    "type": etype,
                    "key": key,
                    "label": label,
                    "original_name": entity.get("name", ""),
                    "name": entity.get("name", ""),
                    "description": entity.get("description", ""),
                })
        
        if not all_entities:
            return entities
        
        print(f"\n{'='*60}")
        print(f"Found {len(all_entities)} potential entities. Please confirm:")
        print(f"{'='*60}")
        
        # Group by type
        by_type = {}
        for e in all_entities:
            by_type.setdefault(e["type"], []).append(e)
        
        for etype, items in by_type.items():
            print(f"\n{items[0]['label'].upper()}S ({len(items)}):")
            for i, item in enumerate(items, 1):
                global_idx = all_entities.index(item) + 1
                print(f"  [{global_idx}] {item['name']}")
                if item['description']:
                    desc_preview = item['description'][:60] + "..." if len(item['description']) > 60 else item['description']
                    print(f"      [{desc_preview}]")
        
        print(f"\n{'='*60}")
        print("Commands:")
        print("  Enter numbers to accept (e.g., 1,3,5)")
        print("  'a' - accept ALL")
        print("  'n' - decline ALL")
        print("  Type 'X newname' to rename (e.g., '3 Strad' to rename #3 to 'Strad')")
        print("  Type 'npc' / 'loc' / 'obj' / 'org' to select by type")
        print(f"{'='*60}\n")
        
        response = input("Your choice: ").strip()
        
        if response.lower() in ["a", "all", ""]:
            # Accept all with original names
            for entity in all_entities:
                confirmed[entity["key"]].append({
                    "name": entity["name"],
                    "description": entity["description"],
                })
            return confirmed
        
        if response.lower() in ["n", "none"]:
            return confirmed
        
        selected = {}  # name -> new_name mapping
        
        # Parse response
        for part in response.split(","):
            part = part.strip()
            if not part:
                continue
            
            # Check for rename syntax: "X newname" or "X=newname"
            parts = part.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                # Rename case
                idx = int(parts[0]) - 1
                new_name = parts[1].strip()
                if 0 <= idx < len(all_entities):
                    old_name = all_entities[idx]["name"]
                    selected[old_name] = new_name
                    print(f"  ✓ Renamed '{old_name}' → '{new_name}'")
            elif part.lower() in ["npc", "npcs"]:
                for e in by_type.get("npc", []):
                    if e["original_name"] not in selected:
                        selected[e["original_name"]] = e["name"]
            elif part.lower() in ["loc", "locs", "locale", "locales"]:
                for e in by_type.get("locale", []):
                    if e["original_name"] not in selected:
                        selected[e["original_name"]] = e["name"]
            elif part.lower() in ["obj", "objs", "object", "objects"]:
                for e in by_type.get("object", []):
                    if e["original_name"] not in selected:
                        selected[e["original_name"]] = e["name"]
            elif part.lower() in ["org", "orgs", "organization", "organizations"]:
                for e in by_type.get("organization", []):
                    if e["original_name"] not in selected:
                        selected[e["original_name"]] = e["name"]
            elif part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(all_entities):
                    entity = all_entities[idx]
                    selected[entity["original_name"]] = entity["name"]
        
        # Build confirmed list with (possibly renamed) names
        for entity in all_entities:
            if entity["original_name"] in selected:
                final_name = selected[entity["original_name"]]
                confirmed[entity["key"]].append({
                    "name": final_name,
                    "description": entity["description"],
                })
        
        return confirmed
    
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
        """Extract entities by processing transcript in chunks."""
        # Chunk size: ~8000 chars (approx 2000 tokens) - safe for mistral:7b
        chunk_size = 8000
        overlap = 500  # Small overlap to catch entities at chunk boundaries
        
        all_entities = {
            "npcs": [],
            "locales": [],
            "objects": [],
            "organizations": []
        }
        
        if len(content) <= chunk_size:
            # Small file - process directly
            return self._extract_from_chunk(content)
        
        # Split into chunks
        chunks = []
        start = 0
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            
            # Try to break at sentence boundary (period, question mark, exclamation)
            if end < len(content):
                break_point = chunk.rfind('.')
                if break_point > chunk_size * 0.7:  # Only if we haven't gone too far
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk)
            start = end - overlap  # Overlap for continuity
        
        logger.info(f"Processing {len(chunks)} chunks from {len(content)} char transcript")
        
        # Extract from each chunk and merge
        seen_npcs = set()
        seen_locales = set()
        seen_objects = set()
        seen_orgs = set()
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            chunk_entities = self._extract_from_chunk(chunk)
            
            # Deduplicate and merge
            for npc in chunk_entities.get("npcs", []):
                if npc["name"] not in seen_npcs:
                    seen_npcs.add(npc["name"])
                    all_entities["npcs"].append(npc)
            
            for loc in chunk_entities.get("locales", []):
                if loc["name"] not in seen_locales:
                    seen_locales.add(loc["name"])
                    all_entities["locales"].append(loc)
            
            for obj in chunk_entities.get("objects", []):
                if obj["name"] not in seen_objects:
                    seen_objects.add(obj["name"])
                    all_entities["objects"].append(obj)
            
            for org in chunk_entities.get("organizations", []):
                if org["name"] not in seen_orgs:
                    seen_orgs.add(org["name"])
                    all_entities["organizations"].append(org)
        
        return all_entities
    
    def _extract_from_chunk(self, chunk: str) -> dict:
        """Extract entities from a single chunk with context."""
        prompt = f"""You are extracting D&D entities from a Polish transcript. For each entity, include a brief description based on context.

For each entity found, provide:
- name: the entity name (in Polish or original language)
- description: 1-2 sentences about this entity from the transcript (what it is, what it does, key facts)

Example:
- "Wampyr": "Ancient vampire who made a pact with Strada. Drains life from the entire land."
- "Opowieści końca": "Book about beliefs regarding how death manifests in various religions. Bound in elvish skin."
- "Monograd": "City where Koso was raised. Mentioned in an amber sarcophagus."

Extract:
- NPCs: characters, monsters, spirits (e.g., Strada, Wampyr, licz, Indul)
- Locales: places with names (e.g., Monograd, Madzina, biblioteka)
- Objects: items, books, artifacts (e.g., "Opowieści końca", "Dziennik Strada")
- Organizations: groups, factions (e.g., "Zakon Wampyra")

Output valid JSON:
{{"npcs": [{{"name": "...", "description": "..."}}], "locales": [], "objects": [], "organizations": []}}

Transcript:
{chunk}

JSON:"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])
        
        # Debug: log raw response for first chunk
        logger.debug(f"Model response preview: {response.content[:300]}...")
        
        return self._parse_entities(response.content)
    
    def _is_generic_npc(self, name: str, description: str) -> bool:
        """Check if NPC is a generic category rather than a specific named character."""
        name_lower = name.lower().strip()
        desc_lower = description.lower().strip()
        
        # Very minimal filtering - only obvious generics
        # We want to extract broadly and let user filter
        if name_lower in {"npc", "character", "person", "you", "narrator", "dm"}:
            return True
        
        return False
    
    def _is_generic_locale(self, name: str) -> bool:
        """Check if locale is a generic place rather than a specific named location."""
        name_lower = name.lower().strip()
        
        # Only filter the most generic terms
        if name_lower in {"room", "rooms", "building", "place", "area", "location"}:
            return True
        
        return False
    
    def _is_generic_object(self, name: str) -> bool:
        """Check if object is generic rather than a specific named item."""
        name_lower = name.lower().strip()
        
        # Only filter the most generic terms
        if name_lower in {"item", "object", "stuff", "something"}:
            return True
        
        return False
    
    def _filter_entities(self, entities: dict) -> dict:
        """Filter out generic entities, keeping only truly named ones."""
        filtered = {
            "npcs": [],
            "locales": [],
            "objects": [],
            "organizations": []
        }
        
        seen_npcs = set()
        seen_locales = set()
        seen_objects = set()
        seen_orgs = set()
        
        for npc in entities.get("npcs", []):
            name = npc.get("name", "")
            desc = npc.get("description", "")
            
            if name and name not in seen_npcs:
                if not self._is_generic_npc(name, desc):
                    seen_npcs.add(name)
                    filtered["npcs"].append({"name": name, "description": desc})
        
        for loc in entities.get("locales", []):
            name = loc.get("name", "")
            
            if name and name not in seen_locales:
                if not self._is_generic_locale(name):
                    seen_locales.add(name)
                    filtered["locales"].append({"name": name, "description": loc.get("description", "")})
        
        for obj in entities.get("objects", []):
            name = obj.get("name", "")
            
            if name and name not in seen_objects:
                if not self._is_generic_object(name):
                    seen_objects.add(name)
                    filtered["objects"].append({"name": name, "description": obj.get("description", "")})
        
        for org in entities.get("organizations", []):
            name = org.get("name", "")
            name_lower = name.lower().strip()
            
            if name and name not in seen_orgs:
                if name_lower not in GENERIC_ORG_PATTERNS:
                    seen_orgs.add(name)
                    filtered["organizations"].append({"name": name, "description": org.get("description", "")})
        
        return filtered
    
    def _parse_entities(self, content: str) -> dict:
        """Parse LLM output into structured dictionary."""
        entities = {
            "npcs": [],
            "locales": [],
            "objects": [],
            "organizations": []
        }
        
        # Try to extract JSON from the response
        json_str = self._extract_json(content)
        
        if not json_str:
            logger.warning("No JSON found in model response")
            return entities
            
        try:
            import json
            data = json.loads(json_str)
            
            # Handle various key formats (singular/plural, different names)
            npc_sources = ["npcs", "NPCs", "characters", "Characters", "npcs_list", "npc"]
            locale_sources = ["locales", "Locales", "locations", "Locations", "places", "Places"]
            obj_sources = ["objects", "Objects", "items", "Items", "artifacts", "Artifacts"]
            org_sources = ["organizations", "Organizations", "factions", "Factions", "guilds", "Guilds"]
            
            for key in npc_sources:
                if key in data and isinstance(data[key], list):
                    for npc in data[key]:
                        if isinstance(npc, dict):
                            name = npc.get("name", "")
                            desc = npc.get("description", "")
                        else:
                            name = str(npc)
                            desc = ""
                        if name and name not in ["You", "Karol", "you", "narrator"]:
                            entities["npcs"].append({"name": name, "description": desc})
                    break
            
            for key in locale_sources:
                if key in data and isinstance(data[key], list):
                    for loc in data[key]:
                        if isinstance(loc, dict):
                            name = loc.get("name", "")
                            desc = loc.get("description", "")
                        else:
                            name = str(loc)
                            desc = ""
                        if name:
                            entities["locales"].append({"name": name, "description": desc})
                    break
                    
            for key in obj_sources:
                if key in data and isinstance(data[key], list):
                    for obj in data[key]:
                        if isinstance(obj, dict):
                            name = obj.get("name", "")
                            desc = obj.get("description", "")
                        else:
                            name = str(obj)
                            desc = ""
                        if name:
                            entities["objects"].append({"name": name, "description": desc})
                    break
                    
            for key in org_sources:
                if key in data and isinstance(data[key], list):
                    for org in data[key]:
                        if isinstance(org, dict):
                            name = org.get("name", "")
                            desc = org.get("description", "")
                        else:
                            name = str(org)
                            desc = ""
                        if name:
                            entities["organizations"].append({"name": name, "description": desc})
                    break
            
            logger.info(f"Parsed: {len(entities['npcs'])} NPCs, {len(entities['locales'])} locales, {len(entities['objects'])} objects, {len(entities['organizations'])} orgs")
            return entities
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"JSON parse failed: {e}")
            return entities
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from model response using brace-balanced parsing."""
        import json
        
        # Remove markdown code blocks first
        content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^```\s*', '', content, flags=re.MULTILINE)
        
        # Try direct parse
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass
        
        # Find first opening brace
        start = content.find('{')
        if start == -1:
            return ""
        
        # Brace-balanced extraction - find the matching closing brace
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(content[start:], start):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found matching close brace
                    candidate = content[start:i+1]
                    try:
                        json.loads(candidate)
                        logger.debug(f"Extracted valid JSON of length {len(candidate)}")
                        return candidate
                    except json.JSONDecodeError:
                        pass
        
        # Fallback: try original heuristic
        end = content.rfind('}') + 1
        if end > start:
            candidate = content[start:end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        
        return ""
    
    def _parse_entity_line(self, line: str) -> dict:
        """Parse a single entity line."""
        try:
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
