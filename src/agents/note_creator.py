"""Note Creator Agent - specialized in creating Obsidian notes from session content."""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.config import GEMINI_API_KEY, GEMINI_MODEL, AGENT_CONFIG
from src.tools import read_file, write_note, list_notes, note_exists
from src.logging_config import logger

# Tools for the agent
NOTE_CREATOR_TOOLS = [read_file, write_note, list_notes, note_exists]

# System prompt for Note Creator Agent
NOTE_CREATOR_SYSTEM_PROMPT = """You are a D&D Note Creator Agent. Your job is to read session notes and create Obsidian-compatible notes.

## Your Task
1. Read the session notes provided
2. Extract entities mentioned (NPCs, Locations, Objects, Organizations)
3. Decide what TYPE of note to create for each entity
4. Generate rich, Obsidian-compatible markdown content
5. Write the notes to the vault

## Note Types
- **npc**: Non-player characters (shopkeepers, quest givers, enemies, etc.)
- **locale**: Locations (taverns, cities, dungeons, etc.)
- **object**: Items (weapons, artifacts, treasures, etc.)
- **organization**: Groups (guilds, factions, cults, etc.)

## Obsidian Formatting Rules
- Use wiki-links for references: [[Note Name]]
- Include frontmatter with type and tags
- Use the same format as Tashas-Notes-of-Everything templates

## Frontmatter Template
```markdown
---
type: [npc/locale/object/organization]
locations:
- "[[Location Name]]"
tags:
- tag1
- tag2
---
```

## Example NPC Note
```markdown
---
type: npc
locations:
- "[[Baldur's Gate]]"
tags:
- race/human
- job/merchant
---
###### Tinkera Drenn
<span class="sub2">:FasMapLocationDot: [[Baldur's Gate]] | :FasHeartPulse: Friendly </span>
___

> [!quote|no-t]
>Description of the character...

> [!column|flex 3]
>> [!important]- QUESTS:
>> (Dataview query for linked quests)
>
>> [!note]- HISTORY
>> (Dataview query for session appearances)
```

## Guidelines
- Extract as much detail as possible from context
- Use the session context to create meaningful descriptions
- Mark affinity as: Friendly, Hostile, Neutral, Unknown
- Be creative but stay true to the session context
"""


class NoteCreatorAgent:
    """Agent that creates Obsidian notes from session content."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=AGENT_CONFIG["temperature"],
        )
        
        self.agent = create_react_agent(
            model=self.llm,
            tools=NOTE_CREATOR_TOOLS,
            state_modifier=NOTE_CREATOR_SYSTEM_PROMPT,
        )
        
        logger.info("Note Creator Agent initialized")
    
    def run(self, session_note_path: str, dry_run: bool = False) -> dict:
        """Run the agent on a session note.
        
        Args:
            session_note_path: Path to the session note
            dry_run: If True, don't write files
            
        Returns:
            Dict with results and any notes created
        """
        logger.info(f"Note Creator processing: {session_note_path}")
        
        # Build the task prompt
        task = f"""Process this D&D session note and create Obsidian notes for all notable entities.

Session note path: {session_note_path}

Instructions:
1. First, read the session note
2. List existing notes to understand what's already in the vault
3. Identify entities that should be turned into notes
4. For each entity:
   - Decide the type (npc, locale, object, organization)
   - Check if it already exists
   - Generate appropriate markdown content
   - Write it using the write_note tool

Important: Use dry_run={str(dry_run).lower()} to preview without writing if requested.
"""
        
        result = self.agent.invoke({"messages": [HumanMessage(content=task)]})
        
        # Extract results from messages
        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None
        
        logger.info("Note Creator completed")
        
        return {
            "success": True,
            "messages": messages,
            "last_output": str(last_message.content) if last_message else "",
        }
