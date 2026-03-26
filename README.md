# Tasha's Agent of Everything

An **agentic API** that transforms your D&D session transcripts into organized Obsidian notes. Built with LangChain + Ollama (mistral:7b).

## What It Does

1. **Records/Transcribes** - Use a Discord bot (like DiscMeet) to record sessions
2. **Extracts Entities** - Automatically identifies NPCs, locations, objects, and organizations from Polish (or any language) transcripts
3. **Creates Notes** - Generates Obsidian notes matching your template format with wiki-links between related entities

## Features

- **Chunked Processing** - Handles long transcripts (3+ hour sessions)
- **Interactive Confirmation** - Review, rename, and merge entities before creating notes
- **Polish Support** - Works with Polish D&D sessions out of the box
- **Wiki-Links** - Auto-creates `[[wiki-links]]` between related entities
- **Obsidian Compatible** - Notes match the [Tasha's Notes of Everything](https://github.com/kevinkickback/Tashas-Notes-of-Everything) vault format

## Quick Start

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) installed
- mistral:7b model: `ollama pull mistral:7b`
- Obsidian vault (like [Tasha's Notes of Everything](https://github.com/kevinkickback/Tashas-Notes-of-Everything))

### 2. Install

```bash
git clone https://github.com/myciek/Tasha-s-Agent-of-Everything.git
cd Tasha-s-Agent-of-Everything
pip install -r requirements.txt
```

### 3. Configure

Create `.env` file:
```env
OBSIDIAN_VAULT_PATH=C:\Users\YourName\Documents\Tashas-Notes-of-Everything
```

### 4. Run

```bash
# Process a transcript with interactive confirmation
python -m src.main "session-transcript.txt" --confirm

# Dry run (preview without creating files)
python -m src.main "session-transcript.txt" --confirm --dry-run

# Verbose logging
python -m src.main "session-transcript.txt" --confirm -v
```

## Interactive Commands

When using `--confirm`:

```
Found 25 entities. Selected: 25
============================================================
NPCS (12):
  [1] ✓ Strada
  [2] ✓ Wampyr
  ...

Commands:
  Enter numbers to toggle (e.g., 1,3,5)
  'r X newname' - rename #X to newname (e.g., 'r 3 Strad')
  'm X Y' - merge X into Y (e.g., 'm 1 2' - keep 2, delete 1)
  'done' or 'd' - finish and create notes
  'cancel' or 'c' - cancel everything
```

## Workflow

1. **Record Session** - Use Discord bot (DiscMeet) to transcribe your voice chat
2. **Save Transcript** - Export as `.txt` file
3. **Run Agent** - `python -m src.main "transcript.txt" --confirm`
4. **Review & Confirm** - Rename duplicates (licz/Licz), toggle entities, merge similar ones
5. **Done** - Notes appear in your Obsidian vault

## Project Structure

```
src/
├── agents/
│   ├── transcriber.py   # Extracts entities from transcripts
│   ├── note_creator.py  # Creates Obsidian notes
│   └── manager.py      # Orchestrates the workflow
├── config/             # Configuration
├── cli.py              # Command-line interface
└── discord_bot.py      # Discord bot (optional)
```

## Example Output

For a character "Strada" mentioned in a Polish session:

```markdown
###### Strada
> [!quote|no-t]
> Mocny czarnoksiężnik, który zawarł pakt z [[Wampyr]] i stał się jego heraldem.

> [!example]- POWIĄZANE / RELATED
> - [[Wampyr]]
```

## Discord Integration (Optional)

For voice recording, use [DiscMeet](https://discmeet.com/) bot - it supports Polish and exports transcripts.

The included `discord_bot.py` provides:
- `/voice join` - Join voice channel
- `/voice leave` - Leave voice channel  
- `/transcribe` - Transcribe recorded audio

## Requirements

- langchain-ollama
- discord.py
- python-dotenv
- ollama running locally

## License

MIT
