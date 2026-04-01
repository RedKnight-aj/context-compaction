"""
Priority Ranker - Message Importance Classification
Determines which messages can be compacted vs must be kept
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    """Message priority levels"""
    FIXED = 5       # Always keep (system prompts)
    HIGH = 4        # Must keep (recent user/assistant)
    MEDIUM = 3      # Can summarize (tool results)
    LOW = 2         # Can prune (very old messages)
    DISCARD = 1     # Can discard (duplicates, noise)


@dataclass
class RankedMessage:
    """Message with priority ranking"""
    index: int
    role: str
    content: str
    priority: Priority
    token_count: int
    reason: str


class PriorityRanker:
    """
    Rank messages by importance for compaction decisions.
    
    Priority Rules:
    - System prompts: FIXED (always keep)
    - Last N messages: HIGH (keep intact)
    - Tool results: MEDIUM (can summarize)
    - User messages: HIGH (keep)
    - Assistant messages: MEDIUM (can summarize if old)
    """
    
    def __init__(
        self,
        keep_recent: int = 10,
        keep_user: bool = True,
        keep_tools_recent: int = 5,
    ):
        self.keep_recent = keep_recent
        self.keep_user = keep_user
        self.keep_tools_recent = keep_tools_recent
        
    def rank(self, messages: List[Dict], token_counts: List[int]) -> List[RankedMessage]:
        """
        Rank all messages by priority.
        
        Args:
            messages: List of message dicts
            token_counts: Token count for each message
            
        Returns:
            List of RankedMessage objects sorted by priority (highest first)
        """
        ranked = []
        total_messages = len(messages)
        
        for i, msg in enumerate(messages):
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            
            # Calculate position metrics
            from_end = total_messages - i - 1
            is_recent = from_end < self.keep_recent
            
            # Determine priority
            priority, reason = self._calculate_priority(
                msg, i, from_end, is_recent, total_messages
            )
            
            ranked.append(RankedMessage(
                index=i,
                role=role,
                content=content,
                priority=priority,
                token_count=token_counts[i] if i < len(token_counts) else 0,
                reason=reason
            ))
        
        return ranked
    
    def _calculate_priority(
        self,
        msg: Dict,
        index: int,
        from_end: int,
        is_recent: bool,
        total: int
    ) -> Tuple[Priority, str]:
        """Calculate priority for a single message"""
        role = msg.get("role", "assistant")
        
        # System prompts are FIXED - never compact
        if role == "system":
            return Priority.FIXED, "System prompt - always kept"
        
        # Recent messages are HIGH priority
        if is_recent:
            return Priority.HIGH, f"Recent message (within {self.keep_recent})"
        
        # User messages - keep if configured
        if role == "user" and self.keep_user:
            return Priority.HIGH, "User message - important"
        
        # Tool messages - recent tools get MEDIUM
        if role == "tool":
            if from_end < self.keep_tools_recent:
                return Priority.MEDIUM, "Recent tool result"
            return Priority.LOW, "Old tool result - can compact"
        
        # Assistant messages - older ones can be summarized
        if role == "assistant":
            if from_end < self.keep_recent // 2:
                return Priority.MEDIUM, "Recent assistant response"
            return Priority.LOW, "Old assistant response - can compact"
        
        # Default
        return Priority.MEDIUM, "Default medium priority"
    
    def get_compactable(
        self,
        ranked: List[RankedMessage]
    ) -> Tuple[List[RankedMessage], List[RankedMessage]]:
        """
        Split messages into compactable vs must-keep.
        
        Returns:
            (must_keep, compactable) - two lists of RankedMessage
        """
        must_keep = []
        compactable = []
        
        for rm in ranked:
            if rm.priority in [Priority.FIXED, Priority.HIGH]:
                must_keep.append(rm)
            else:
                compactable.append(rm)
        
        return must_keep, compactable
    
    def get_compaction_candidates(
        self,
        ranked: List[RankedMessage],
        max_tokens: int,
        strategy: str = "oldest_first"
    ) -> List[RankedMessage]:
        """
        Get list of messages to compact to stay under max_tokens.
        
        Args:
            ranked: Ranked messages
            max_tokens: Maximum tokens to allow
            strategy: How to select candidates (oldest_first, lowest_priority)
            
        Returns:
            List of messages to compact
        """
        # Get compactable messages
        _, compactable = self.get_compactable(ranked)
        
        if not compactable:
            return []
        
        # Sort by strategy
        if strategy == "oldest_first":
            candidates = sorted(compactable, key=lambda x: x.index)
        elif strategy == "lowest_priority":
            candidates = sorted(compactable, key=lambda x: (x.priority.value, x.index))
        else:
            candidates = compactable
        
        # Find how many we can compact while staying under limit
        current_tokens = sum(rm.token_count for rm in ranked)
        target_reduction = current_tokens - max_tokens
        
        selected = []
        accumulated = 0
        
        for rm in candidates:
            if accumulated >= target_reduction:
                break
            selected.append(rm)
            accumulated += rm.token_count
        
        return selected
    
    def get_summary_stats(self, ranked: List[RankedMessage]) -> Dict:
        """Get summary statistics of ranking"""
        stats = {
            "total": len(ranked),
            "fixed": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "discard": 0,
            "compactable": 0,
            "keepable": 0,
        }
        
        for rm in ranked:
            stats[rm.priority.name.lower()] += 1
        
        must_keep, compactable = self.get_compactable(ranked)
        stats["keepable"] = len(must_keep)
        stats["compactable"] = len(compactable)
        
        return stats


if __name__ == "__main__":
    # Test
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "tool", "content": "Result 1", "tool_call_id": "1"},
        {"role": "assistant", "content": "Processing..."},
        {"role": "tool", "content": "Result 2", "tool_call_id": "2"},
        {"role": "user", "content": "Tell me more"},
        {"role": "assistant", "content": "More info here"},
        {"role": "assistant", "content": "Even more"},
        {"role": "user", "content": "Final question?"},
        {"role": "assistant", "content": "Final answer."},
    ]
    
    ranker = PriorityRanker(keep_recent=5)
    token_counts = [20, 10, 15, 100, 20, 100, 15, 25, 20, 20, 15]
    
    ranked = ranker.rank(messages, token_counts)
    stats = ranker.get_summary_stats(ranked)
    
    print("Stats:", stats)
    
    must_keep, compactable = ranker.get_compactable(ranked)
    print(f"\nMust keep: {len(must_keep)}")
    print(f"Compactable: {len(compactable)}")