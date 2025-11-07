"""
RAG (Retrieval-Augmented Generation) engine for DiaryML
Uses ChromaDB for vector storage and semantic search
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class RAGEngine:
    """RAG engine for semantic search over journal entries"""

    def __init__(self, persist_directory: Optional[Path] = None):
        """
        Initialize RAG engine

        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        global _rag_init_logged

        if persist_directory is None:
            persist_directory = Path(__file__).parent.parent / "chroma_db"

        persist_directory.mkdir(exist_ok=True)

        # Only log initialization once
        if not _rag_init_logged:
            print("Initializing RAG engine...")
            _rag_init_logged = True

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="diary_entries",
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

        # Initialize embedding model (lightweight and fast)
        if not _rag_init_logged or _rag_engine is None:  # Only log on first init
            print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        if not _rag_init_logged or _rag_engine is None:
            print("✓ RAG engine initialized")

    def add_entry(
        self,
        entry_id: int,
        content: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add diary entry to vector database

        Args:
            entry_id: Unique entry ID from SQLite
            content: Entry text content
            timestamp: Entry timestamp
            metadata: Additional metadata (moods, projects, etc.)
        """
        # Generate embedding
        embedding = self.embedding_model.encode(content).tolist()

        # Prepare metadata
        meta = {
            "timestamp": timestamp.isoformat(),
            "length": len(content)
        }

        if metadata:
            meta.update(metadata)

        # Add to ChromaDB
        self.collection.add(
            embeddings=[embedding],
            documents=[content],
            ids=[str(entry_id)],
            metadatas=[meta]
        )

    def search_entries(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant entries

        Args:
            query: Search query or current entry text
            n_results: Number of results to return
            filter_metadata: Optional filters (e.g., date range, emotions)

        Returns:
            List of relevant entries with metadata
        """
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata if filter_metadata else None
        )

        # Format results
        entries = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                entry = {
                    "id": int(results['ids'][0][i]),
                    "content": doc,
                    "distance": results['distances'][0][i] if 'distances' in results else None,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {}
                }
                entries.append(entry)

        return entries

    def get_contextual_entries(
        self,
        current_entry: str,
        exclude_id: Optional[int] = None,
        n_results: int = 3
    ) -> List[str]:
        """
        Get contextually relevant past entries for RAG

        Args:
            current_entry: Current entry text
            exclude_id: Entry ID to exclude (typically the current entry)
            n_results: Number of context entries to retrieve

        Returns:
            List of relevant entry texts
        """
        results = self.search_entries(current_entry, n_results=n_results + 1)

        # Filter out the excluded entry
        relevant_entries = []
        for result in results:
            if exclude_id is None or result["id"] != exclude_id:
                relevant_entries.append(result["content"])

            if len(relevant_entries) >= n_results:
                break

        return relevant_entries

    def search_by_emotion(
        self,
        emotion: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find entries with similar emotional content

        Args:
            emotion: Emotion to search for
            n_results: Number of results

        Returns:
            List of entries with similar emotions
        """
        # Use emotion as query
        query = f"feeling {emotion}"
        return self.search_entries(query, n_results=n_results)

    def search_by_timeframe(
        self,
        start_date: datetime,
        end_date: datetime,
        query: Optional[str] = None,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search entries within a timeframe

        Args:
            start_date: Start of timeframe
            end_date: End of timeframe
            query: Optional search query
            n_results: Number of results

        Returns:
            List of entries in timeframe
        """
        # Note: ChromaDB filtering by date range requires metadata filters
        # This is a simplified version - might need adjustment based on ChromaDB version

        if query:
            results = self.search_entries(query, n_results=n_results * 2)
            # Filter by date in post-processing
            filtered = []
            for result in results:
                timestamp_str = result.get("metadata", {}).get("timestamp")
                if timestamp_str:
                    entry_date = datetime.fromisoformat(timestamp_str)
                    if start_date <= entry_date <= end_date:
                        filtered.append(result)
                        if len(filtered) >= n_results:
                            break
            return filtered
        else:
            # Get all and filter
            # For production, implement proper date filtering
            return []

    def update_entry(
        self,
        entry_id: int,
        content: str,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update an existing entry in the vector database"""
        # Delete old version
        try:
            self.collection.delete(ids=[str(entry_id)])
        except:
            pass

        # Add updated version
        self.add_entry(entry_id, content, timestamp, metadata)

    def delete_entry(self, entry_id: int):
        """Delete entry from vector database"""
        try:
            self.collection.delete(ids=[str(entry_id)])
        except:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        count = self.collection.count()

        return {
            "total_entries": count,
            "collection_name": self.collection.name
        }

    def clear_all(self):
        """Clear all entries (use with caution!)"""
        self.client.delete_collection("diary_entries")
        self.collection = self.client.create_collection(
            name="diary_entries",
            metadata={"hnsw:space": "cosine"}
        )


# Singleton
_rag_engine: Optional[RAGEngine] = None
_rag_init_logged: bool = False


def get_rag_engine() -> RAGEngine:
    """Get or create RAG engine singleton"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
