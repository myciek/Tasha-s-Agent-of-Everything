"""Note Creator Agent - creates Obsidian notes from extracted entities (JSON)."""

import json
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
        
        # Build notes from entities
        notes = []
        
        for npc in entities.get("npcs", []):
            notes.append({
                "note_type": "npc",
                "name": npc.get("name", "Unknown"),
                "description": npc.get("description", "")
            })
        
        for locale in entities.get("locales", []):
            notes.append({
                "note_type": "locale",
                "name": locale.get("name", "Unknown"),
                "description": locale.get("description", "")
            })
        
        for obj in entities.get("objects", []):
            notes.append({
                "note_type": "object",
                "name": obj.get("name", "Unknown"),
                "description": obj.get("description", "")
            })
        
        for org in entities.get("organizations", []):
            notes.append({
                "note_type": "organization",
                "name": org.get("name", "Unknown"),
                "description": org.get("description", "")
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
    
    def _write_note(self, note: dict) -> bool:
        """Write a single note to the vault."""
        note_type = note.get("note_type")
        name = note.get("name", "Untitled")
        description = note.get("description", "")
        
        if note_type not in NOTE_OUTPUT_PATHS:
            return False
        
        content = self._build_note_content(note_type, name, description)
        
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
    
    def _build_note_content(self, note_type: str, name: str, description: str) -> str:
        """Build markdown content matching Obsidian Templater templates."""
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
> Profile of {name}, the NPC. {description}

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
>Description of the locale {name}. {description}

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
>
>> [!example]- LOCATIONS
>> > ```base
>> > properties:
>> >   file.name:
>> >     displayName: Name
>> > views:
>> >   - type: table
>> >     name: Landmarks
>> >   filters:
>> >     and:
>> >       - file.inFolder("Compendium/Atlas")
>> >       - locations.contains(this.file)
>> > ```
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
            "object": f"""---
type: object
tags:
  - object/unknown
---

###### {name}
<span class="sub2">:FasCircleQuestion: Unknown Type</span>
___

> [!quote|no-t]
>![[embed.jpg|right wm-sm]]Description of the object, {name}. {description}
<span class="clearfix"></span>

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
