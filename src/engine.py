"""
Context Compaction Engine - Core Implementation
Orchestrates tokenization, ranking, and compaction
"""

from typing import List, Dict, Optional, Tuple, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid

from .tokenizer import TokenEstimator, TokenCount
from .ranker import PriorityRanker, RankedMessage, Priority
from .summarizer import LLMSummarizer, SummarizerConfig


@dataclass
class CompactionResult:
    """Result of a compaction operation"""
    session_id: str
    original_tokens: int
    compacted_tokens: int
    tokens_saved: int
    savings_percentage: float
    messages_compacted: int
    messages_kept: int
    timestamp: str
    strategy: str
    summary: str


@dataclass
class CompactionConfig:
    """Configuration for compaction"""
    model: str = "gpt-4"
    max_context_percentage: float = 80.0  # Trigger at 80% of context
    keep_recent: int = 10
    keep_user: bool = True
    keep_tools_recent: int = 5
    strategy: str = "oldest_first"  # oldest_first, lowest_priority, hybrid
    enable_summarization: bool = True
    min_savings_percentage: float = 10.0  # Only compact if >10% savings
    # Summarizer settings
    summarizer_model: str = "gpt-4o-mini"
    summarizer_provider: str = "simple"  # openai, anthropic, ollama, simple
    summarizer_api_key: Optional[str] = None


class CompactionEngine:
    """
    Core compaction engine.
    
    Flow:
    1. Analyze session → count tokens
    2. Check if compaction needed (at threshold?)
    3. Rank messages by priority
    4. Select compaction candidates
    5. Execute compaction (summarize/prune)
    6. Return result with savings
    """
    
    def __init__(self, config: Optional[CompactionConfig] = None):
        self.config = config or CompactionConfig()
        self.token_estimator = TokenEstimator(self.config.model)
        self.ranker = PriorityRanker(
            keep_recent=self.config.keep_recent,
            keep_user=self.config.keep_user,
            keep_tools_recent=self.config.keep_tools_recent
        )
        self.summarizer = None
        self._init_summarizer()
    
    def _init_summarizer(self):
        """Initialize LLM summarizer based on config"""
        if not self.config.enable_summarization:
            return
        
        try:
            from .summarizer import create_summarizer
            self.summarizer = create_summarizer(
                provider=self.config.summarizer_provider,
                api_key=self.config.summarizer_api_key,
                model=self.config.summarizer_model
            )
        except Exception as e:
            print(f"Warning: Could not initialize summarizer: {e}")
            self.summarizer = None
    
    def _async_summarize(self, text: str) -> str:
        """Summarize text using configured LLM summarizer"""
        import asyncio
        if self.summarizer:
            return asyncio.run(self.summarizer.summarize_single(text))
        # Fallback to simple extraction
        return self._simple_extract(text)
    
    def _simple_extract(self, text: str) -> str:
        """Simple extraction fallback without LLM"""
        lines = text.split("\n")
        important = []
        keywords = ["decision", "important", "remember", "use", "create", "build", "fix", "bug", "error", "preferred", "want", "need", "must", "should", "def ", "class "]
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                if ":" in line:
                    important.append(line.split(":", 1)[1].strip())
                else:
                    important.append(line.strip())
        if not important:
            important = [l.strip() for l in lines[:3] if l.strip()]
        return " • ".join(important[:3]) if important else "[Compacted]"
        
    def analyze(self, messages: List[Dict]) -> Dict:
        """
        Analyze session without making changes.
        
        Returns analysis of current state.
        """
        count = self.token_estimator.count_messages(messages)
        limit = self.token_estimator.estimate_context_limit(self.config.model)
        usage = self.token_estimator.get_usage_percentage(messages, self.config.model)
        
        ranked = self.ranker.rank(messages, count.messages)
        stats = self.ranker.get_summary_stats(ranked)
        
        return {
            "tokens": count,
            "usage": usage,
            "limit": limit,
            "ranking": stats,
            "needs_compaction": usage["percentage"] > self.config.max_context_percentage,
            "threshold": self.config.max_context_percentage
        }
    
    def should_compact(self, messages: List[Dict]) -> Tuple[bool, str]:
        """
        Determine if compaction should trigger.
        
        Returns:
            (should_compact, reason)
        """
        analysis = self.analyze(messages)
        
        if not analysis["needs_compaction"]:
            return False, f"At {analysis['usage']['percentage']}% - below {self.config.max_context_percentage}% threshold"
        
        # Check minimum savings
        ranked = self.ranker.rank(messages, analysis["tokens"].messages)
        _, compactable = self.ranker.get_compactable(ranked)
        compactable_tokens = sum(rm.token_count for rm in compactable)
        current_tokens = analysis["tokens"].total
        potential_savings = compactable_tokens / current_tokens * 100
        
        if potential_savings < self.config.min_savings_percentage:
            return False, f"Potential savings {potential_savings:.1f}% below minimum {self.config.min_savings_percentage}%"
        
        return True, f"At {analysis['usage']['percentage']}% - above {self.config.max_context_percentage}% threshold"
    
    def compact(
        self,
        messages: List[Dict],
        session_id: Optional[str] = None,
        summarizer=None  # Optional LLM summarizer function
    ) -> Tuple[List[Dict], CompactionResult]:
        """
        Execute compaction on messages.
        
        Args:
            messages: Original messages
            session_id: Session identifier
            summarizer: Optional async function to summarize text
            
        Returns:
            (compacted_messages, result)
        """
        session_id = session_id or str(uuid.uuid4())
        original_tokens = self.token_estimator.count_messages(messages).total
        
        # Analyze and rank
        analysis = self.analyze(messages)
        ranked = self.ranker.rank(messages, analysis["tokens"].messages)
        
        # Get compaction candidates
        limit = self.token_estimator.estimate_context_limit(self.config.model)
        target_tokens = int(limit * self.config.max_context_percentage / 100 * 0.8)  # Target 80% of threshold
        
        candidates = self.ranker.get_compaction_candidates(
            ranked,
            target_tokens,
            self.config.strategy
        )
        
        if not candidates:
            return messages, CompactionResult(
                session_id=session_id,
                original_tokens=original_tokens,
                compacted_tokens=original_tokens,
                tokens_saved=0,
                savings_percentage=0.0,
                messages_compacted=0,
                messages_kept=len(messages),
                timestamp=datetime.utcnow().isoformat(),
                strategy=self.config.strategy,
                summary="No messages eligible for compaction"
            )
        
        # Create new message list
        compacted_messages = []
        compacted_indices = {c.index for c in candidates}
        
        for i, msg in enumerate(messages):
            if i in compacted_indices:
                # Get the candidate for this index
                candidate = next(c for c in candidates if c.index == i)
                
                if self.config.enable_summarization:
                    # Try to summarize - use provided summarizer or built-in
                    summarize_func = summarizer if summarizer else self._async_summarize
                    try:
                        summarized = summarize_func(msg.get("content", ""))
                        compacted_messages.append({
                            **msg,
                            "content": f"[SUMMARIZED from {candidate.token_count} tokens]: {summarized}",
                            "_compacted": True,
                            "_original_tokens": candidate.token_count
                        })
                    except Exception:
                        # Fall back to pruning
                        compacted_messages.append({
                            **msg,
                            "content": "[COMPACTED]",
                            "_compacted": True,
                            "_original_tokens": candidate.token_count
                        })
                else:
                    # Just mark as compacted
                    compacted_messages.append({
                        **msg,
                        "content": "[COMPACTED]",
                        "_compacted": True,
                        "_original_tokens": candidate.token_count
                    })
            else:
                compacted_messages.append(msg)
        
        # Calculate result
        compacted_tokens = self.token_estimator.count_messages(compacted_messages).total
        tokens_saved = original_tokens - compacted_tokens
        savings_pct = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0
        
        result = CompactionResult(
            session_id=session_id,
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            tokens_saved=tokens_saved,
            savings_percentage=round(savings_pct, 2),
            messages_compacted=len(candidates),
            messages_kept=len(messages) - len(candidates),
            timestamp=datetime.utcnow().isoformat(),
            strategy=self.config.strategy,
            summary=f"Compacted {len(candidates)} messages, saved {tokens_saved} tokens ({savings_pct:.1f}%)"
        )
        
        return compacted_messages, result
    
    def estimate_savings(self, messages: List[Dict]) -> Dict:
        """Estimate potential savings without actually compacting"""
        analysis = self.analyze(messages)
        ranked = self.ranker.rank(messages, analysis["tokens"].messages)
        
        limit = self.token_estimator.estimate_context_limit(self.config.model)
        target_tokens = int(limit * self.config.max_context_percentage / 100 * 0.8)
        
        candidates = self.ranker.get_compaction_candidates(
            ranked,
            target_tokens,
            self.config.strategy
        )
        
        original = analysis["tokens"].total
        compactable_tokens = sum(c.token_count for c in candidates)
        
        return {
            "original_tokens": original,
            "compactable_tokens": compactable_tokens,
            "potential_savings": compactable_tokens,
            "potential_savings_percentage": round(compactable_tokens / original * 100, 2) if original > 0 else 0,
            "messages_compactable": len(candidates),
            "messages_kept": len(messages) - len(candidates)
        }


# Convenience function
def quick_compact(messages: List[Dict], config: Optional[CompactionConfig] = None) -> Tuple[List[Dict], CompactionResult]:
    """Quick compaction for simple use cases"""
    engine = CompactionEngine(config)
    return engine.compact(messages)


if __name__ == "__main__":
    # Test
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write me a Python function to add two numbers"},
        {"role": "assistant", "content": "def add(a, b):\\n    return a + b"},
        {"role": "tool", "content": "File created: add.py"},
        {"role": "assistant", "content": "Done! Here's the function:"},
        {"role": "user", "content": "Now make it handle strings too"},
        {"role": "assistant", "content": "Here's the updated version with type checking..."},
        {"role": "tool", "content": "File updated: add.py"},
        {"role": "assistant", "content": "Now it handles both ints and strings!"},
        {"role": "user", "content": "Great! Can you add type hints?"},
        {"role": "assistant", "content": "def add(a: int, b: int) -> int:\\n    return a + b"},
        {"role": "user", "content": "Perfect. Add tests too."},
        {"role": "assistant", "content": "def test_add():\\n    assert add(1, 2) == 3\\n    assert add('a', 'b') == 'ab'"},
    ]
    
    engine = CompactionEngine()
    
    # Analyze
    analysis = engine.analyze(messages)
    print("Analysis:", json.dumps(analysis, indent=2, default=str))
    
    # Should we compact?
    should, reason = engine.should_compact(messages)
    print(f"\nShould compact: {should} - {reason}")
    
    # Estimate
    estimate = engine.estimate_savings(messages)
    print(f"\nEstimate: {json.dumps(estimate, indent=2)}")
    
    # Compact (without summarizer for demo)
    compacted, result = engine.compact(messages)
    print(f"\nResult: {result}")