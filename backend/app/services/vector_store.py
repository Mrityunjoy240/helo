
import os
import logging
import json
import pickle
import numpy as np
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Try to import FAISS and SentenceTransformer
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

logger = logging.getLogger(__name__)

class VectorStore:
    """
    Abstract base class for vector storage (to allow easy swapping in future)
    """
    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        raise NotImplementedError
        
    def search(self, query: str, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        raise NotImplementedError
        
    def save(self) -> None:
        raise NotImplementedError
        
    def load(self) -> None:
        raise NotImplementedError

class FAISSVectorStore(VectorStore):
    """
    Vector store implementation using FAISS and SentenceTransformers.
    """
    def __init__(self, persist_dir: str = "chroma_db", model_name: str = "all-MiniLM-L6-v2"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(exist_ok=True, parents=True)
        
        self.index_file = self.persist_dir / "faiss_index.bin"
        self.docs_file = self.persist_dir / "documents.pkl"
        
        self.documents = []  # Stores the actual document metadata/content
        self.index = None    # FAISS index
        
        if not HAS_FAISS:
             logger.warning("FAISS or SentenceTransformers not installed. Vector search will be disabled.")
             self.model = None
             return

        try:
            logger.info(f"Loading embedding model: {model_name}")
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None
            
        # Try to load existing index
        self.load()
        
        # Check for dimension mismatch (e.g. upgrading from MiniLM to mpnet)
        if self.index and self.model:
            current_dim = self.model.get_sentence_embedding_dimension()
            index_dim = self.index.d
            if current_dim != index_dim:
                logger.warning(f"Dimension mismatch! Index: {index_dim}, Model: {current_dim}. Resetting vector store.")
                self.index = None
                self.documents = []
                # Clear files to prevent reload on next restart
                if self.index_file.exists(): os.remove(self.index_file)
                if self.docs_file.exists(): os.remove(self.docs_file)

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """
        Add documents to the store.
        documents: List of dicts with 'text' and 'metadata' keys
        """
        if not self.model:
            logger.warning("No model available, skipping embedding generation.")
            return
            
        if not documents:
            return

        texts = [doc.get('text', '') for doc in documents]
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} documents...")
        embeddings = self.model.encode(texts)
        
        # Initialize index if needed
        if self.index is None:
            dimension = embeddings.shape[1]
            # using IndexFlatL2 for exact search (good for small datasets < 1M)
            self.index = faiss.IndexFlatL2(dimension)
            
        # Add to FAISS index
        self.index.add(np.array(embeddings).astype('float32'))
        
        # Store document data
        # We append to existing documents because FAISS adds sequentially
        self.documents.extend(documents)
        
        logger.info(f"Added {len(documents)} documents to vector store. Total: {len(self.documents)}")
        self.save()

    def search(self, query: str, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for similar documents.
        Returns list of (document, score) tuples.
        """
        if not self.model or self.index is None or not self.documents:
            return []
            
        query_vector = self.model.encode([query])
        
        # Search FAISS
        # D: distances (lower is better for L2), I: indices
        D, I = self.index.search(np.array(query_vector).astype('float32'), k)
        
        results = []
        for j, doc_idx in enumerate(I[0]):
            if doc_idx < 0 or doc_idx >= len(self.documents):
                continue
                
            doc = self.documents[doc_idx]
            score = float(D[0][j])
            
            # FAISS L2 distance: 0 is identical.
            # Convert to similarity score roughly [0, 1] for compatibility
            # Simple conversion: 1 / (1 + distance)
            similarity = 1 / (1 + score)
            
            results.append((doc, similarity))
            
        return results

    def save(self) -> None:
        """Save index and documents to disk"""
        if not self.persist_dir.exists():
            self.persist_dir.mkdir(parents=True)
            
        if self.index:
            try:
                faiss.write_index(self.index, str(self.index_file))
                with open(self.docs_file, 'wb') as f:
                    pickle.dump(self.documents, f)
                logger.info(f"Saved vector store to {self.persist_dir}")
            except Exception as e:
                logger.error(f"Error saving vector store: {e}")

    def load(self) -> None:
        """Load index and documents from disk"""
        if self.index_file.exists() and self.docs_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                with open(self.docs_file, 'rb') as f:
                    self.documents = pickle.load(f)
                logger.info(f"Loaded vector store with {len(self.documents)} documents")
            except Exception as e:
                logger.error(f"Error loading vector store: {e}")
                self.index = None
                self.documents = []
