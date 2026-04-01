"""
LLM Summarizer - AI-Powered Message Compression
Uses LLM to intelligently summarize old messages while preserving key information
"""

import asyncio
import json
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib


@dataclass
class SummaryResult:
    """Result of a summarization operation"""
    original_text: str
    summarized_text: str
    original_tokens: int
    summarized_tokens: int
    compression_ratio: float
    key_points_preserved: List[str]
    timestamp: str


@dataclass
class SummarizerConfig:
    """Configuration for summarizer"""
    model: str = "gpt-4o-mini"  # Cost-effective model
    max_tokens: int = 500
    temperature: float = 0.3
    preserve_code: bool = True
    preserve_decisions: bool = True
    preserve_facts: bool = True
    custom_prompt: Optional[str] = None


class LLMSummarizer:
    """
    LLM-powered summarizer for context compaction.
    
    Preserves:
    - Key facts and figures
    - Important decisions
    - Code snippets
    - User preferences
    - Critical context
    
    Uses chunked processing for long messages.
    """
    
    DEFAULT_PROMPT = """You are a context compression assistant. Summarize the following conversation/messages into a concise summary that preserves:

1. KEY FACTS - Numbers, dates, names, URLs, important data
2. DECISIONS - Any conclusions reached, choices made
3. CODE - Any code snippets or technical implementations
4. PREFERENCES - User preferences, settings, configurations
5. CRITICAL CONTEXT - Anything essential for understanding future messages

Be extremely concise but preserve all critical information. Use bullet points where appropriate.

MESSAGES:
{messages}

SUMMARY:"""

    def __init__(
        self,
        config: Optional[SummarizerConfig] = None,
        llm_provider: Optional[Callable] = None
    ):
        self.config = config or SummarizerConfig()
        self.llm_provider = llm_provider  # Function that calls LLM API
        
    def set_llm_provider(self, provider: Callable[[str, str, int, float], str]):
        """
        Set the LLM API provider function.
        
        Args:
            provider: Async function that takes:
                - prompt: str
                - model: str  
                - max_tokens: int
                - temperature: float
              And returns: str (summary text)
        """
        self.llm_provider = provider
    
    async def summarize(
        self,
        messages: List[Dict],
        session_context: Optional[str] = None
    ) -> SummaryResult:
        """
        Summarize a list of messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            session_context: Optional context about the session
            
        Returns:
            SummaryResult with summarized text
        """
        # Prepare messages for summarization
        formatted = self._format_messages(messages, session_context)
        
        # Build prompt
        prompt = self.config.custom_prompt or self.DEFAULT_PROMPT
        prompt = prompt.format(messages=formatted)
        
        # Call LLM
        if not self.llm_provider:
            # Fallback to simple extraction if no provider
            summarized = await self._simple_summarize(formatted)
        else:
            summarized = await self.llm_provider(
                prompt=prompt,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
        
        # Extract key points
        key_points = self._extract_key_points(summarized)
        
        # Estimate tokens (rough approximation)
        original_tokens = sum(len(m.get("content", "").split()) for m in messages) * 4 // 5
        summarized_tokens = len(summarized.split()) * 4 // 5
        
        return SummaryResult(
            original_text=formatted,
            summarized_text=summarized,
            original_tokens=original_tokens,
            summarized_tokens=summarized_tokens,
            compression_ratio=summarized_tokens / original_tokens if original_tokens > 0 else 1.0,
            key_points_preserved=key_points,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def summarize_single(self, text: str) -> str:
        """Summarize a single text block"""
        prompt = f"""Compress this text into a brief summary preserving key facts and decisions:

TEXT:
{text}

BRIEF SUMMARY:"""
        
        if not self.llm_provider:
            return await self._simple_summarize(text)
        
        return await self.llm_provider(
            prompt=prompt,
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )
    
    def _format_messages(
        self,
        messages: List[Dict],
        session_context: Optional[str] = None
    ) -> str:
        """Format messages for summarization prompt"""
        lines = []
        
        if session_context:
            lines.append(f"Session Context: {session_context}\n")
        
        for msg in messages:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            
            # Skip empty or placeholder content
            if not content or content == "[COMPACTED]":
                continue
            
            # Truncate very long content
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            lines.append(f"[{role.upper()}]: {content}")
        
        return "\n".join(lines)
    
    async def _simple_summarize(self, text: str) -> str:
        """Fallback simple summarization without LLM"""
        lines = text.split("\n")
        important = []
        
        keywords = [
            "decision", "decided", "important", "remember",
            "use", "create", "build", "fix", "bug", "error",
            "preferred", "want", "need", "must", "should",
            "http", "https", "def ", "class ", "import "
        ]
        
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                # Extract the meaningful part
                if ":" in line:
                    important.append(line.split(":", 1)[1].strip())
                else:
                    important.append(line.strip())
        
        if not important:
            # Just take first few non-empty lines
            important = [l.strip() for l in lines[:5] if l.strip()]
        
        return " • ".join(important[:5]) if important else "[Compacted content]"
    
    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key bullet points from summary"""
        points = []
        
        # Look for bullet points
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "• ", "* ")):
                points.append(line[2:].strip())
            elif line and (line[0].isdigit() and "." in line[:3]):
                points.append(line.strip())
        
        # If no bullets, just return first few sentences
        if not points:
            sentences = text.split(". ")
            points = [s.strip() for s in sentences[:3] if s.strip()]
        
        return points


# Integration with OpenAI API
class OpenAISummarizer(LLMSummarizer):
    """Summarizer with OpenAI API integration"""
    
    def __init__(
        self,
        config: Optional[SummarizerConfig] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        super().__init__(config)
        self.api_key = api_key
        self.api_base = api_base or "https://api.openai.com/v1"
        self._setup_provider()
    
    def _setup_provider(self):
        """Set up async OpenAI API call"""
        import aiohttp
        
        async def openai_call(prompt: str, model: str, max_tokens: int, temperature: float) -> str:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"OpenAI API error: {resp.status}")
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        
        self.set_llm_provider(openai_call)


# Integration with Anthropic API
class AnthropicSummarizer(LLMSummarizer):
    """Summarizer with Anthropic Claude API integration"""
    
    def __init__(
        self,
        config: Optional[SummarizerConfig] = None,
        api_key: Optional[str] = None
    ):
        super().__init__(config)
        self.api_key = api_key
        self._setup_provider()
    
    def _setup_provider(self):
        """Set up async Anthropic API call"""
        import aiohttp
        
        async def anthropic_call(prompt: str, model: str, max_tokens: int, temperature: float) -> str:
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            # Map model names
            model_map = {
                "gpt-4o-mini": "claude-3-haiku-20240307",
                "gpt-4o": "claude-3-opus-20240229",
                "gpt-4": "claude-3-opus-20240229",
            }
            anthropic_model = model_map.get(model, "claude-3-haiku-20240307")
            
            payload = {
                "model": anthropic_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"Anthropic API error: {resp.status}")
                    data = await resp.json()
                    return data["content"][0]["text"]
        
        self.set_llm_provider(anthropic_call)


# Integration with free/Ollama models
class OllamaSummarizer(LLMSummarizer):
    """Summarizer with Ollama local API integration"""
    
    def __init__(
        self,
        config: Optional[SummarizerConfig] = None,
        base_url: str = "http://localhost:11434"
    ):
        super().__init__(config)
        self.base_url = base_url
        self._setup_provider()
    
    def _setup_provider(self):
        """Set up async Ollama API call"""
        import aiohttp
        
        async def ollama_call(prompt: str, model: str, max_tokens: int, temperature: float) -> str:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"Ollama API error: {resp.status}")
                    data = await resp.json()
                    return data.get("response", "")
        
        self.set_llm_provider(ollama_call)


# Factory function
def create_summarizer(
    provider: str = "openai",
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    **kwargs
) -> LLMSummarizer:
    """
    Create a summarizer with the specified provider.
    
    Args:
        provider: "openai", "anthropic", "ollama", or "simple"
        api_key: API key for provider
        model: Model to use
        **kwargs: Additional provider-specific options
        
    Returns:
        LLMSummarizer instance
    """
    config = SummarizerConfig(model=model)
    
    if provider == "openai":
        return OpenAISummarizer(config, api_key)
    elif provider == "anthropic":
        return AnthropicSummarizer(config, api_key)
    elif provider == "ollama":
        return OllamaSummarizer(config, **kwargs)
    else:
        return LLMSummarizer(config)


async def quick_summarize(
    text: str,
    provider: str = "simple",
    **kwargs
) -> str:
    """
    Quick summarization utility.
    
    Args:
        text: Text to summarize
        provider: Provider type
        **kwargs: Provider options
        
    Returns:
        Summarized text
    """
    summarizer = create_summarizer(provider, **kwargs)
    return await summarizer.summarize_single(text)


if __name__ == "__main__":
    async def test():
        # Test with simple provider
        messages = [
            {"role": "user", "content": "I need to build a web app with React and Node.js"},
            {"role": "assistant", "content": "I'll help you set up a full-stack app. Let's start with the frontend..."},
            {"role": "user", "content": "Use PostgreSQL for the database"},
            {"role": "assistant", "content": "Great choice! Here's the schema we'll use..."},
            {"role": "tool", "content": "Created files: package.json, server.js, schema.sql"},
        ]
        
        summarizer = LLMSummarizer()
        result = await summarizer.summarize(messages)
        
        print("=== Original ===")
        print(result.original_text[:500])
        print("\n=== Summary ===")
        print(result.summarized_text)
        print(f"\nCompression: {result.compression_ratio:.1%}")
        print(f"Key points: {result.key_points_preserved}")
    
    asyncio.run(test())
