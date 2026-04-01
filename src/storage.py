"""
Storage Layer - LanceDB Integration
Persist compaction history and analytics
"""

import lancedb
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class CompactionRecord:
    """Record of a compaction operation"""
    session_id: str
    original_tokens: int
    compacted_tokens: int
    tokens_saved: int
    savings_percentage: float
    messages_compacted: int
    messages_kept: int
    timestamp: str
    strategy: str


class CompactionStorage:
    """
    Storage layer using LanceDB for compaction history.
    """
    
    def __init__(self, db_path: str = "lancedb"):
        self.db_path = db_path
        self.db = None
        self.table = None
        
    def connect(self):
        """Connect to LanceDB"""
        self.db = lancedb.connect(self.db_path)
        self._ensure_table()
        
    def _ensure_table(self):
        """Ensure compaction history table exists"""
        tables = self.db.table_names()
        
        if "compaction_history" not in tables:
            self.table = self.db.create_table(
                "compaction_history",
                schema=[
                    ("session_id", "utf8"),
                    ("original_tokens", "int64"),
                    ("compacted_tokens", "int64"),
                    ("tokens_saved", "int64"),
                    ("savings_percentage", "float64"),
                    ("messages_compacted", "int64"),
                    ("messages_kept", "int64"),
                    ("timestamp", "utf8"),
                    ("strategy", "utf8"),
                ]
            )
        else:
            self.table = self.db.open_table("compaction_history")
    
    def save(self, record: CompactionRecord):
        """Save a compaction record"""
        if not self.table:
            self.connect()
            
        self.table.add([
            {
                "session_id": record.session_id,
                "original_tokens": record.original_tokens,
                "compacted_tokens": record.compacted_tokens,
                "tokens_saved": record.tokens_saved,
                "savings_percentage": record.savings_percentage,
                "messages_compacted": record.messages_compacted,
                "messages_kept": record.messages_kept,
                "timestamp": record.timestamp,
                "strategy": record.strategy,
            }
        ])
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """Get compaction history for a session"""
        if not self.table:
            return []
        return self.table.filter(f"session_id = '{session_id}'").to_pandas().to_dict("records")
    
    def get_all_history(self, limit: int = 100) -> List[Dict]:
        """Get all compaction history"""
        if not self.table:
            return []
        df = self.table.to_pandas()
        return df.tail(limit).to_dict("records")
    
    def get_stats(self) -> Dict:
        """Get aggregate statistics"""
        if not self.table:
            return {
                "total_sessions": 0,
                "total_tokens_saved": 0,
                "average_savings": 0,
                "total_compactions": 0
            }
        
        df = self.table.to_pandas()
        
        if df.empty:
            return {
                "total_sessions": 0,
                "total_tokens_saved": 0,
                "average_savings": 0,
                "total_compactions": 0
            }
        
        return {
            "total_sessions": df["session_id"].nunique(),
            "total_tokens_saved": int(df["tokens_saved"].sum()),
            "average_savings": round(df["savings_percentage"].mean(), 2),
            "total_compactions": len(df)
        }
    
    def close(self):
        """Close connection"""
        self.db = None
        self.table = None


# Mock storage for testing without LanceDB
class MockStorage:
    """In-memory storage for testing"""
    
    def __init__(self):
        self.records = []
        
    def connect(self):
        pass
    
    def save(self, record: CompactionRecord):
        self.records.append(record)
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        return [r.__dict__ for r in self.records if r.session_id == session_id]
    
    def get_all_history(self, limit: int = 100) -> List[Dict]:
        return [r.__dict__ for r in self.records[-limit:]]
    
    def get_stats(self) -> Dict:
        if not self.records:
            return {
                "total_sessions": 0,
                "total_tokens_saved": 0,
                "average_savings": 0,
                "total_compactions": 0
            }
        
        return {
            "total_sessions": len(set(r.session_id for r in self.records)),
            "total_tokens_saved": sum(r.tokens_saved for r in self.records),
            "average_savings": round(sum(r.savings_percentage for r in self.records) / len(self.records), 2),
            "total_compactions": len(self.records)
        }
    
    def close(self):
        pass


if __name__ == "__main__":
    # Test with mock
    storage = MockStorage()
    
    # Save some records
    for i in range(5):
        record = CompactionRecord(
            session_id=f"session_{i}",
            original_tokens=50000,
            compacted_tokens=30000,
            tokens_saved=20000,
            savings_percentage=40.0,
            messages_compacted=10,
            messages_kept=20,
            timestamp=datetime.utcnow().isoformat(),
            strategy="oldest_first"
        )
        storage.save(record)
    
    stats = storage.get_stats()
    print("Stats:", stats)