"""Note Creator Agent - creates Obsidian notes from model output."""

import re
from pathlib import Path

from langchain_ollama import ChatOllama

from src.config import AGENT_CONFIG, VAULT_PATH, NOTE_OUTPUT_PATHS
from src.logging_config import logger


class NoteCreatorAgent:
    """Agent that creates Obsidian notes from session content."""
    
    def __init__(self, model: str = "mistral:7b"):
        self.llm = ChatOllama(
            model=model,
            temperature=AGENT_CONFIG["temperature"],
        )
        
        logger.info(f"Note Creator Agent initialized with model: {model}")
    
    def run(self, session_note_path: str, dry_run: bool = False) -> dict:
        """Run the agent on a session note."""
        logger.info(f"Note Creator processing: {session_note_path}")
        
        # Read the session note
        content = self._read_session_note(session_note_path)
        if not content:
            return {"success": False, "error": f"Could not read: {session_note_path}"}
        
        # Improved prompt - very explicit format
        prompt = f"""You are a D&D world-building assistant. Read the session notes below and extract important entities.

For EACH entity you find, output EXACTLY this format on separate lines:

[NPC]
name: <character name>
description: <brief description of who they are>

[LOCALE]
name: <location name>
description: <brief description of the place>

[OBJECT]
name: <item name>
description: <brief description of the item>

[ORGANIZATION]
name: <group name>
description: <brief description of the organization>

Rules:
- Output one entity per block
- Use the EXACT labels shown above: [NPC], [LOCALE], [OBJECT], [ORGANIZATION]
- The "name:" and "description:" must be on separate lines
- Include as many entities as you find
- If no entities of a type exist, skip that type entirely

SESSION NOTES:
{content}

Extract all entities now. Write ONLY the entity blocks, nothing else:"""

        response = self.llm.invoke([
            {"role": "user", "content": prompt}
        ])
        
        # Parse notes
        notes = self._parse_notes(response.content)
        
        if not notes:
            logger.warning("No notes extracted")
            return {
                "success": True,
                "notes_created": [],
                "message": "Could not parse notes"
            }
        
        # Write notes
        created = []
        for note in notes:
            if dry_run:
                created.append(f"[DRY RUN] {note['name']}")
            else:
                if self._write_note(note):
                    created.append(note['name'])
        
        logger.info(f"Created {len(created)} notes")
        
        return {
            "success": True,
            "notes_created": created,
            "count": len(created),
        }
    
    def _read_session_note(self, path: str) -> str:
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
    
    def _parse_notes(self, content: str) -> list:
        notes = []
        
        # Split into blocks by entity type headers
        blocks = re.split(r'\[(NPC|LOCALE|OBJECT|ORGANIZATION)\]', content)
        
        for i in range(1, len(blocks), 2):
            entity_type = blocks[i].lower()
            entity_data = blocks[i + 1] if i + 1 < len(blocks) else ""
            
            if entity_type == "npc":
                note_type = "npc"
            elif entity_type == "locale":
                note_type = "locale"
            elif entity_type == "object":
                note_type = "object"
            elif entity_type == "organization":
                note_type = "organization"
            else:
                continue
            
            # Extract name and description
            name_match = re.search(r'name:\s*(.+?)(?:\n|$)', entity_data, re.IGNORECASE)
            desc_match = re.search(r'description:\s*(.+?)(?:\n\n|\[|$)', entity_data, re.IGNORECASE | re.DOTALL)
            
            if name_match:
                name = name_match.group(1).strip()
                desc = desc_match.group(1).strip() if desc_match else ""
                
                # Create note with template
                note_content = self._build_note_content(note_type, name, desc)
                
                notes.append({
                    "note_type": note_type,
                    "name": name,
                    "content": note_content
                })
        
        logger.info(f"Parsed {len(notes)} notes")
        return notes
    
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
>> >     filters:
>> >       and:
>> >         - file.inFolder("Compendium/Atlas")
>> >         - locations.contains(this.file)
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
>> >     filters:
>> >       and:
>> >         - file.inFolder("Session Notes")
>> >         - file.hasLink(this.file)
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
>> >     filters:
>> >       and:
>> >         - file.inFolder("Session Notes")
>> >         - file.hasLink(this.file)
>> > ```
"""
        }
        
        return templates.get(note_type, templates["npc"])
    
    def _write_note(self, note: dict) -> bool:
        note_type = note.get("note_type")
        name = note.get("name", "Untitled")
        content = note.get("content", "")
        
        if note_type not in NOTE_OUTPUT_PATHS:
            return False
        
        output_dir = VAULT_PATH / NOTE_OUTPUT_PATHS[note_type]
        output_path = output_dir / f"{name}.md"
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            logger.info(f"Created: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
