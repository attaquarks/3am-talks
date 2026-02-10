import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def search_with_inference(
    pc_client,
    index,
    namespace: str,
    query_text: str,
    top_k: int = 3,
    filter_dict: Optional[Dict] = None
) -> List[Dict]:
    try:
        # Use Pinecone inference API to embed the query
        # Use Pinecone inference API to embed the query
        
        logger.info(f"Embedding query: {query_text[:100]}...")
        
        # Embed the query using the index's inference model (llama-text-embed-v2)
        query_embeddings = pc_client.inference.embed(
            model="llama-text-embed-v2",
            inputs=[query_text],
            parameters={
                "input_type": "query",
                "truncate": "END"
            }
        )
        
        # Extract the embedding vector
        if hasattr(query_embeddings, 'data') and len(query_embeddings.data) > 0:
            query_vector = query_embeddings.data[0].values
        elif hasattr(query_embeddings, 'values'):
            query_vector = query_embeddings.values[0]
        else:
            # Fallback: try to access as list
            query_vector = query_embeddings[0].get('values', [])
        
        if not query_vector or len(query_vector) == 0:
            logger.error("Failed to generate query embedding")
            return []
        
        logger.info(f"Generated embedding vector of dimension {len(query_vector)}")
        
        # Now query the index with the embedded vector
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
            filter=filter_dict
        )
        
        # Parse results
        techniques = []
        if hasattr(results, 'matches') and results.matches:
            logger.info(f"Retrieved {len(results.matches)} relevant techniques:")
            for idx, match in enumerate(results.matches, 1):
                technique = {
                    "id": match.id,
                    "score": match.score,
                    "text": match.metadata.get('text', ''),
                    "metadata": match.metadata
                }
                techniques.append(technique)
                
                # Log detailed technique info
                tech_name = match.metadata.get('technique_name', match.id)
                modality = match.metadata.get('modality', 'Unknown')
                logger.info(f"  [{idx}] {tech_name} ({modality}) - Similarity: {match.score:.4f} - ID: {match.id}")
        else:
            logger.warning("No results returned from Pinecone")
        
        return techniques
        
    except Exception as e:
        logger.error(f"Error in inference search: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
