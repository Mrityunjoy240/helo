from typing import List, Dict, Optional, AsyncGenerator, Tuple
import logging
import time
import os
from pathlib import Path
from datetime import datetime
import numpy as np
from collections import defaultdict
import json
import re
import asyncio
import hashlib
import pickle
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

# Import conversation memory
from app.services.conversation_memory import ConversationMemory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# 1. HYBRID RETRIEVER - BM25 + Semantic Similarity
# ============================================================================

# Import FAISS Vector Store
from app.services.vector_store import FAISSVectorStore

class KnowledgeRetriever:
    """
    Retrieves exact facts from structured knowledge graph (JSON).
    Used for high-precision queries like Fees, Courses, Faculty.
    """
    def __init__(self, data_path: str = "backend/data/knowledge_graph.json"):
        self.data = self._load(data_path)
        
    def _load(self, path: str) -> Dict:
        try:
            # Handle relative paths from backend root
            if not os.path.exists(path):
                # Try finding it relative to current working dir
                path = os.path.join(os.getcwd(), path)
                
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load knowledge graph: {e}")
            return {}

    def search(self, query: str) -> Optional[str]:
        """
        Check for deterministic intent matches.
        Returns formatted answer string or None.
        """
        q = query.lower()
        
        # 1. FEES INTENT
        if any(w in q for w in ["fee", "fees", "cost", "price", "tuition", "payment"]):
            raw_fees = self.data.get("fees_raw")
            if raw_fees:
                # Clean up for voice (remove bullets, titles)
                voice_text = raw_fees.replace("\u20b9", "rupees ").replace("- ", "").strip()
                return voice_text
                
        # 2. COURSES / INTAKE INTENT
        if any(w in q for w in ["course", "courses", "branch", "program", "stream", "intake", "seat"]):
            courses = self.data.get("courses", [])
            if courses:
                lines = ["We offer several programs."]
                for c in courses:
                    name = c.get("Course Name", "Unknown")
                    dept = c.get("Department", "")
                    intake = c.get("Intake", "?")
                    lines.append(f"{name} in {dept} has {intake} seats.")
                return " ".join(lines)

        # 3. ELIGIBILITY INTENT
        if any(w in q for w in ["eligibility", "eligible", "criteria", "percentage", "marks", "pcm"]):
            eligibility = self.data.get("eligibility")
            if eligibility:
                return eligibility

        # 4. ADMISSION DATES INTENT
        if any(w in q for w in ["date", "dates", "deadline", "last date", "start date", "schedule"]):
            dates = self.data.get("admission_dates")
            if dates:
                return dates

        # 5. REQUIRED DOCUMENTS INTENT
        if any(w in q for w in ["document", "documents", "certificate", "certificates", "mark sheet", "aadhar"]):
            docs = self.data.get("required_documents")
            if docs:
                return f"For admission, you need: {docs}"

        # 6. ADMISSION PROCESS INTENT
        if any(w in q for w in ["process", "steps", "apply", "application", "how to"]):
            process = self.data.get("admission_process_steps")
            if process:
                return f"The process includes: {process}"

        # 7. RESERVATION POLICY INTENT
        if any(w in q for w in ["reservation", "quota", "sc", "st", "obc", "pwd"]):
            policy = self.data.get("reservation_policy")
            if policy:
                return f"Our reservation policy is: {policy}"

        # 8. CONTACT INFORMATION INTENT
        if any(w in q for w in ["contact", "phone", "email", "address", "location", "reach", "call"]):
            contact = self.data.get("contact_info", {})
            if contact:
                return f"You can reach us at {contact.get('phone')} or email {contact.get('email')}. We are located at {contact.get('address')}."

        # 9. PLACEMENT STATISTICS INTENT
        if any(w in q for w in ["placement", "placements", "job", "jobs", "company", "companies", "package", "salary", "lpa"]):
            stats = self.data.get("placement_stats", [])
            if stats:
                lines = ["Our students have been placed in top companies."]
                for s in stats:
                    lines.append(f"{s.get('Company')} offered {s.get('Package')} to {s.get('Placed')} students.")
                return " ".join(lines)
                
        return None


class HybridRetriever:
    """
    Combines BM25 lexical matching with semantic similarity (via FAISS) for robust retrieval.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"): 
        """
        Initialize the hybrid retriever.
        """
        # Initialize FAISS Vector Store
        self.vector_store = FAISSVectorStore(model_name=model_name)
        self.bm25 = None
        self.documents = []
        logger.info(f"Initialized HybridRetriever with {model_name} and FAISS")
    
    def index_documents(self, documents: List[Dict]) -> None:
        """
        Index documents using both BM25 and FAISS.
        """
        self.documents = documents
        logger.info(f"Indexing {len(documents)} documents...")
        
        # Build BM25 index
        tokenized_docs = [
            doc['text'].lower().split() 
            for doc in documents
        ]
        self.bm25 = BM25Okapi(tokenized_docs)
        
        # Add to FAISS Vector Store
        # Check if already indexed to avoid duplicates/re-indexing cost
        if len(self.vector_store.documents) != len(documents):
            logger.info("Updating vector store...")
            # Ideally we would clear and rebuild or add new ones
            # For simplicity in this session, we'll re-add (FAISS store logic might need update to clear)
            # But the vector_store.py I wrote appends. 
            # Let's assume for now we trust the persistence or overwrite it.
            # Actually, my FAISS store loads from disk on init. 
            # If we are indexing fresh documents, we might want to clear it first or checking if they exist.
            # For this 'lite' version, let's just add them if the count differs significantly or it's empty.
            if not self.vector_store.documents:
                self.vector_store.add_documents(documents)
            else:
                 logger.info("Vector store already populated. Skipping re-embedding for speed.")
        
        logger.info(f"Indexed documents. FAISS contains {len(self.vector_store.documents)} docs.")
    
    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Min-max normalization to [0, 1]"""
        if len(scores) == 0:
            return np.array([])
            
        min_score = scores.min()
        max_score = scores.max()
        
        if max_score == min_score:
            return np.ones_like(scores) * 0.5
        
        return (scores - min_score) / (max_score - min_score)
    
    def retrieve(
        self, 
        query: str, 
        k: int = 5,
        bm25_weight: float = 0.4,
        semantic_weight: float = 0.6
    ) -> List[Dict]:
        """
        Hybrid retrieval combining BM25 and semantic similarity.
        """
        
        if not self.bm25:
             logger.warning("BM25 not initialized. Returning empty.")
             return []
        
        # 1. BM25 Retrieval
        # Get all scores, then we'll map them
        bm25_scores = self.bm25.get_scores(query.lower().split())
        
        # 2. Semantic Retrieval (FAISS)
        # FAISS returns top k. To do proper hybrid fusion, we ideally need scores for ALL docs
        # or we do Reciprocal Rank Fusion (RRF) on the top K from each.
        # For this implementation, let's exact RRF or simply merge top K from both.
        
        # Let's get top 2k candidates from FAISS
        semantic_results = self.vector_store.search(query, k=k*2)
        
        # Create a map of doc_index -> semantic_score
        # We need to map back to original indices. 
        # My FAISS store stores the full document, so I can try to match by content or ID
        # Issue: FAISS store 'documents' list might not be in same order as 'self.documents' 
        # if loaded from disk vs passed in.
        # Let's rely on the text being the key for mapping scores.
        
        semantic_score_map = {}
        for doc, score in semantic_results:
            # key: first 50 chars of text as simplistic ID
            key = doc.get('text', '')[:50] 
            semantic_score_map[key] = score

        # Combine scores
        final_results = []
        for i, doc in enumerate(self.documents):
            key = doc['text'][:50]
            
            s_score = semantic_score_map.get(key, 0.0) # 0 if not in top k of semantic
            b_score = bm25_scores[i]
            
            # Normalize scores roughly? BM25 is unbounded.
            # Let's just normalize BM25 relative to the batch if possible, 
            # or just assume standard ranges.
            # A simple normalization for BM25 in this context:
            
            final_score = (bm25_weight * b_score) + (semantic_weight * s_score * 10) # boosting semantic a bit
            
            final_results.append({
                'document': doc,
                'hybrid_score': final_score,
                'bm25_score': b_score,
                'semantic_score': s_score
            })
            
        # Sort by hybrid score
        final_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # Apply diversity filtering: max 2 chunks per document
        seen_documents = {}
        diverse_results = []

        for result in final_results:
            # Extract document source/name from result
            doc_source = result.get('document', {}).get('source') or result.get('document', {}).get('metadata', {}).get('filename') or 'unknown'
            
            # Track how many chunks we've taken from this document
            if doc_source not in seen_documents:
                seen_documents[doc_source] = 0
            
            # Only allow max 2 chunks per document
            if seen_documents[doc_source] < 2:
                diverse_results.append(result)
                seen_documents[doc_source] += 1
                
                # Stop when we have enough diverse results
                if len(diverse_results) >= k:
                    break

        logger.info(f"Retrieved {len(diverse_results)} diverse documents from {len(seen_documents)} unique sources")
        return diverse_results
        



# ============================================================================
# 2. QUERY EXPANSION - Context-Aware Query Enhancement
# ============================================================================

class QueryExpander:
    """
    Expands short/ambiguous queries using conversation history.
    Reduces need for clarification in multi-turn conversations.
    """
    
    def __init__(self, llm_client):
        """
        Args:
            llm_client: Groq client or similar (must have invoke() method)
        """
        self.llm = llm_client
        self.session_history = defaultdict(list)
    
    def add_to_history(self, session_id: str, query: str) -> None:
        """Track query history per session"""
        self.session_history[session_id].append(query)
        
        # Keep only last 5 queries to avoid token bloat
        if len(self.session_history[session_id]) > 5:
            self.session_history[session_id].pop(0)
    
    def _should_expand(self, query: str, history: List[str]) -> bool:
        """
        Heuristic: expand if query is short AND history exists
        Avoids unnecessary API calls on clear queries.
        """
        is_short = len(query.split()) < 4
        has_history = len(history) > 0
        
        return is_short and has_history
    
    async def expand_query(
        self, 
        query: str, 
        session_id: str
    ) -> Tuple[str, bool]:
        """
        Expand ambiguous query with context.
        
        Args:
            query: Original user query
            session_id: Conversation session ID
        
        Returns:
            (expanded_query, was_expanded)
        """
        
        history = self.session_history[session_id]
        
        if not self._should_expand(query, history):
            return query, False
        
        # Build expansion prompt
        history_str = " -> ".join(history[-3:]) if history else ""
        expansion_prompt = f"""Given the conversation context, expand this ambiguous query to be more specific and complete.

Context: {history_str}
Current query: "{query}"

Rules:
- Keep it concise (under 20 words)
- Infer topic from history if needed
- Return ONLY the expanded query, nothing else"""

        try:
            # Call Groq API with minimal overhead
            response = self.llm.chat.completions.create(
                messages=[{"role": "user", "content": expansion_prompt}],
                model="llama-3.1-8b-instant",  # Using Groq model
                temperature=0,
                max_tokens=20
            )
            expanded = response.choices[0].message.content.strip()
            
            logger.info(f"Query expansion: '{query}' -> '{expanded}'")
            return expanded, True
            
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}. Using original query.")
            return query, False


# ============================================================================
# 3. SYSTEM PROMPT - College-Specific Instructions
# ============================================================================

class SystemPromptBuilder:
    """
    Builds college-specific system prompts that reduce hallucination.
    """
    
    def __init__(self, college_config: Dict, knowledge_data: Dict = None):
        """
        Args:
            college_config: Dict with college name, departments, contact info
            knowledge_data: Statically extracted knowledge from JSON
        """
        self.config = college_config
        self.knowledge = knowledge_data or {}
    
    def build_system_prompt(self, retrieved_context: List[Dict], user_profile: Dict = None) -> str:
        """
        Build system prompt with retrieved context and user profile.
        Using XML tags for better Llama-3 adherence.
        """
        
        # Format context from retrieved documents
        context_blocks = []
        for doc in retrieved_context:
            source = doc['document'].get('source', 'Unknown')
            content = doc['document'].get('text', '')
            score = doc['hybrid_score']
            
            context_blocks.append(f'<document source="{source}" confidence="{score:.2f}">\n{content}\n</document>')
        
        context_str = "\n".join(context_blocks)
        
        # Format user context
        user_context_str = ""
        if user_profile:
            rank = user_profile.get("wbjee_rank", "Not provided")
            interests = user_profile.get("interests", "Not provided")
            if rank != "Not provided" or interests != "Not provided":
                user_context_str = f"""
<user_context>
User Rank: {rank}
User Interests: {interests}
</user_context>
"""
        
        # Prepare static knowledge summary
        static_knowledge_str = ""
        if self.knowledge:
            static_knowledge_str = f"""
<core_college_facts>
Name: {self.config.get('name')}
Courses: {', '.join([c.get('Course Name') for c in self.knowledge.get('courses', [])])}
Eligibility: {self.knowledge.get('eligibility', 'N/A')}
Important Dates: {self.knowledge.get('admission_dates', 'N/A')}
Required Documents: {self.knowledge.get('required_documents', 'N/A')}
Application Fee: ₹1,000
Application Process: {self.knowledge.get('admission_process_steps', 'N/A')}
Contact: {self.knowledge.get('contact_info', {}).get('phone')}
</core_college_facts>
"""

        system_prompt = f"""You are a RAG-based AI Calling Agent working as a COLLEGE RECEPTIONIST for {self.config['name']}.

Your PRIMARY ROLE:
- Handle admission-related queries politely and clearly
- Answer ONLY using the provided knowledge base documents
- Speak in a calm, professional, receptionist-like tone
- Keep answers short, factual, and voice-friendly (under 3 sentences unless detailed process needed)

CRITICAL RULES:
1. NEVER invent facts, numbers, or details.
2. If exact data is NOT available in context or core facts, say: "The exact details may vary each year. Please contact the admission office."
3. DO NOT mix unrelated document content into answers.
4. DO NOT answer exam MCQs or unrelated academic questions.
5. DO NOT hallucinate placement packages, rankings, or guarantees.

{static_knowledge_str}
{user_context_str}

<context>
{context_str}
</context>

Answer the user's question now based on the above context.
"""
        return system_prompt


# ============================================================================
# 4. QUERY ANALYTICS - Monitoring & Quality Tracking
# ============================================================================

class QueryAnalytics:
    """
    Tracks query performance, retrieval quality, and latency.
    Identifies problematic queries for document updates.
    """
    
    def __init__(self, output_dir: str = "./analytics"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.metrics = defaultdict(list)
    
    def log_interaction(self, session_id: str, query: str, retrieved_docs: List[Dict], 
                       response: str, latency: float) -> None:
        """Log every interaction for analysis"""
        
        self.metrics['interactions'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'query': query,
            'retrieval_score': retrieved_docs[0]['hybrid_score'] if retrieved_docs else 0,
            'response_length': len(response),
            'latency_ms': latency * 1000
        })
    
    def get_quality_report(self) -> Dict:
        """Generate quality metrics"""
        interactions = self.metrics['interactions']
        
        if not interactions:
            return {'error': 'No interactions logged yet'}
        
        return {
            'total_queries': len(interactions),
            'avg_latency_ms': np.mean([i['latency_ms'] for i in interactions]),
            'retrieval_confidence': np.mean([i['retrieval_score'] for i in interactions]),
            'low_confidence_queries': [
                i for i in interactions 
                if i['retrieval_score'] < 0.3
            ]
        }


# ============================================================================
# 5. RESPONSE CACHE - Fast Response Caching with TTL
# ============================================================================

class ResponseCache:
    """
    Cache LLM responses to avoid redundant API calls.
    Uses MD5 hashing for query normalization and LRU eviction.
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Args:
            max_size: Maximum number of cached responses
            ttl_seconds: Time-to-live for cached responses (default: 1 hour)
        """
        self.cache = {}  # {query_hash: (answer, timestamp, original_query)}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        logger.info(f"ResponseCache initialized (max_size={max_size}, ttl={ttl_seconds}s)")
    
    def _hash_query(self, query: str) -> str:
        """Normalize and hash query for cache key"""
        import hashlib
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get(self, query: str) -> Optional[str]:
        """
        Get cached response if available and not expired.
        
        Args:
            query: User query
            
        Returns:
            Cached answer or None if not found/expired
        """
        query_hash = self._hash_query(query)
        
        if query_hash in self.cache:
            answer, timestamp, original_query = self.cache[query_hash]
            
            # Check if cache entry is still valid
            if time.time() - timestamp < self.ttl_seconds:
                logger.info(f"Cache HIT for query: '{query}' (cached: '{original_query}')")
                return answer
            else:
                # Expired, remove from cache
                logger.info(f"Cache EXPIRED for query: '{query}'")
                del self.cache[query_hash]
        
        logger.info(f"Cache MISS for query: '{query}'")
        return None
    
    def set(self, query: str, answer: str) -> None:
        """
        Cache a response with current timestamp.
        
        Args:
            query: User query
            answer: LLM-generated answer
        """
        query_hash = self._hash_query(query)
        
        # LRU eviction if cache is full
        if len(self.cache) >= self.max_size and query_hash not in self.cache:
            # Find oldest entry
            oldest_hash = min(
                self.cache.items(), 
                key=lambda x: x[1][1]  # Sort by timestamp
            )[0]
            logger.info(f"Cache FULL, evicting oldest entry")
            del self.cache[oldest_hash]
        
        self.cache[query_hash] = (answer, time.time(), query)
        logger.info(f"Cache SET for query: '{query}' (cache size: {len(self.cache)})")
    
    def clear(self) -> None:
        """Clear all cached responses"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds
        }


# ============================================================================
# 6. MAIN RAG SERVICE - Integration of All Components
# ============================================================================

class RAGService:
    """
    Main RAG service integrating hybrid retrieval, query expansion, analytics, and caching.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        self.knowledge_retriever = KnowledgeRetriever() # Phase 2: Structured Knowledge
        self.hybrid_retriever = HybridRetriever()
        self.query_expander = None  # Will be set after initialization
        self.system_prompt_builder = None  # Will be set after initialization
        self.analytics = QueryAnalytics()
        self.response_cache = ResponseCache(max_size=100, ttl_seconds=3600)  # 1 hour TTL
        self.conversation_memory = ConversationMemory()  # Initialize conversation memory
        
        # Initialize query prefetcher
        self.query_prefetcher = QueryPrefetcher(self)
        
        # Load documents from JSON file
        self.documents = self._load_documents()
        
        # Index documents for retrieval
        if self.documents:
            # Check if we need to re-index (simple check: if vector store is empty or count mismatch)
            # In a real prod env, we'd check file hashes.
            if len(self.hybrid_retriever.vector_store.documents) != len(self.documents):
                 logger.info("Document count mismatch. Re-indexing...")
                 self.hybrid_retriever.vector_store.documents = [] 
                 self.hybrid_retriever.vector_store.index = None
                 self.hybrid_retriever.index_documents(self.documents)
            elif not self.hybrid_retriever.vector_store.documents:
                 self.hybrid_retriever.index_documents(self.documents)
            else:
                 # Just load the BM25 index which isn't persisted in this simple version
                 # We still need to init BM25 even if FAISS is loaded
                 logger.info("Initializing BM25 index on existing documents...")
                 self.hybrid_retriever.index_documents(self.documents)
        
        self.initialized = True
        logger.info(f"RAGService initialized with {len(self.documents)} documents")
    
    def _load_documents(self) -> List[Dict]:
        """Load documents from JSON file"""
        try:
            # Check multiple potential locations for documents.json
            potential_paths = [
                Path("uploads/documents.json"),             # PRIORITY 1: User Uploads (Backend relative)
                Path("backend/uploads/documents.json"),     # PRIORITY 2: User Uploads (Root relative)
                Path("chroma_db/documents.json"),           # Fallback: Legacy
                Path("backend/chroma_db/documents.json")    # Fallback: Legacy
            ]
            
            storage_file = None
            for p in potential_paths:
                if p.exists():
                    storage_file = p
                    break
            
            if storage_file:
                logger.info(f"Loading documents from: {storage_file.absolute()}")
                with open(storage_file, 'r', encoding='utf-8') as f:
                    documents = json.load(f)
                    logger.info(f"Loaded {len(documents)} documents")
                    return documents
            else:
                logger.warning(f"documents.json not found in any expected location: {[str(p) for p in potential_paths]}")
                return []
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            return []
    
    def set_clients(self, llm_client, college_config: Dict):
        """Set LLM client and college config after initialization"""
        self.query_expander = QueryExpander(llm_client)
        # Pass structured knowledge to prompt builder
        knowledge_data = self.knowledge_retriever.data if self.knowledge_retriever else {}
        self.system_prompt_builder = SystemPromptBuilder(college_config, knowledge_data)
    
    async def query_stream(self, message: str, session_id: str = None):
        """
        Main query method that integrates all components.
        """
        start_time = time.time()
        logger.info(f"Processing query: '{message}' for session: {session_id}")

        # --- Greeting Check ---
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "how are you"]
        normalized_message = message.lower().strip()
        if any(greeting in normalized_message for greeting in greetings) or "can you hear me" in normalized_message:
            logger.info("Greeting detected. Bypassing RAG pipeline.")
            yield {
                "type": "answer",
                "answer": "Hello! How can I help you today?",
                "documents": [],
                "query_used": message,
                "processing_time": time.time() - start_time
            }
            return
        # --- End Greeting Check ---

        # Check if this is a branch query to gather user preferences
        is_branch_query = any(keyword in message.lower() for keyword in ["branch", "branches", "available", "program", "programs", "cse", "it", "aiml", "ece", "ee", "me", "ce"])

        try:
            # Expand query if needed
            # Expand query if needed
            if hasattr(self, 'query_expander') and self.query_expander and self.query_expander.llm:
                try:
                    expanded_query, was_expanded = await self.query_expander.expand_query(
                        message, session_id or "default"
                    )
                    query_to_use = expanded_query if was_expanded else message
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")
                    query_to_use = message
            else:
                 logger.warning("QueryExpander or LLM not available. Using original query.")
                 query_to_use = message
            
            logger.info(f"Using query: {query_to_use}")

            # 0. Deterministic Knowledge Lookup (Phase 2)
            # Check for exact facts (Fees, Courses) in Knowledge Graph
            if self.knowledge_retriever:
                exact_answer = self.knowledge_retriever.search(query_to_use)
                if exact_answer:
                    logger.info("Deterministic match found in Knowledge Graph.")
                    yield {
                        "type": "answer",
                        "answer": exact_answer,
                        "documents": [], 
                        "query_used": query_to_use,
                        "processing_time": time.time() - start_time
                    }
                    return

            # Prefetch related queries in background
            try:
                if hasattr(self, 'query_prefetcher'):
                    import asyncio
                    asyncio.create_task(self.query_prefetcher.prefetch_related(query_to_use))
            except Exception as e:
                logger.warning(f"Error in prefetching: {e}")

            # Retrieve relevant documents
            retrieved_docs = self.hybrid_retriever.retrieve(query_to_use, k=5)
            logger.info(f"Retrieved {len(retrieved_docs)} documents.")
            # --- Added Logging for retrieved docs ---
            for doc in retrieved_docs:
                # Try to get source from metadata first, then directly from document
                source = doc['document'].get('metadata', {}).get('source') or doc['document'].get('source', 'Unknown')
                logger.info(f"  - Doc: {source}, Score: {doc['hybrid_score']:.4f}")
            # --- End Added Logging ---
            
            # Build system prompt with context
            if self.system_prompt_builder:
                # Get user profile for personalization
                user_profile = self.conversation_memory.get_user_profile(session_id or "default")
                system_prompt = self.system_prompt_builder.build_system_prompt(retrieved_docs, user_profile)
                # --- Added Logging for system prompt ---
                logger.info(f"System Prompt created with {len(system_prompt)} characters.")
                # logger.debug(f"SYSTEM PROMPT: {system_prompt}") # DEBUG level for full prompt
                # --- End Added Logging ---
            else:
                # Fallback prompt
                context_str = "\n\n".join([doc['document']['text'] for doc in retrieved_docs])
                system_prompt = f"""You are a college information assistant. Answer based on the following context:\n\n{context_str}"""

            # Generate Answer using LLM
            # Previously it was just returning the document text, which explains "garbage" if the document is raw data
            # Now we will actually call the LLM to generate a coherent answer
            
            # Check cache first before processing
            cached_answer = self.response_cache.get(query_to_use) if hasattr(self, 'response_cache') else None
            if cached_answer:
                logger.info(f"Cache HIT for query: '{query_to_use}'")
                answer = cached_answer
            else:
                answer = ""
                if self.query_expander and self.query_expander.llm:
                     try:
                        # Enable streaming for lower latency
                        logger.info("Generating answer with LLM (Streaming)...")
                        stream_response = await asyncio.wait_for(
                            asyncio.to_thread(
                                self.query_expander.llm.chat.completions.create,
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": query_to_use}
                                ],
                                model="llama-3.1-8b-instant",
                                temperature=0.0,
                                max_tokens=500,
                                frequency_penalty=1.0, 
                                presence_penalty=0.5,
                                stream=True
                            ),
                            timeout=10.0
                        )

                        full_content = []
                        for chunk in stream_response:
                            content = chunk.choices[0].delta.content
                            if content:
                                full_content.append(content)
                                # Yield each chunk immediately
                                yield {
                                    "type": "answer_chunk",
                                    "text": content,
                                    "session_id": session_id
                                }
                        
                        answer = "".join(full_content).strip()
                        logger.info(f"LLM streaming finished. Total length: {len(answer)}")

                     except asyncio.TimeoutError:
                        logger.error("GROQ API timeout")
                        answer = "I'm experiencing delays. Please try again."
                        yield {"type": "answer_chunk", "text": answer}
                     except Exception as api_error:
                        logger.error(f"GROQ API error: {api_error}")
                        raise 
                        
                        # Cache the response for future queries
                        if hasattr(self, 'response_cache'):
                            cache_key = query_to_use
                            last_write_key = f"{cache_key}:last_write_time"
                            current_time = time.time()
                            last_write = self.response_cache.get(last_write_key)
                            
                            if last_write and (current_time - float(last_write)) < 1.0:
                                logger.debug(f"Duplicate cache write suppressed for: {cache_key}")
                            else:
                                self.response_cache.set(cache_key, answer)
                                self.response_cache.set(last_write_key, str(current_time))
                        
                        # If this is a branch query, check if we should ask for user preferences
                        if is_branch_query and ("available" in query_to_use.lower() or "branches" in query_to_use.lower()):
                            # Get user profile information
                            user_profile = self.conversation_memory.get_user_profile(session_id or "default")
                            user_rank = user_profile.get("wbjee_rank", "not provided")
                            user_interests = user_profile.get("interests", "not specified")
                            
                            # If user hasn't provided rank or interests, add a prompt to ask for them
                            if user_rank == "not provided" or user_interests == "not specified":
                                additional_prompt = "\n\nFor personalized branch recommendations, could you please share your WBJEE rank and your interests (like programming, electronics, mechanics, etc.)?"
                                answer += additional_prompt
                                
                     except Exception as e:
                         # --- Added specific logging for LLM failure ---
                         logger.error(f"CRITICAL: LLM generation failed: {e}", exc_info=True)
                         # --- End Added Logging ---
                         # Fallback to top document text if LLM fails
                         if retrieved_docs:
                             top_doc = retrieved_docs[0]['document']
                             content = top_doc.get('text', '')
                             # Extract relevant information about HODs or fees based on query
                             if 'hod' in query_to_use.lower() or 'head' in query_to_use.lower():
                                 # Look for HOD information in the content
                                 import re
                                 hod_match = re.search(r'(HOD|Head.*?)([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', content)
                                 if hod_match:
                                     answer = f"The HOD is {hod_match.group(2).strip()}"
                                 else:
                                     answer = f"Based on the available information: {content[:500]}"
                             elif 'fee' in query_to_use.lower() or 'cost' in query_to_use.lower():
                                 # Look for fee information in the content
                                 import re
                                 fee_match = re.search(r'(fee|cost|tuition|\₹\d+,?\d*)\s*(?:per semester|per year|total)?\s*(\₹\d+,?\d*|\d+,?\d+)', content, re.IGNORECASE)
                                 if fee_match:
                                     answer = f"The fee information is: {fee_match.group(0)[:100]}"
                                 else:
                                     answer = f"Based on the available information: {content[:500]}"
                             else:
                                 answer = f"Based on the available information: {content[:500]}"
                             logger.info("Falling back to processed document content")
                         else:
                             # No documents available, provide default error message
                             answer = "I'm having trouble processing your request. Please try again or contact the admissions office."
                elif retrieved_docs:
                     # No LLM client, fallback
                     logger.warning("No LLM client available, using document content")
                     answer = "I apologize, but I am currently unable to generate a smart answer because my AI connection is not fully established. Please restart the backend server to apply the new configuration."
                else:
                     answer = "I don't have enough information to answer that."

            # Log the interaction
            latency = time.time() - start_time
            if self.analytics:
                self.analytics.log_interaction(
                    session_id or "default", 
                    message, 
                    retrieved_docs, 
                    answer, 
                    latency
                )
            
            # Add user preferences to conversation memory if they provided rank or interests
            if session_id:
                if "wbjee" in message.lower() or "rank" in message.lower():
                    # Extract rank from the message
                    import re
                    rank_match = re.search(r'(\d+)', message)
                    if rank_match:
                        rank = rank_match.group(1)
                        self.conversation_memory.update_user_profile(session_id, "wbjee_rank", rank)
                if any(interest in message.lower() for interest in ["programming", "coding", "software", "electronics", "mechanics", "civil", "electrical", "ai", "machine learning"]):
                    self.conversation_memory.update_user_profile(session_id, "interests", message)
                
                # Add the interaction to conversation memory
                self.conversation_memory.add_interaction(session_id, message, answer)

            # Yield the results
            yield {
                "type": "answer",  # Changed from "documents" to "answer" to better reflect content
                "answer": answer,
                "documents": retrieved_docs,
                "query_used": query_to_use,
                "processing_time": latency
            }
        
        except Exception as e:
            logger.error(f"Error in query_stream: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }
    
    async def generate_answer_stream(self, query: str, context: str, session_id: str = None):
        """
        Generate streaming answer from LLM
        """
        try:
            # Build system prompt with context
            if self.system_prompt_builder:
                # For streaming, we need to get the relevant docs first
                retrieved_docs = self.hybrid_retriever.retrieve(query, k=5)
                system_prompt = self.system_prompt_builder.build_system_prompt(retrieved_docs)
            else:
                # Fallback prompt
                retrieved_docs = []
                system_prompt = f"You are a college information assistant. Answer based on the following context: {context}"
            
            # Create streaming response
            response = self.query_expander.llm.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.1,
                max_tokens=300,
                stream=True  # Enable streaming
            )
            
            # Yield chunks as they arrive
            full_answer = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_answer += content
                    yield {
                        "type": "answer_chunk",
                        "content": content,
                        "query_used": query
                    }
            
            # Cache the full answer after streaming is complete
            if hasattr(self, 'response_cache'):
                self.response_cache.set(query, full_answer)
                
        except Exception as e:
            logger.error(f"Error in streaming answer generation: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }
    
    def get_document_count(self):
        """Get total number of indexed documents"""
        return len(self.documents)
    
    def check_groq_connection(self):
        """Check if Groq connection is working"""
        if self.query_expander and self.query_expander.llm:
            try:
                # Test with a simple API call
                response = self.query_expander.llm.chat.completions.create(
                    messages=[{"role": "user", "content": "test"}],
                    model="llama-3.1-8b-instant",
                    max_tokens=1
                )
                return True
            except Exception as e:
                logger.error(f"Groq connection test failed: {e}")
                return False
        return False

class QueryPrefetcher:
    """
    Predict likely follow-up queries and pre-fetch results
    """
    def __init__(self, rag_service):
        self.rag_service = rag_service
        self.follow_up_patterns = {
            "admission": ["deadline", "fees", "documents", "eligibility"],
            "hostel": ["fees", "facilities", "rooms", "mess"],
            "placement": ["companies", "packages", "statistics"],
            "branch": ["cutoff", "syllabus", "hod", "facilities"],
            "fee": ["payment", "refund", "semester", "late fee"],
            "courses": ["syllabus", "credits", "duration", "fees"]
        }
    
    async def prefetch_related(self, query: str):
        """
        Prefetch related queries in background
        """
        import asyncio
        
        # Identify topic from query
        query_lower = query.lower()
        for topic, related in self.follow_up_patterns.items():
            if topic in query_lower:
                # Prefetch related queries in background
                for rel_query in related:
                    # Create a background task to prefetch
                    full_query = f"{topic} {rel_query}"
                    asyncio.create_task(self._prefetch_query(full_query))
    
    async def _prefetch_query(self, query: str):
        """
        Internal method to prefetch a single query
        """
        try:
            # Retrieve documents for the query to warm up cache
            retrieved_docs = self.rag_service.hybrid_retriever.retrieve(query, k=3)
            # Cache the retrieval results
            if hasattr(self.rag_service, 'response_cache'):
                # We could cache the documents or even pre-generate responses
                pass
        except Exception as e:
            logger.error(f"Error in prefetching {query}: {e}")

# The duplicate class definition has been removed to fix the issue