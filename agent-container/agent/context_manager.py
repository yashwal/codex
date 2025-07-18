import json
import os
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib

@dataclass
class ContextItem:
    """Represents a single context item with metadata"""
    id: str
    content: str
    timestamp: float
    importance: float
    category: str  # 'conversation', 'code', 'file', 'output'
    size: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextItem':
        return cls(**data)

class ContextManager:
    """
    Manages context for the coding agent with intelligent pruning
    and file-based persistence to handle >1M token contexts.
    """
    
    def __init__(self, workspace_dir: str = "/workspace", max_memory_tokens: int = 50000):
        self.workspace_dir = Path(workspace_dir)
        self.context_dir = self.workspace_dir / ".agent_context"
        self.context_dir.mkdir(exist_ok=True)
        
        self.max_memory_tokens = max_memory_tokens
        self.memory_items: List[ContextItem] = []
        self.token_count = 0
        
        # Load existing context
        self._load_context()
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def _calculate_importance(self, content: str, category: str) -> float:
        """Calculate importance score for context item"""
        base_scores = {
            'conversation': 1.0,
            'code': 1.5,
            'file': 1.2,
            'output': 0.8
        }
        
        base = base_scores.get(category, 1.0)
        
        # Boost importance for certain keywords
        importance_keywords = ['error', 'exception', 'todo', 'fixme', 'important', 'critical']
        for keyword in importance_keywords:
            if keyword.lower() in content.lower():
                base *= 1.3
        
        # Boost for recent items
        age_factor = 1.0  # Will be updated based on recency
        
        return base * age_factor
    
    def add_context(self, content: str, category: str) -> str:
        """Add new context item and manage memory"""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        item_id = f"{category}_{int(time.time())}_{content_hash}"
        
        size = self._estimate_tokens(content)
        importance = self._calculate_importance(content, category)
        
        item = ContextItem(
            id=item_id,
            content=content,
            timestamp=time.time(),
            importance=importance,
            category=category,
            size=size
        )
        
        self.memory_items.append(item)
        self.token_count += size
        
        # Persist to disk
        self._save_item(item)
        
        # Prune if necessary
        if self.token_count > self.max_memory_tokens:
            self._prune_memory()
        
        return item_id
    
    def _prune_memory(self):
        """Intelligent pruning based on importance and recency"""
        current_time = time.time()
        
        # Update importance based on recency
        for item in self.memory_items:
            age_hours = (current_time - item.timestamp) / 3600
            recency_factor = max(0.1, 1.0 - (age_hours / 24))  # Decay over 24 hours
            item.importance *= recency_factor
        
        # Sort by importance (descending)
        self.memory_items.sort(key=lambda x: x.importance, reverse=True)
        
        # Keep the most important items within token limit
        new_items = []
        new_token_count = 0
        
        for item in self.memory_items:
            if new_token_count + item.size <= self.max_memory_tokens:
                new_items.append(item)
                new_token_count += item.size
            else:
                # Move to archive
                self._archive_item(item)
        
        self.memory_items = new_items
        self.token_count = new_token_count
    
    def _save_item(self, item: ContextItem):
        """Save context item to disk"""
        file_path = self.context_dir / f"{item.id}.json"
        with open(file_path, 'w') as f:
            json.dump(item.to_dict(), f, indent=2)
    
    def _archive_item(self, item: ContextItem):
        """Move item to archive directory"""
        archive_dir = self.context_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        source = self.context_dir / f"{item.id}.json"
        target = archive_dir / f"{item.id}.json"
        
        if source.exists():
            source.rename(target)
    
    def _load_context(self):
        """Load context from disk on startup"""
        if not self.context_dir.exists():
            return
        
        for file_path in self.context_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                item = ContextItem.from_dict(data)
                self.memory_items.append(item)
                self.token_count += item.size
            except Exception as e:
                print(f"Error loading context item {file_path}: {e}")
        
        # Sort by timestamp
        self.memory_items.sort(key=lambda x: x.timestamp)
    
    def get_relevant_context(self, query: str, max_tokens: int = 10000) -> List[ContextItem]:
        """Get relevant context items for a query"""
        query_lower = query.lower()
        scored_items = []
        
        # Score items based on relevance
        for item in self.memory_items:
            score = item.importance
            
            # Boost score for keyword matches
            content_lower = item.content.lower()
            query_words = query_lower.split()
            matches = sum(1 for word in query_words if word in content_lower)
            score *= (1 + matches * 0.2)
            
            scored_items.append((score, item))
        
        # Sort by score and select within token limit
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        selected_items = []
        total_tokens = 0
        
        for score, item in scored_items:
            if total_tokens + item.size <= max_tokens:
                selected_items.append(item)
                total_tokens += item.size
            else:
                break
        
        return selected_items
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of current context state"""
        categories = {}
        for item in self.memory_items:
            if item.category not in categories:
                categories[item.category] = {'count': 0, 'tokens': 0}
            categories[item.category]['count'] += 1
            categories[item.category]['tokens'] += item.size
        
        return {
            'total_items': len(self.memory_items),
            'total_tokens': self.token_count,
            'categories': categories,
            'memory_usage': f"{self.token_count}/{self.max_memory_tokens}",
            'archived_items': len(list((self.context_dir / "archive").glob("*.json"))) if (self.context_dir / "archive").exists() else 0
        }
    
    def search_context(self, query: str, category: Optional[str] = None) -> List[ContextItem]:
        """Search context items by content"""
        query_lower = query.lower()
        results = []
        
        for item in self.memory_items:
            if category and item.category != category:
                continue
            
            if query_lower in item.content.lower():
                results.append(item)
        
        return sorted(results, key=lambda x: x.timestamp, reverse=True)