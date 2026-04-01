# Context Compaction Toolkit
"""
Context Compaction Engine for OpenClaw

Provides token optimization, context management, and compaction services.

Usage:
    from toolkit.compaction import CompactionEngine, CompactionConfig
    
    engine = CompactionEngine()
    analysis = engine.analyze(messages)
    compacted, result = engine.compact(messages)
"""

from .engine import CompactionEngine, CompactionConfig, CompactionResult
from .tokenizer import TokenEstimator, TokenCount
from .ranker import PriorityRanker, RankedMessage, Priority
from .storage import CompactionStorage, CompactionRecord
from .summarizer import LLMSummarizer, SummarizerConfig, create_summarizer

__version__ = "1.1.0"
__all__ = [
    "CompactionEngine",
    "CompactionConfig", 
    "CompactionResult",
    "TokenEstimator",
    "TokenCount",
    "PriorityRanker",
    "RankedMessage",
    "Priority",
    "CompactionStorage",
    "CompactionRecord",
    "LLMSummarizer",
    "SummarizerConfig",
    "create_summarizer",
]