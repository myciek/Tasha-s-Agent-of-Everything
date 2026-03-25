"""Manager Agent - decides which worker to spawn based on task."""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import AGENT_CONFIG
from src.logging_config import logger
from src.agents.note_creator import NoteCreatorAgent


class ManagerAgent:
    """Manager agent that decides which worker to spawn."""
    
    def __init__(self, model: str = "mistral:7b"):
        self.llm = ChatOllama(
            model=model,
            temperature=0.3,
        )
        
        # Initialize workers
        self.note_creator = NoteCreatorAgent(model=model)
        
        logger.info(f"Manager Agent initialized with model: {model}")
    
    def run(self, task: str, dry_run: bool = False) -> dict:
        """Process a task and spawn appropriate worker."""
        logger.info(f"Manager processing task: {task}")
        
        # Extract filename from task
        filename = task
        if "process" in task.lower():
            parts = task.split()
            for part in parts:
                if part.endswith(".md"):
                    filename = part
                    break
        
        # Always spawn Note Creator
        result = self.note_creator.run(
            session_note_path=filename,
            dry_run=dry_run
        )
        
        # Format response
        if result.get("success"):
            notes = result.get("notes_created", [])
            count = result.get("count", 0)
            
            if dry_run:
                msg = f"Would create {count} notes:\n"
                msg += "\n".join(f"  - {n}" for n in notes)
            else:
                msg = f"Created {count} notes:\n"
                msg += "\n".join(f"  - {n}" for n in notes)
            
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
