# 🔄 API 切换指南：Qwen vs Claude

## 📌 当前问题

你正在使用 **Claude 的 API key**，但代码配置的是 **Qwen（通义千问）API**。这两个是不同的服务！

---

## 🎯 解决方案（二选一）

### 方案 1：使用 Qwen API（推荐，已配置）

**优势：**
- ✅ 代码已配置完成
- ✅ 无需修改代码
- ✅ 阿里云服务，国内访问快
- ✅ 有免费额度

**步骤：**

1. **获取 Qwen API Key**：
   - 访问：https://dashscope.aliyuncs.com/
   - 登录/注册阿里云账号
   - 点击右上角 "API-KEY管理"
   - 创建新的 API-KEY
   - 复制密钥（格式：`sk-xxxxxxxxxxxxx`）

2. **设置环境变量**：
   ```bash
   export OPENAI_API_KEY='sk-qwen-你的密钥'
   ```

3. **重启应用**：
   ```bash
   python app.py
   ```

---

### 方案 2：使用 Claude API（需要修改代码）

**优势：**
- ✅ 你已经有 Claude API key
- ✅ Claude 能力强大

**劣势：**
- ❌ 需要安装额外依赖
- ❌ 需要修改代码
- ❌ 国外服务，可能较慢

**步骤：**

1. **安装 Claude 依赖**：
   ```bash
   pip install langchain-anthropic
   ```

2. **修改 graph/nodes.py**：

   将整个文件内容替换为：
   ```python
   from langchain_anthropic import ChatAnthropic
   from langgraph.prebuilt import ToolNode
   from graph.state import AgentState
   from tools import TOOLS
   import os

   # Initialize LLM (Claude)
   api_key = os.environ.get("ANTHROPIC_API_KEY", "")

   if not api_key:
       raise ValueError(
           "❌ Claude API密钥未设置！\n"
           "请设置: export ANTHROPIC_API_KEY='sk-ant-your-key'"
       )

   llm = ChatAnthropic(
       model="claude-3-5-sonnet-20241022",
       temperature=0,
       api_key=api_key
   )

   llm_with_tools = llm.bind_tools(TOOLS)
   tool_node = ToolNode(TOOLS)

   def call_model(state: AgentState) -> AgentState:
       messages = state["messages"]
       response = llm_with_tools.invoke(messages)
       return {"messages": [response]}
   ```

3. **设置环境变量**：
   ```bash
   export ANTHROPIC_API_KEY='sk-ant-your-claud-key'
   ```

4. **重启应用**：
   ```bash
   python app.py
   ```

---

## 🔍 如何确认你使用的是哪个 API？

### 检查你的 API key 格式：

**Qwen API Key**（阿里云）：
```
sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
- 格式：`sk-` 开头
- 获取地址：https://dashscope.aliyuncs.com/

**Claude API Key**（Anthropic）：
```
sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
```
- 格式：`sk-ant-` 开头
- 获取地址：https://console.anthropic.com/

---

## 💡 推荐选择

### 推荐使用 Qwen API，原因：

1. **快速配置**：无需改代码
2. **国内服务**：访问速度快
3. **成本较低**：有免费额度
4. **中文优化**：Qwen 对中文支持更好

### 使用 Claude API 的场景：

1. **已有 Claude key**：不想注册新账号
2. **更高性能**：Claude Opus 能力更强
3. **特殊需求**：需要 Claude 特定功能

---

## 🚀 快速开始（推荐方案）

```bash
# 1. 获取 Qwen API key 并设置
export OPENAI_API_KEY='sk-qwen-你的密钥'

# 2. 启动应用
python app.py

# 3. 打开浏览器
open http://localhost:5001
```

---

## ❓ 常见问题

### Q: 我能用 Claude key 吗？
A: 可以，但需要修改代码（见方案2）

### Q: 哪个 API 更便宜？
A: Qwen 通常更便宜，且有免费额度

### Q: 哪个效果更好？
A: Claude Opus > Claude Sonnet ≈ Qwen Plus
   但对于学术推荐，Qwen 足够了

### Q: 我两个都想试试？
A: 可以！修改代码后随时切换

---

**建议：先用 Qwen 测试功能，后续可切换到 Claude**
