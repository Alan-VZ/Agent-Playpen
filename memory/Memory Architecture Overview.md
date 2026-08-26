# Memory Architecture Overview

+---------------------+     +---------------------+
|   Working Memory    |     |   Episodic Memory   |
|   (current session  |     |   (past sessions,   |
|    scratchpad)      |     |    summaries, tags) |
+---------------------+     +---------------------+
           |                          |
           +------------+-------------+
                        |
                        v
               +-----------------+
               |  MemoryManager  |
               |  (unified API)  |
               +-----------------+
                        |
           +------------+-------------+
           |                          |
           v                          v
+---------------------+     +---------------------+
|   Semantic Memory   |     |   Vector Store      |
|   (long-term facts, |     |   (ChromaDB/FAISS   |
|    remember/recall) |     |    embeddings)      |
+---------------------+     +---------------------+
