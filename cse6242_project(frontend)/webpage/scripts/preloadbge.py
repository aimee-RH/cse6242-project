# scripts/preload_bge.py
from sentence_transformers import SentenceTransformer
import time

print("开始下载 BGE-M3 (约 2.3GB)...")
t0 = time.time()
model = SentenceTransformer("BAAI/bge-m3", device="mps")
elapsed = time.time() - t0
print(f"✅ 加载完成，耗时 {elapsed:.1f} 秒")

# 小测试
test_texts = [
    "Machine learning is a subfield of AI",
    "深度学习是机器学习的一个分支",
    "Graph neural networks for molecular property prediction",
]
embeddings = model.encode(test_texts)
print(f"✅ Embedding 维度: {embeddings.shape}")
print(f"   第一个向量前 5 维: {embeddings[0][:5]}")# scripts/preload_bge.py
from sentence_transformers import SentenceTransformer
import time

print("开始下载 BGE-M3 (约 2.3GB)...")
t0 = time.time()
model = SentenceTransformer("BAAI/bge-m3", device="mps")
elapsed = time.time() - t0
print(f"✅ 加载完成，耗时 {elapsed:.1f} 秒")

# 小测试
test_texts = [
    "Machine learning is a subfield of AI",
    "深度学习是机器学习的一个分支",
    "Graph neural networks for molecular property prediction",
]
embeddings = model.encode(test_texts)
print(f"✅ Embedding 维度: {embeddings.shape}")
print(f"   第一个向量前 5 维: {embeddings[0][:5]}")