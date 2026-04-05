import os
import sys
import asyncio
from app.services.document_processor import DocumentProcessor
from app.services.rag import RAGService
from app.config import settings

# Setup basic logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reindex_documents():
    """Re-process all files in the uploads directory."""
    
    upload_dir = settings.upload_dir
    if not os.path.exists(upload_dir):
        logger.error(f"Upload directory not found: {upload_dir}")
        return

    logger.info(f"Starting re-indexing from: {upload_dir}")
    
    processor = DocumentProcessor()
    rag = RAGService()
    
    # Clear existing documents
    rag.documents = []
    
    files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    
    for filename in files:
        file_path = os.path.join(upload_dir, filename)
        logger.info(f"Processing: {filename}")
        
        try:
            chunks = processor.process_file(file_path)
            rag.add_documents(chunks)
            logger.info(f"  -> Added {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"  -> Failed to process {filename}: {e}")
            
    logger.info("Re-indexing complete!")
    logger.info(f"Total documents in DB: {len(rag.documents)}")

if __name__ == "__main__":
    # Add backend to path so imports work
    sys.path.append(os.getcwd())
    asyncio.run(reindex_documents())
