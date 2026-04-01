"""
Context Compaction CLI Commands
Integration with OpenClaw slash commands
"""

import json
from typing import Optional
from .engine import CompactionEngine, CompactionConfig, CompactionResult
from .storage import CompactionStorage, CompactionRecord


class CompactionCLI:
    """CLI integration for context compaction"""
    
    def __init__(self, config: Optional[CompactionConfig] = None):
        self.engine = CompactionEngine(config)
        self.storage = None  # Initialize on demand
        
    def _get_storage(self):
        if not self.storage:
            self.storage = CompactionStorage()
            self.storage.connect()
        return self.storage
    
    def cmd_compact(
        self,
        messages: list,
        session_id: str,
        mode: str = "manual",
        keep_recent: Optional[int] = None
    ) -> dict:
        """
        Handle /compact command
        
        Usage: /compact [auto|manual] [--keep-recent N]
        """
        config = self.engine.config
        if keep_recent:
            config.keep_recent = keep_recent
            
        compacted, result = self.engine.compact(messages, session_id)
        
        # Save to storage
        try:
            storage = self._get_storage()
            record = CompactionRecord(
                session_id=result.session_id,
                original_tokens=result.original_tokens,
                compacted_tokens=result.compacted_tokens,
                tokens_saved=result.tokens_saved,
                savings_percentage=result.savings_percentage,
                messages_compacted=result.messages_compacted,
                messages_kept=result.messages_kept,
                timestamp=result.timestamp,
                strategy=result.strategy
            )
            storage.save(record)
        except Exception:
            pass  # Storage is optional
            
        return {
            "success": True,
            "compacted_messages": compacted,
            "result": {
                "tokens_saved": result.tokens_saved,
                "savings_percentage": result.savings_percentage,
                "messages_compacted": result.messages_compacted,
                "messages_kept": result.messages_kept,
                "summary": result.summary
            }
        }
    
    def cmd_estimate(self, messages: list) -> dict:
        """
        Handle /estimate command
        
        Usage: /estimate
        """
        analysis = self.engine.analyze(messages)
        
        return {
            "success": True,
            "tokens": analysis["tokens"].total,
            "limit": analysis["limit"],
            "usage_percentage": analysis["usage"]["percentage"],
            "needs_compaction": analysis["needs_compaction"],
            "ranking": analysis["ranking"]
        }
    
    def cmd_stats(self) -> dict:
        """
        Handle /stats command
        
        Usage: /stats
        """
        try:
            storage = self._get_storage()
            stats = storage.get_stats()
        except Exception:
            stats = {"error": "Storage not available"}
            
        return {
            "success": True,
            "stats": stats
        }
    
    def cmd_config(self, key: Optional[str] = None, value: Optional[str] = None) -> dict:
        """
        Handle /config command
        
        Usage: /config [key [value]]
        """
        config = self.engine.config
        
        if key is None:
            # Show all config
            return {
                "success": True,
                "config": {
                    "model": config.model,
                    "max_context_percentage": config.max_context_percentage,
                    "keep_recent": config.keep_recent,
                    "strategy": config.strategy,
                    "enable_summarization": config.enable_summarization,
                    "min_savings_percentage": config.min_savings_percentage
                }
            }
        
        # Set value
        if hasattr(config, key):
            if key in ["max_context_percentage", "min_savings_percentage"]:
                setattr(config, key, float(value))
            elif key in ["keep_recent", "enable_summarization"]:
                if value.lower() in ["true", "1"]:
                    setattr(config, key, True)
                elif value.lower() in ["false", "0"]:
                    setattr(config, key, False)
                else:
                    setattr(config, key, int(value))
            else:
                setattr(config, key, value)
            
            return {
                "success": True,
                "message": f"Set {key} = {value}"
            }
        
        return {
            "success": False,
            "error": f"Unknown config key: {key}"
        }


# CLI command router
def handle_command(command: str, args: list, messages: list, session_id: str) -> dict:
    """Route CLI commands"""
    cli = CompactionCLI()
    
    commands = {
        "compact": lambda: cli.cmd_compact(messages, session_id, *args),
        "estimate": lambda: cli.cmd_estimate(messages),
        "stats": lambda: cli.cmd_stats(),
        "config": lambda: cli.cmd_config(args[0] if args else None, args[1] if len(args) > 1 else None),
    }
    
    if command in commands:
        return commands[command]()
    
    return {
        "success": False,
        "error": f"Unknown command: {command}"
    }


if __name__ == "__main__":
    # Demo
    cli = CompactionCLI()
    
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ] * 10  # Multiply to simulate conversation
    
    print("=== /estimate ===")
    result = cli.cmd_estimate(messages)
    print(json.dumps(result, indent=2))
    
    print("\n=== /stats ===")
    result = cli.cmd_stats()
    print(json.dumps(result, indent=2))
    
    print("\n=== /config ===")
    result = cli.cmd_config()
    print(json.dumps(result, indent=2))