"""Note Creator Agent - creates Obsidian notes from extracted entities (JSON)."""

import json
import re
from pathlib import Path

from src.config import EXTRACTED_ENTITIES_FILE, VAULT_PATH, NOTE_OUTPUT_PATHS
from src.logging_config import logger


class NoteCreatorAgent:
    """Agent that creates Obsidian notes from shared JSON entity data."""
    
    def run(self, dry_run: bool = False) -> dict:
        """Create notes from the shared extracted entities JSON."""
        logger.info(f"Note Creator reading from: {EXTRACTED_ENTITIES_FILE}")
        
        # Read shared JSON
        entities_data = self._read_shared_json()
        if not entities_data:
            return {
                "success": False,
                "error": f"Could not read: {EXTRACTED_ENTITIES_FILE}"
            }
        
        entities = entities_data.get("entities", {})
        session_id = entities_data.get("session_id", "unknown")
        
        # Collect all entity names for wiki-linking (excluding self-references)
        all_entities = []
        for npc in entities.get("npcs", []):
            all_entities.append({"name": npc.get("name", ""), "type": "npc"})
        for loc in entities.get("locales", []):
            all_entities.append({"name": loc.get("name", ""), "type": "locale"})
        for obj in entities.get("objects", []):
            all_entities.append({"name": obj.get("name", ""), "type": "object"})
        for org in entities.get("organizations", []):
            all_entities.append({"name": org.get("name", ""), "type": "org"})
        
        # Build notes from entities
        notes = []
        
        for npc in entities.get("npcs", []):
            desc = npc.get("description", "")
            links = npc.get("links", [])
            entity_name = npc.get("name", "Unknown")
            # Auto-detect entity names in description and create wiki-links
            desc, detected_links = self._auto_wiki_links(desc, entity_name, all_entities)
            # Combine with explicit links
            all_links = list(set(links + detected_links))
            notes.append({
                "note_type": "npc",
                "name": entity_name,
                "description": desc,
                "links": all_links,
            })
        
        for locale in entities.get("locales", []):
            desc = locale.get("description", "")
            links = locale.get("links", [])
            entity_name = locale.get("name", "Unknown")
            desc, detected_links = self._auto_wiki_links(desc, entity_name, all_entities)
            all_links = list(set(links + detected_links))
            notes.append({
                "note_type": "locale",
                "name": entity_name,
                "description": desc,
                "links": all_links,
            })
        
        for obj in entities.get("objects", []):
            desc = obj.get("description", "")
            links = obj.get("links", [])
            entity_name = obj.get("name", "Unknown")
            desc, detected_links = self._auto_wiki_links(desc, entity_name, all_entities)
            all_links = list(set(links + detected_links))
            notes.append({
                "note_type": "object",
                "name": entity_name,
                "description": desc,
                "links": all_links,
            })
        
        for org in entities.get("organizations", []):
            desc = org.get("description", "")
            links = org.get("links", [])
            entity_name = org.get("name", "Unknown")
            desc, detected_links = self._auto_wiki_links(desc, entity_name, all_entities)
            all_links = list(set(links + detected_links))
            notes.append({
                "note_type": "organization",
                "name": entity_name,
                "description": desc,
                "links": all_links,
            })
        
        if not notes:
            logger.warning("No entities found in shared data")
            return {
                "success": True,
                "notes_created": [],
                "message": "No entities to create notes from"
            }
        
        # Create notes
        created = []
        for note in notes:
            if dry_run:
                created.append(f"[DRY RUN] {note['note_type']}: {note['name']}")
            else:
                if self._write_note(note):
                    created.append(note['name'])
        
        logger.info(f"Created {len(created)} notes for session {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "notes_created": created,
            "count": len(created),
        }
    
    def _read_shared_json(self) -> dict:
        """Read entities from shared JSON file."""
        if not EXTRACTED_ENTITIES_FILE.exists():
            logger.error(f"Shared file not found: {EXTRACTED_ENTITIES_FILE}")
            return {}
        
        try:
            return json.loads(EXTRACTED_ENTITIES_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read shared JSON: {e}")
            return {}
    
    def _add_wiki_links(self, description: str, links: list, all_names: set) -> str:
        """Convert linked entity names to Obsidian wiki-links [[name]]."""
        if not links:
            return description
        
        result = description
        for link_name in links:
            # Case-insensitive replacement to handle "Strada" → "[[Strada]]"
            pattern = re.compile(re.escape(link_name), re.IGNORECASE)
            result = pattern.sub(f"[[{link_name}]]", result)
        
        return result
    
    def _auto_wiki_links(self, description: str, current_name: str, all_entities: list) -> tuple:
        """Auto-detect entity names in description and convert to wiki-links.
        
        Returns: (description_with_links, list_of_detected_links)
        """
        if not description:
            return description, []
        
        result = description
        detected_links = []
        
        # Sort by length (longer names first) to avoid partial matches
        sorted_entities = sorted(
            [e for e in all_entities if e["name"] and e["name"].lower() != current_name.lower()],
            key=lambda x: len(x["name"]),
            reverse=True
        )
        
        for entity in sorted_entities:
            name = entity["name"]
            name_lower = name.lower()
            
            # Try exact word boundary match first
            pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            
            if pattern.search(result):
                if f"[[{name}]]" not in result.lower():
                    result = pattern.sub(f"[[{name}]]", result)
                    detected_links.append(name)
                continue
            
            # Try matching name without last 2-3 chars (handles Polish case endings)
            # e.g., "wampirem" contains "wampir" which is related to "Wampyr"
            for suffix_len in [2, 3, 4]:
                if len(name) > suffix_len + 3:
                    base_name = name[:-suffix_len].lower()
                    # Find word that starts with base_name
                    pattern2 = re.compile(r'\b' + re.escape(base_name) + r'\w*', re.IGNORECASE)
                    match = pattern2.search(result)
                    if match and f"[[{name}]]" not in result.lower():
                        matched_text = match.group()
                        # Replace with wiki-link
                        result = result[:match.start()] + f"[[{name}]]" + result[match.end():]
                        detected_links.append(name)
                        break
        
        return result, detected_links
    
    def _write_note(self, note: dict) -> bool:
        """Write a single note to the vault."""
        note_type = note.get("note_type")
        name = note.get("name", "Untitled")
        description = note.get("description", "")
        links = note.get("links", [])
        
        if note_type not in NOTE_OUTPUT_PATHS:
            return False
        
        content = self._build_note_content(note_type, name, description, links)
        
        output_dir = VAULT_PATH / NOTE_OUTPUT_PATHS[note_type]
        output_path = output_dir / f"{name}.md"
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            logger.info(f"Created: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing note: {e}")
            return False
    
    def _build_note_content(self, note_type: str, name: str, description: str, links: list = None) -> str:
        """Build markdown content matching Obsidian Templater templates."""
        links = links or []
        
        # Build related links section if there are links
        related_section = ""
        if links:
            link_items = "".join([f"- [[{link}]]\n" for link in links])
            related_section = f"""
> [!example]- POWIĄZANE / RELATED
> {link_items}"""
        
        templates = {
            "npc": f"""---
type: npc
locations:
  - "[[Unknown]]"
tags:
  - race/unknown
---

###### {name}
<span class="sub2">:FasMapLocationDot: [[Unknown]] &nbsp; | &nbsp; :FasHeartPulse: Unknown </span>
___

> [!infobox|no-t right]
> ![[portrait.jpg]]
> ###### Details:
> | Type | Stat |
> | ---- | ---- |
> | :FasBriefcase: Job | <!-- Fill in --> |
> | :FasVenusMars: Gender | <!-- Fill in --> |
> | :FasUser: Race | <!-- Fill in --> |
<span class="clearfix"></span>

> [!quote|no-t]
> {description}{related_section}

> [!column|flex 3]
>> [!important]- QUESTS:
>> ```base
>> properties:
>>   file.name:
>>     displayName: Name
>> views:
>>   - type: table
>>     name: Name
>>     filters:
>>       and:
>>         - file.inFolder("Compendium/Party/Quests")
>>         - file.hasLink(this.file)
>>     order:
>>       - file.name
>> ```
>
>> [!note]- HISTORY
>> > ```base
>> > properties:
>> >   file.name:
>> >     displayName: Name
>> > views:
>> >   - type: table
>> >     name: Session Notes
>> >     filters:
>> >       and:
>> >         - file.inFolder("Session Notes")
>> >         - file.hasLink(this.file)
>> > ```
""",
            "locale": f"""---
type: locale
locations:
  - "[[Unknown]]"
tags:
  - location/unknown
---

![[banner.jpg|banner]]
###### {name}
<span class="sub2">:FasCircleQuestion: Unknown Type</span>
___

> [!quote|no-t] SUMMARY
>{description}

{related_section if related_section else ""}
> [!column|flex 3]
> > [!hint]- NPC's
> > ```base
> > formulas:
> >   LinkedIndirectly: |
> >     locations.contains(this.file)
> >     || list(locations)
> >          .filter(file(value)
> >            && list(file(value).properties.locations).contains(this))
> >          .length > 0
> > 
> > properties:
> >   file.name:
> >     displayName: Name
> > 
> > views:
> >   - type: table
> >     name: This Location Only
> >     filters:
> >       and:
> >         - file.inFolder("Compendium/NPC's")
> >         - locations.contains(this.file)
> > 
> >   - type: table
> >     name: Sub-Locations Included
> >     filters:
> >       and:
> >         - file.inFolder("Compendium/NPC's")
> >         - formula.LinkedIndirectly
> > ```
> >
> >> [!example]- LOCATIONS
> >> > ```base
> >> > properties:
> >> >   file.name:
> >> >     displayName: Name
> >> > views:
> >> >   - type: table
> >> >     name: Landmarks
> >> >   filters:
> >> >     and:
> >> >       - file.inFolder("Compendium/Atlas")
> >> >       - locations.contains(this.file)
> >> > ```
> >
> >> [!note]- HISTORY
> >> > ```base
> >> > properties:
> >> >   file.name:
> >> >     displayName: Name
> >> > views:
> >> >   - type: table
> >> >     name: Session Notes
> >> >     filters:
> >> >       and:
> >> >         - file.inFolder("Session Notes")
> >> >         - file.hasLink(this.file)
> >> > ```
> """,
            "object": f"""---
type: object
tags:
  - object/unknown
---

###### {name}
<span class="sub2">:FasCircleQuestion: Unknown Type</span>
___

> [!quote|no-t]
>![[embed.jpg|right wm-sm]]{description}
<span class="clearfix"></span>

{related_section}

> [!column|flex 3]
> > [!hint]- NPC's
> > ```base
> > properties:
> >   file.name:
> >     displayName: Name
> > views:
> >   - type: table
> >     name: Name
> >     filters:
> >       and:
> >         - file.inFolder("Compendium/NPC's")
> >         - file.hasLink(this.file)
> > ```
>
>> [!note]- HISTORY
>> > ```base
>> > properties:
>> >   file.name:
>> >     displayName: Name
>> > views:
>> >   - type: table
>> >     name: Session Notes
>> >   filters:
>> >     and:
>> >       - file.inFolder("Session Notes")
>> >       - file.hasLink(this.file)
>> > ```
""",
            "organization": f"""---
type: organization
locations:
  - "[[Unknown]]"
tags:
  - 
---

###### {name}
<span class="sub2">:FasSitemap: Organization</span>
___

> [!quote|no-t]
>![[embed.jpg|right wm-sm]]Profile of {name}, the <!-- Fill in alignment --> aligned organization. {description}

> [!column|flex 3]
> > [!hint]- NPC's
> > ```base
> > properties:
> >   file.name:
> >     displayName: Name
> > views:
> >   - type: table
> >     name: Name
> >     filters:
> >       and:
> >         - file.inFolder("Compendium/NPC's")
> >         - file.hasLink(this.file)
> > ```
>
>> [!note]- HISTORY
>> > ```base
>> > properties:
>> >   file.name:
>> >     displayName: Name
>> > views:
>> >   - type: table
>> >     name: Session Notes
>> >   filters:
>> >     and:
>> >       - file.inFolder("Session Notes")
>> >       - file.hasLink(this.file)
>> > ```
"""
        }
        
        return templates.get(note_type, templates["npc"])
