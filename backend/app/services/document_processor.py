import os
from typing import List, Dict, Any
import logging
from pathlib import Path
import json
import re

# Import optional dependencies
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
    
    async def process_file(self, file_path: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Process a file and return a list of document chunks.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File {file_path} not found")
            
        ext = file_path.suffix.lower()
        content = ""
        
        try:
            if ext == '.pdf':
                content = self._process_pdf(file_path)
            elif ext in ['.csv', '.xlsx', '.xls']:
                content = self._process_spreadsheet(file_path)
            elif ext == '.txt':
                content = self._process_txt(file_path)
            else:
                # Try as text for other extensions
                content = self._process_txt(file_path)
                
            # Simple chunking by paragraphs or size
            chunks = self._chunk_text(content)
            
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append({
                    "text": chunk,
                    "source": file_path.name,
                    "metadata": {
                        **(metadata or {}),
                        "chunk_id": i,
                        "file_type": ext
                    }
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise

    def _process_pdf(self, file_path: Path) -> str:
        if not pypdf:
            raise ImportError("pypdf is required for PDF processing")
        
        text = ""
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text

    def _process_spreadsheet(self, file_path: Path) -> str:
        if not pd:
            raise ImportError("pandas is required for spreadsheet processing")
            
        if file_path.suffix == '.csv':
            df = pd.read_csv(file_path)
        else:
            if not openpyxl and file_path.suffix in ['.xlsx', '.xlsm']:
                 raise ImportError("openpyxl is required for Excel processing")
            df = pd.read_excel(file_path)
            
        # Convert to string representation
        return df.to_string(index=False)

    def _process_txt(self, file_path: Path) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Smart Recursive Chunking (The 'Brain' for Structure).
        Prioritizes splitting by Paragraphs -> Sentences -> Words to preserve meaning.
        """
        if not text:
            return []

        # List of separators to try in order (Semantic Hierarchy)
        separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]
        
        def _split_text(text_segment: str, separator_idx: int) -> List[str]:
            # Base case: if we ran out of separators, return the text as is (or char split)
            if separator_idx >= len(separators):
                return [text_segment]
            
            separator = separators[separator_idx]
            
            # If separator is empty string, just split by character (last resort)
            if separator == "":
                return list(text_segment)
                
            # Split current segment
            splits = text_segment.split(separator)
            final_chunks = []
            current_buffer = []
            current_len = 0
            
            for split in splits:
                # Add back the separator if it's not whitespace (to preserve punctuation)
                if separator.strip(): 
                    split += separator.strip()
                    
                split_len = len(split)
                
                # If this single split is huge, we need to recurse down to the next separator level
                if split_len > chunk_size:
                    # First, flush any buffer we have
                    if current_buffer:
                        joined_buffer = "".join(current_buffer)
                        final_chunks.append(joined_buffer)
                        current_buffer = []
                        current_len = 0
                    
                    # Recurse on this large chunk
                    sub_chunks = _split_text(split, separator_idx + 1)
                    final_chunks.extend(sub_chunks)
                    continue
                
                # Standard accumulation
                if current_len + split_len > chunk_size:
                    # Flush buffer
                    joined_buffer = "".join(current_buffer)
                    final_chunks.append(joined_buffer)
                    
                    # Handle Overlap (Concept: Keep the tail of the previous chunk)
                    if overlap > 0 and len(joined_buffer) > overlap:
                        # Simple overlap: approximate by characters
                        # Ideally we'd be smarter here, but simple character overlap is robust enough
                        overlap_buffer = [joined_buffer[-overlap:]]
                        current_buffer = overlap_buffer + [split]
                        current_len = len(joined_buffer[-overlap:]) + len(split)
                    else:
                        current_buffer = [split]
                        current_len = len(split)
                else:
                    current_buffer.append(split)
                    current_len += len(split)
            
            # Flush remaining
            if current_buffer:
                final_chunks.append("".join(current_buffer))
                
            return final_chunks

        # Clean text slightly before processing
        text = re.sub(r'[ \t]+', ' ', text) # Normalise spaces
        
        return _split_text(text, 0)
    
    async def process_files_batch(self, file_paths: List[str], metadata_list: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Process multiple files in parallel for better performance.
        """
        import asyncio
        
        if metadata_list is None:
            metadata_list = [None] * len(file_paths)
        elif len(metadata_list) != len(file_paths):
            raise ValueError("metadata_list must have same length as file_paths")
        
        # Create tasks for parallel processing
        tasks = [
            self.process_file(file_path, metadata) 
            for file_path, metadata in zip(file_paths, metadata_list)
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results and handle any exceptions
        all_documents = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing file {file_paths[i]}: {result}")
                continue
            all_documents.extend(result)
        
        return all_documents
