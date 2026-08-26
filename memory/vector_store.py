# Vector Store Memory (vector_store.py)
# Supports ChromaDB (default, pip install chromadb sentence-transformers) and FAISS 
# (pip install faiss-cpu). The provider is selected via the MEMORY_VECTOR_PROVIDER 
# environment variable.

import os
import uuid
from memory.base_memory import BaseMemory


class VectorStoreMemory(BaseMemory):
    """
    Embedding-based vector memory.
    Provider: 'chroma' (default) or 'faiss'.
    ChromaDB: pip install chromadb sentence-transformers
    FAISS:    pip install faiss-cpu sentence-transformers
    """

    def __init__(
        self,
        provider: str = "chroma",
        collection_name: str = "agent_playpen",
        persist_dir: str = "./chroma_data",
        embed_model: str = "all-MiniLM-L6-v2",
    ):
        self.provider = provider
        self.embed_model = embed_model
        self._items = []   # Used by FAISS provider

        if provider == "chroma":
            import chromadb
            client = chromadb.PersistentClient(path=persist_dir)
            self._collection = client.get_or_create_collection(collection_name)
        elif provider == "faiss":
            import faiss
            from sentence_transformers import SentenceTransformer
            self._st = SentenceTransformer(embed_model)
            dim = self._st.get_sentence_embedding_dimension()
            self._index = faiss.IndexFlatL2(dim)

    def _embed(self, text: str) -> list:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(self.embed_model)
        return model.encode([text])[0].tolist()

    def add(self, text: str, metadata: dict = None) -> str:
        doc_id = str(uuid.uuid4())
        if self.provider == "chroma":
            self._collection.add(
                documents=[text],
                metadatas=[metadata or {}],
                ids=[doc_id],
            )
        elif self.provider == "faiss":
            import numpy as np
            vec = self._st.encode([text])
            self._index.add(np.array(vec, dtype="float32"))
            self._items.append({"id": doc_id, "text": text, "meta": metadata or {}})
        return doc_id

    def query(self, text: str, top_k: int = 5) -> list:
        if self.provider == "chroma":
            results = self._collection.query(
                query_texts=[text], n_results=top_k
            )
            docs = results.get("documents", [[]])[0]
            return docs
        elif self.provider == "faiss":
            import numpy as np
            vec = self._st.encode([text])
            distances, indices = self._index.search(
                np.array(vec, dtype="float32"), top_k
            )
            return [self._items[i]["text"] for i in indices[0] if i < len(self._items)]
        return []

    def delete(self, doc_id: str) -> None:
        if self.provider == "chroma":
            self._collection.delete(ids=[doc_id])

    def persist(self) -> None:
        """ChromaDB auto-persists. FAISS requires manual save."""
        if self.provider == "faiss":
            import faiss
            faiss.write_index(self._index, "faiss_index.bin")

    def store(self, key: str, value: str) -> None:
        self.add(value, metadata={"key": key})

    def retrieve(self, query: str, top_k: int = 5) -> list:
        return self.query(query, top_k)
    