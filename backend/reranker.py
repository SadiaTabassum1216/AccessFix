from sentence_transformers import CrossEncoder
import logging

logger = logging.getLogger(__name__)

class CrossEncoderReranker:
    def __init__(self, model_name='cross-encoder/ms-marco-MiniLM-L-6-v2'):
        logger.info(f"Loading Cross-Encoder model: {model_name}")
        try:
            self.model = CrossEncoder(model_name)
        except Exception as e:
            logger.error(f"Failed to load Cross-Encoder model: {e}")
            self.model = None

    def rerank(self, query, documents, top_k=3):
        if not self.model or not documents:
            return documents[:top_k]

        # Prepare pairs for the cross-encoder: (query, document_text)
        # Assuming documents are ChromaDB-style (list of strings or list of dicts with 'text')
        doc_texts = [doc if isinstance(doc, str) else doc.get('text', str(doc)) for doc in documents]
        pairs = [[query, text] for text in doc_texts]

        # Predict scores
        scores = self.model.predict(pairs)

        # Pair documents with scores and sort
        scored_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

        logger.info(f"Reranked {len(documents)} documents. Top score: {scored_docs[0][1] if scored_docs else 'N/A'}")
        
        return [doc for doc, score in scored_docs[:top_k]]
