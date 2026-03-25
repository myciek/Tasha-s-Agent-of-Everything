"""Manager Agent - decides which worker to spawn based on task."""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import AGENT_CONFIG, DEFAULT_MODEL
from src.logging_config import logger
from src.agents.transcriber import TranscriberAgent
from src.agents.note_creator import NoteCreatorAgent


class ManagerAgent:
    """Manager agent that decides which worker to spawn."""
    
    def __init__(self, model: str = DEFAULT_MODEL):
        self.llm = ChatOllama(
            model=model,
            temperature=0.3,
        )
        
        # Workers
        self.transcriber = TranscriberAgent(model=model)
        self.note_creator = NoteCreatorAgent()
        
        logger.info(f"Manager Agent initialized with model: {model}")
    
    def run(self, task: str, dry_run: bool = False) -> dict:
        """Process a task by spawning appropriate workers."""
        logger.info(f"Manager processing task: {task}")
        
        # Determine what needs to be done
        action = self._decide_action(task)
        
        if action == "transcribe_only":
            # Just transcribe
            result = self.transcriber.run(task)
            return self._format_result(result, "Transcribed")
        
        elif action == "create_notes_only":
            # Just create notes from existing JSON
            result = self.note_creator.run(dry_run=dry_run)
            return self._format_result(result, "Created notes")
        
        elif action == "full_pipeline":
            # Transcribe then create notes
            logger.info("Running full pipeline: transcribe -> create notes")
            
            # Step 1: Transcribe
            transcribe_result = self.transcriber.run(task)
            if not transcribe_result.get("success"):
                return {
                    "success": False,
                    "error": f"Transcription failed: {transcribe_result.get('error')}"
                }
            
            logger.info(f"Extracted {transcribe_result.get('total_extracted', 0)} entities")
            
            # Step 2: Create notes
            notes_result = self.note_creator.run(dry_run=dry_run)
            notes_result["transcription"] = transcribe_result
            
            return self._format_result(notes_result, "Processed")
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }
    
    def _decide_action(self, task: str) -> str:
        """Use LLM to decide what action to take."""
        task_lower = task.lower()
        
        # Simple keyword-based decision for now
        if "transcribe" in task_lower:
            return "transcribe_only"
        elif "create notes" in task_lower or "create-notes" in task_lower:
            return "create_notes_only"
        elif ".md" in task or "session" in task_lower or "transcript" in task_lower:
            # Default: full pipeline for session files
            return "full_pipeline"
        else:
            # Default to full pipeline
            return "full_pipeline"
    
    def _format_result(self, result: dict, action: str) -> dict:
        """Format result for display."""
        if result.get("success"):
            count = result.get("count", 0) or result.get("total_extracted", 0)
            notes = result.get("notes_created", [])
            
            if notes:
                msg = f"{action} {count} items:\n"
                msg += "\n".join(f"  - {n}" for n in notes[:10])
                if len(notes) > 10:
                    msg += f"\n  ... and {len(notes) - 10} more"
            else:
                msg = f"{action} successfully"
            
            result["message"] = msg
        
        return result
    
    def chat(self, message: str, dry_run: bool = False) -> str:
        """Chat interface for the manager."""
        logger.info(f"Manager chat: {message}")
        
        # If it looks like a file/path, process it
        if ".md" in message or "process" in message.lower():
            result = self.run(task=message, dry_run=dry_run)
            return result.get("message", "Task completed")
        
        # Otherwise, use the LLM to respond
        response = self.llm.invoke([
            SystemMessage(content="You are a D&D campaign assistant. Help users manage their campaign notes."),
            HumanMessage(content=message)
        ])
        
        return response.content
