import os
from pinecone import Pinecone
from dotenv import load_dotenv
from typing import List, Dict, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

class RAGService:
    def __init__(
        self,
        index_name: str = "3am-talks-rag",
        namespace: str = "default",
        top_k: int = 3
    ):
        self.index_name = index_name
        self.namespace = namespace
        self.top_k = top_k
        self.pc = None
        self.index = None
        self._initialize_pinecone()
    
    def _initialize_pinecone(self):
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key or api_key == "your_api_key_here":
            logger.error("PINECONE_API_KEY not found or not set in .env file")
            raise ValueError("PINECONE_API_KEY is required")
        
        try:
            logger.info("Initializing Pinecone RAG service")
            self.pc = Pinecone(api_key=api_key)
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise
    
    def retrieve_relevant_techniques(
        self,
        query: str,
        issue_tags: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> List[Dict]:
        if not query:
            return []
        
        k = top_k if top_k is not None else self.top_k
        
        try:
            # Use Pinecone SDK inference for server-side embedding
            from .pinecone_engine import search_with_inference
            
            # Build filter if needed
            filter_dict = None
            if issue_tags and len(issue_tags) > 0:
                filter_dict = {"issue_tags": {"$in": issue_tags}}
            
            # Query using inference embedding
            techniques = search_with_inference(
                pc_client=self.pc,
                index=self.index,
                namespace=self.namespace,
                query_text=query,
                top_k=k,
                filter_dict=filter_dict
            )
            
            return techniques
            
        except Exception as e:
            logger.error(f"Error retrieving techniques: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def format_techniques_for_prompt(self, techniques: List[Dict]) -> str:
        if not techniques:
            return ""
        
        formatted = "## Relevant Therapeutic Techniques\n\n"
        
        for idx, tech in enumerate(techniques, 1):
            metadata = tech.get("metadata", {})
            technique_name = metadata.get("technique_name", "Unknown Technique")
            modality = metadata.get("modality", "")
            difficulty = metadata.get("difficulty", "")
            
            formatted += f"### {idx}. {technique_name}"
            if modality:
                formatted += f" ({modality})"
            if difficulty:
                formatted += f" - {difficulty} Level"
            formatted += "\n\n"
            
            # Add technique content (truncated if too long)
            text = tech.get("text", "")
            if len(text) > 800:
                text = text[:800] + "..."
            formatted += f"{text}\n\n"
            
            # Add culture notes if present
            culture_notes = metadata.get("culture_notes")
            if culture_notes:
                formatted += f"*Cultural Considerations: {culture_notes}*\n\n"
            
            formatted += "---\n\n"
        
        return formatted
    
    def retrieve_and_format(
        self,
        query: str,
        issue_tags: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        top_k: Optional[int] = None
    ) -> str:
        techniques = self.retrieve_relevant_techniques(
            query=query,
            issue_tags=issue_tags,
            difficulty=difficulty,
            top_k=top_k
        )
        return self.format_techniques_for_prompt(techniques)
