import torch

print(f"PyTorch 版本: {torch.__version__}")
print(f"MPS 是否可用: {torch.backends.mps.is_available()}")
print(f"MPS 是否已构建: {torch.backends.mps.is_built()}")

if torch.backends.mps.is_available():
    # 跑个小测试
    x = torch.rand(3, 3, device="mps")
    y = x @ x.T
    print(f"✅ MPS 测试成功，结果 shape: {y.shape}")
else:
    print("❌ MPS 不可用，会 fallback 到 CPU")