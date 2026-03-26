"""CLI for D&D Note Generation Agent."""

import argparse
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.agents import ManagerAgent
from src.logging_config import logger, setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="D&D Note Generation Agent - Process session notes into Obsidian notes"
    )
    
    parser.add_argument(
        "session_note",
        nargs="?",
        help="Path to the session note (or session note name)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without writing files"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start chat mode"
    )
    
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Ask to confirm entities before creating notes"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(verbose=args.verbose)
    
    # Initialize agent
    logger.info("Initializing Manager Agent...")
    manager = ManagerAgent()
    
    if args.chat:
        # Chat mode
        print("\n🎲 D&D Note Agent - Chat Mode")
        print("Type 'exit' or 'quit' to stop\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ["exit", "quit", "q"]:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                response = manager.chat(user_input, dry_run=args.dry_run)
                print(f"\nAgent: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
    
    elif args.session_note:
        # Process session note
        logger.info(f"Processing: {args.session_note}")
        print(f"\n🎲 Processing: {args.session_note}")
        
        if args.dry_run:
            print("📝 DRY RUN MODE - No files will be written\n")
        
        result = manager.run(args.session_note, dry_run=args.dry_run, confirm=args.confirm)
        
        if result.get("success"):
            print("\n✅ Task completed!")
            if result.get("last_output"):
                print(f"\n{result['last_output']}")
        else:
            print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    else:
        # No arguments, show help
        parser.print_help()
        print("\n" + "="*50)
        print("Example usage:")
        print("  python -m src.cli \"Session 01.md\"")
        print("  python -m src.cli \"Session 01.md\" --dry-run")
        print("  python -m src.cli --chat")


if __name__ == "__main__":
    main()
