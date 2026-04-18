from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

# Sample context from our DB
context = [
    "Course: BCA, Type: Undergraduate, Department: Computer Science",
    "Course: ADCA, Type: Diploma, Department: Computer Science",
    "Course: Forensic Science, Type: Certification, Department: Science",
    "Admission 2026 Latest News and Deadlines"
]

# User queries
queries = [
    "कौन-से सर्टिफिकेशन कोर्स उपलब्ध हैं?",
    "BCA fees kya hai?",
    "Who is the HOD?"
]

print("Testing Semantic Similarity...")
context_embeddings = model.encode(context)

for q in queries:
    q_emb = model.encode(q)
    sims = np.dot(context_embeddings, q_emb)
    best_idx = np.argmax(sims)
    print(f"Query: {q}")
    print(f"Best Match: {context[best_idx]} (Score: {sims[best_idx]:.4f})")
    print("-" * 30)
