"""
RAG (Retrieval-Augmented Generation) system for context injection
Embeddings-based document retrieval with semantic search
"""

import numpy as np
import logging
import asyncio
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import time

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from sklearn.metrics.pairwise import cosine_similarity
from app.core.config import settings
from app.models.schemas import DocumentChunk, RAGContext

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a document with metadata"""
    content: str
    source: str
    chunks: List[str]
    embeddings: Optional[np.ndarray] = None


class EmbeddingService:
    """Service for generating and managing embeddings"""
    
    def __init__(self):
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers package not installed")
        
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.dimension}")
    
    async def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for text"""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode(text, normalize_embeddings=True)
        )
        return embedding
    
    async def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        )
        return embeddings


class DocumentChunker:
    """Chunks documents into overlapping segments for better retrieval"""
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Chunk text into overlapping segments
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - overlap
            
            if start >= len(text):
                break
        
        return chunks if chunks else [text]


class RAGSystem:
    """Retrieval-Augmented Generation system for context injection"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.documents: Dict[str, Document] = {}
        self.chunker = DocumentChunker()
        self.index: Optional[np.ndarray] = None  # All embeddings
        self.index_sources: List[Tuple[str, int]] = []  # Source and chunk index
    
    async def add_document(self, content: str, source: str) -> int:
        """
        Add document to RAG system
        
        Returns:
            Number of chunks created
        """
        start_time = time.time()
        
        try:
            # Chunk the document
            chunks = self.chunker.chunk_text(
                content,
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP
            )
            
            # Generate embeddings for chunks
            embeddings = await self.embedding_service.embed_texts(chunks)
            
            # Store document
            self.documents[source] = Document(
                content=content,
                source=source,
                chunks=chunks,
                embeddings=embeddings
            )
            
            # Update index
            self._rebuild_index()
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Added document '{source}' with {len(chunks)} chunks in {elapsed:.2f}ms")
            
            return len(chunks)
        
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            raise
    
    def _rebuild_index(self):
        """Rebuild embedding index from all documents"""
        embeddings_list = []
        sources_list = []
        
        for source, doc in self.documents.items():
            if doc.embeddings is not None:
                for i, emb in enumerate(doc.embeddings):
                    embeddings_list.append(emb)
                    sources_list.append((source, i))
        
        if embeddings_list:
            self.index = np.array(embeddings_list)
            self.index_sources = sources_list
            logger.info(f"Rebuilt index with {len(embeddings_list)} chunks")
    
    async def retrieve_context(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        """
        Retrieve most relevant document chunks for query
        
        Args:
            query: User query
            top_k: Number of top chunks to retrieve
            
        Returns:
            List of relevant document chunks
        """
        start_time = time.time()
        
        if not self.documents or self.index is None:
            logger.warning("No documents in RAG system")
            return []
        
        try:
            # Embed query
            query_embedding = await self.embedding_service.embed_text(query)
            
            # Compute similarity scores
            similarities = cosine_similarity([query_embedding], self.index)[0]
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Build result chunks
            result_chunks = []
            for idx in top_indices:
                if similarities[idx] >= settings.SIMILARITY_THRESHOLD:
                    source, chunk_idx = self.index_sources[idx]
                    doc = self.documents[source]
                    
                    result_chunks.append(DocumentChunk(
                        content=doc.chunks[chunk_idx],
                        source=source,
                        relevance_score=float(similarities[idx]),
                        chunk_index=chunk_idx
                    ))
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Retrieved {len(result_chunks)} relevant chunks in {elapsed:.2f}ms")
            
            return result_chunks
        
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []
    
    def build_context_prompt(self, context_chunks: List[DocumentChunk], max_length: int = 2000) -> str:
        """
        Build context string for LLM prompt
        
        Args:
            context_chunks: Retrieved document chunks
            max_length: Maximum length of context in characters
            
        Returns:
            Formatted context string
        """
        if not context_chunks:
            return ""
        
        context_parts = []
        total_length = 0
        
        for chunk in context_chunks:
            if total_length + len(chunk.content) > max_length:
                break
            
            context_parts.append(f"[{chunk.source} - Relevance: {chunk.relevance_score:.2f}]")
            context_parts.append(chunk.content)
            context_parts.append("")
            
            total_length += len(chunk.content)
        
        if not context_parts:
            return ""
        
        return "\n".join(context_parts)
    
    async def clear(self):
        """Clear all documents and index"""
        self.documents.clear()
        self.index = None
        self.index_sources.clear()
        logger.info("RAG system cleared")
    
    def get_stats(self) -> Dict:
        """Get RAG system statistics"""
        total_chunks = sum(len(doc.chunks) for doc in self.documents.values())
        return {
            "total_documents": len(self.documents),
            "total_chunks": total_chunks,
            "index_size": self.index.shape[0] if self.index is not None else 0,
            "embedding_dimension": self.embedding_service.dimension
        }


# Global RAG system instance
_rag_system: Optional[RAGSystem] = None


async def get_rag_system() -> RAGSystem:
    """Get or create RAG system singleton"""
    global _rag_system
    if _rag_system is None:
        _rag_system = RAGSystem()
    return _rag_system
