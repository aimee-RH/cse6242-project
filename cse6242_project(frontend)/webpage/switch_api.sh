#!/bin/bash

# API 切换脚本
# 用法: ./switch_api.sh [minimax|claude|qwen]

API_TYPE=${1:-minimax}

echo "======================================"
echo "   LangGraph Agent API 切换工具"
echo "======================================"
echo ""

if [ "$API_TYPE" = "minimax" ]; then
    echo "🔄 切换到 MiniMax API..."
    cp graph/nodes.py graph/nodes.py.bak 2>/dev/null
    cp graph/minimax_nodes.py graph/nodes.py
    echo "✅ 已切换到 MiniMax API"
    echo ""
    echo "📝 请设置环境变量："
    echo "   export MINIMAX_API_KEY='your-minimax-api-key'"
    echo ""
    echo "🌐 MiniMax 官网: https://www.minimaxi.com/"
    echo ""

elif [ "$API_TYPE" = "claude" ]; then
    echo "🔄 切换到 Claude API..."
    cp graph/nodes.py graph/nodes.py.bak 2>/dev/null
    cp graph/claude_nodes.py graph/nodes.py
    echo "✅ 已切换到 Claude API"
    echo ""
    echo "📝 请设置环境变量："
    echo "   export ANTHROPIC_API_KEY='sk-ant-your-key-here'"
    echo ""
    echo "🌐 Claude 官网: https://console.anthropic.com/"
    echo ""

elif [ "$API_TYPE" = "qwen" ]; then
    echo "🔄 切换到 Qwen API..."
    cp graph/nodes.py graph/nodes.py.bak 2>/dev/null
    cp graph/qwen_nodes.py graph/nodes.py
    echo "✅ 已切换到 Qwen API"
    echo ""
    echo "📝 请设置环境变量："
    echo "   export OPENAI_API_KEY='sk-qwen-your-key-here'"
    echo ""
    echo "🌐 Qwen 官网: https://dashscope.aliyuncs.com/"
    echo ""

else
    echo "❌ 未知的 API 类型: $API_TYPE"
    echo ""
    echo "用法: ./switch_api.sh [minimax|claude|qwen]"
    echo ""
    echo "支持的 API:"
    echo "  - minimax: MiniMax API（国内服务）"
    echo "  - claude:  Claude API（Anthropic）"
    echo "  - qwen:    Qwen API（阿里云）"
    echo ""
    exit 1
fi

echo "🚀 现在可以启动应用："
echo "   python app.py"
echo ""
echo "======================================"
