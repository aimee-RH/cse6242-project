from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from graph.graph import graph_app
from prompts.system_prompt import SYSTEM_PROMPT

app = Flask(__name__,
            static_folder='.',
            static_url_path='',
            template_folder='.')
CORS(app)

# Set API key for Qwen (should be set from environment variable)
os.environ.setdefault("OPENAI_API_KEY", "")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """LangGraph Agent chat endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '')
        chat_history = data.get('history', [])

        # Build initial message list
        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        # Add conversation history
        for msg in chat_history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                # Convert assistant messages to AIMessage
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=msg['content']))

        # Add current user message
        messages.append(HumanMessage(content=user_message))

        # Call LangGraph with recursion limit
        result = graph_app.invoke(
            {"messages": messages},
            {"recursion_limit": 50}  # 增加递归限制
        )

        # Extract final AI response
        final_message = result["messages"][-1]
        response_text = final_message.content

        return jsonify({
            'message': response_text,
            'success': True,
            'tool_calls': getattr(final_message, 'tool_calls', None)
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

if __name__ == '__main__':
    print("Starting LangGraph-based Academic Advisor Agent...")
    print("Open your browser and go to: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
