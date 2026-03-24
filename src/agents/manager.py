"""Manager Agent - decides which worker to spawn based on task."""

from typing import Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import GEMINI_API_KEY, GEMINI_MODEL, AGENT_CONFIG
from src.logging_config import logger
from src.agents.note_creator import NoteCreatorAgent


class ManagerAgent:
    """Manager agent that decides which worker to spawn."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=0.3,  # Lower temp for decision-making
        )
        
        # Initialize workers
        self.note_creator = NoteCreatorAgent()
        
        logger.info("Manager Agent initialized")
    
    def run(self, task: str, dry_run: bool = False) -> dict:
        """Process a task and spawn appropriate worker.
        
        Args:
            task: The task description
            dry_run: Whether to run in dry-run mode
            
        Returns:
            Dict with results from the spawned worker
        """
        logger.info(f"Manager processing task: {task}")
        
        # For MVP, always spawn Note Creator
        # In the future, we can add logic here to route to different workers
        worker_decision = self._decide_worker(task)
        
        if worker_decision == "note_creator":
            logger.info("Spawning Note Creator Agent")
            result = self.note_creator.run(
                session_note_path=task,
                dry_run=dry_run
            )
            return {
                "worker": "note_creator",
                "success": True,
                **result
            }
        else:
            return {
                "success": False,
                "error": f"Unknown worker type: {worker_decision}"
            }
    
    def _decide_worker(self, task: str) -> str:
        """Decide which worker to spawn based on the task.
        
        For MVP, this always returns note_creator.
        In the future, this can be expanded to route to different workers.
        """
        # MVP: Always use Note Creator
        # Future: Add logic like:
        # - "combat log" -> combat_worker
        # - "track quests" -> quest_worker
        # - "session notes" -> note_creator
        
        task_lower = task.lower()
        
        if "session" in task_lower or "note" in task_lower or ".md" in task_lower:
            return "note_creator"
        
        # Default to note creator for MVP
        return "note_creator"
    
    def chat(self, message: str, dry_run: bool = False) -> str:
        """Chat interface for the manager.
        
        Args:
            message: User message describing what they want
            dry_run: Whether to run in dry-run mode
            
        Returns:
            Response from the agent
        """
        logger.info(f"Manager chat: {message}")
        
        # Check if this is a task to process
        if "session" in message.lower() or ".md" in message:
            result = self.run(task=message, dry_run=dry_run)
            return result.get("last_output", "Task completed")
        
        # Otherwise, use the LLM to respond
        response = self.llm.invoke([
            SystemMessage(content="""You are a helpful D&D campaign assistant manager.
            
You can help with:
- Processing session notes to create Obsidian notes
- Understanding D&D lore
- Managing campaign information

Keep responses concise and helpful."""),
            HumanMessage(content=message)
        ])
        
        return response.content
