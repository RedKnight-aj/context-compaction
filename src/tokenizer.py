"""
Context Compaction Engine - Token Estimation
Accurate token counting for multiple models
"""

import tiktoken
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TokenCount:
    """Token count result"""
    total: int
    messages: List[int]
    system: int
    user: int
    assistant: int
    tools: int


class TokenEstimator:
    """
    Accurate token estimation for various models.
    Uses tiktoken for OpenAI models, custom estimation for others.
    """
    
    # Model to encoding mapping
    ENCODING_MAP = {
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "claude-3": "cl100k_base",  # Approximate
        "claude-3-5": "cl100k_base",
        "default": "cl100k_base",
    }
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self.encoding = self._get_encoding(model)
        
    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """Get appropriate encoding for model"""
        encoding_name = self.ENCODING_MAP.get(model, self.ENCODING_MAP["default"])
        return tiktoken.get_encoding(encoding_name)
    
    def count(self, text: str) -> int:
        """Count tokens in single text"""
        return len(self.encoding.encode(text))
    
    def count_messages(self, messages: List[Dict]) -> TokenCount:
        """
        Count tokens in a list of messages.
        
        Expected message format:
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "...", "tool_calls": [...]},
            {"role": "tool", "content": "..."},
        ]
        """
        total_tokens = 0
        message_tokens = []
        system_tokens = 0
        user_tokens = 0
        assistant_tokens = 0
        tool_tokens = 0
        
        for msg in messages:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            
            # Count content tokens
            tokens = self.count(content)
            
            # Add tool calls tokens
            if tool_calls:
                for tc in tool_calls:
                    tc_content = str(tc)
                    tokens += self.count(tc_content)
            
            # Add role formatting overhead (~4 tokens per message)
            tokens += 4
            
            message_tokens.append(tokens)
            total_tokens += tokens
            
            # Track by role
            if role == "system":
                system_tokens += tokens
            elif role == "user":
                user_tokens += tokens
            elif role == "tool":
                tool_tokens += tokens
            else:
                assistant_tokens += tokens
        
        return TokenCount(
            total=total_tokens,
            messages=message_tokens,
            system=system_tokens,
            user=user_tokens,
            assistant=assistant_tokens,
            tools=tool_tokens
        )
    
    def estimate_context_limit(self, model: str) -> int:
        """Return context window size for model"""
        limits = {
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "gpt-4o": 128000,
            "gpt-3.5-turbo": 16385,
            "claude-3": 200000,
            "claude-3-5": 200000,
            "default": 100000,
        }
        return limits.get(model, limits["default"])
    
    def get_usage_percentage(self, messages: List[Dict], model: str) -> Dict:
        """Get percentage of context used"""
        count = self.count_messages(messages)
        limit = self.estimate_context_limit(model)
        return {
            "tokens": count.total,
            "limit": limit,
            "percentage": round(count.total / limit * 100, 2),
            "remaining": limit - count.total
        }


# Standalone function for simple usage
def quick_count(text: str, model: str = "gpt-4") -> int:
    """Quick token count for a single text"""
    estimator = TokenEstimator(model)
    return estimator.count(text)


if __name__ == "__main__":
    # Test
    estimator = TokenEstimator("gpt-4")
    
    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
    ]
    
    result = estimator.count_messages(test_messages)
    print(f"Total tokens: {result.total}")
    print(f"System: {result.system}, User: {result.user}, Assistant: {result.assistant}")
    
    usage = estimator.get_usage_percentage(test_messages, "gpt-4")
    print(f"Usage: {usage}")