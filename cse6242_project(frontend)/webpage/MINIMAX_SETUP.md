# ✅ MiniMax API 配置完成！

## 🎉 已完成配置

1. ✅ **创建了 MiniMax 配置**
   - `graph/minimax_nodes.py` - MiniMax API 配置文件

2. ✅ **切换到 MiniMax**
   - `graph/nodes.py` - 当前使用 MiniMax API

3. ✅ **保留了所有版本**
   - `graph/minimax_nodes.py` - MiniMax 版本（当前）
   - `graph/claude_nodes.py` - Claude 版本（备份）
   - `graph/qwen_nodes.py` - Qwen 版本（备份）

4. ✅ **更新了切换脚本**
   - `switch_api.sh` - 支持 minimax/claude/qwen 三种切换

---

## 🚀 立即使用 MiniMax API

### 步骤 1: 获取 MiniMax API Key

1. **访问 MiniMax 官网**：https://www.minimaxi.com/
2. **注册/登录账号**
3. **进入开发者中心**：https://www.minimaxi.com/user-center/basic-information/interface-key
4. **创建 API Key**
5. **复制你的 API Key**

### 步骤 2: 设置环境变量

```bash
export MINIMAX_API_KEY='your-minimax-api-key-here'
```

### 步骤 3: 启动应用

```bash
python app.py
```

### 步骤 4: 打开浏览器

```
http://localhost:5001
```

---

## 🔄 API 切换

### 切换到 MiniMax
```bash
./switch_api.sh minimax
export MINIMAX_API_KEY='your-key'
```

### 切换到 Claude
```bash
./switch_api.sh claude
export ANTHROPIC_API_KEY='sk-ant-your-key'
```

### 切换到 Qwen
```bash
./switch_api.sh qwen
export OPENAI_API_KEY='sk-qwen-your-key'
```

---

## 📊 三种 API 对比

| 特性 | MiniMax | Claude | Qwen |
|------|---------|--------|------|
| **服务地区** | 🇨🇳 国内 | 🇺🇸 国外 | 🇨🇳 国内 |
| **速度** | ⭐⭐⭐⭐⭐ 快 | ⭐⭐⭐ 中 | ⭐⭐⭐⭐⭐ 快 |
| **价格** | ⭐⭐⭐⭐ 便宜 | ⭐⭐ 较贵 | ⭐⭐⭐⭐ 便宜 |
| **中文支持** | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐⭐ 良好 | ⭐⭐⭐⭐⭐ 优秀 |
| **工具调用** | ⭐⭐⭐⭐ 支持 | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐⭐ 支持 |
| **上下文长度** | 32K | 200K | 32K |
| **模型** | abab6.5s-chat | Claude 3.5 Sonnet | qwen-plus |

---

## 🎯 MiniMax 模型选择

当前配置使用 **abab6.5s-chat**

### 可选模型：

```python
# 平衡性能和速度（推荐）
model="abab6.5s-chat"

# 更强的性能
model="abab6-chat"

# 更快响应
model="abab5.5-chat"

# 最快响应
model="abab5-chat"
```

### 如何切换模型？

编辑 `graph/minimax_nodes.py`，修改 `model` 参数：

```python
llm = ChatOpenAI(
    model="abab6-chat",  # 改成你想要的模型
    base_url="https://api.minimax.chat/v1",
    temperature=0,
    api_key=api_key
)
```

---

## 💡 MiniMax 优势

### ✅ 为什么选择 MiniMax？

1. **国内服务** - 响应速度快，延迟低
2. **价格实惠** - 相比 Claude 更便宜
3. **中文优化** - 对中文理解非常好
4. **工具调用** - 支持 Function Calling
5. **合规性** - 符合国内法规要求
6. **稳定性** - 服务稳定可靠

### 🎯 适用场景

- ✅ 中文学术导师推荐
- ✅ 快速响应需求
- ✅ 成本敏感项目
- ✅ 需要国内服务
- ✅ 中文对话为主

---

## 🧪 测试 MiniMax 配置

### 1. 验证 API Key
```bash
echo $MINIMAX_API_KEY
```
应该显示你的 MiniMax API key

### 2. 测试连接
```bash
python test_agent.py
```

预期输出：
```
✅ All critical tests passed!
```

### 3. 启动应用
```bash
python app.py
```

---

## 💬 测试对话

启动后，试试这些问题：

### 基础功能测试
```
"你好，请介绍一下你自己"
```

### 导师推荐
```
"推荐一些机器学习领域的导师"
"根据我的研究兴趣推荐导师：深度学习和计算机视觉"
```

### 学者搜索
```
"查找计算机视觉领域的高影响力学者"
```

### 研究趋势
```
"分析自然语言处理领域的研究趋势"
```

### 合作网络
```
"分析张教授的合作网络"
```

---

## 📝 MiniMax API 配置详情

### 当前配置
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="abab6.5s-chat",
    base_url="https://api.minimax.chat/v1",
    temperature=0,
    api_key=os.environ.get("MINIMAX_API_KEY")
)
```

### API 端点
- **Base URL**: `https://api.minimax.chat/v1`
- **兼容性**: 兼容 OpenAI API 格式

### 环境变量
```bash
export MINIMAX_API_KEY='your-api-key'
```

---

## 🔧 故障排查

### 问题 1: "API key not found"
**解决方案：**
```bash
# 检查环境变量
echo $MINIMAX_API_KEY

# 重新设置
export MINIMAX_API_KEY='your-key'
```

### 问题 2: "Connection timeout"
**解决方案：**
- 检查网络连接
- 确认 MiniMax 服务状态
- 尝试使用 VPN（如果有网络限制）

### 问题 3: "Model not found"
**解决方案：**
- 确认模型名称正确
- 检查 MiniMax 账号是否有该模型权限
- 尝试切换到其他模型（如 abab5.5-chat）

### 问题 4: "Rate limit exceeded"
**解决方案：**
- 等待一段时间后重试
- 检查账号配额
- 升级 MiniMax 账号等级

---

## 📚 参考资源

### MiniMax 官方文档
- **官网**: https://www.minimaxi.com/
- **API 文档**: https://www.minimaxi.com/document/guides/chat/start
- **价格**: https://www.minimaxi.com/document/price
- **开发者中心**: https://www.minimaxi.com/user-center/basic-information/interface-key

### 模型对比
- **abab6.5s-chat**: 最新模型，性能和速度平衡
- **abab6-chat**: 更强性能，稍慢
- **abab5.5-chat**: 较快响应，性能良好

---

## 🎊 开始使用

### 快速开始

```bash
# 1. 设置 API key
export MINIMAX_API_KEY='your-minimax-api-key'

# 2. 启动应用
python app.py

# 3. 打开浏览器
open http://localhost:5001
```

### 验证成功

当你看到以下输出时，说明配置成功：

```
Starting LangGraph-based Academic Advisor Agent...
Open your browser and go to: http://localhost:5001
 * Running on http://0.0.0.0:5001
```

---

## 🎉 总结

你现在拥有：

✅ **MiniMax API** - 当前使用（国内快速）
✅ **Claude API** - 备份选项（性能最强）
✅ **Qwen API** - 备份选项（阿里云服务）

**随时可以切换**，选择最适合你的 API！

**一切就绪，开始使用 MiniMax 驱动的学术助手吧！** 🚀
