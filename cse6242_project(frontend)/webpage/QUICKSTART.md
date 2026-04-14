# Quick Start Guide - LangGraph Academic Advisor Agent

## 🚀 5-Minute Setup

### Prerequisites
- Python 3.8+
- Neo4j database (Docker)
- Qwen API key (Alibaba Cloud)

---

## Step 1: Install Dependencies (1 min)

```bash
cd "cse6242_project(frontend)/webpage"
pip install -r requirements.txt
```

---

## Step 2: Configure API Key (30 sec)

```bash
export OPENAI_API_KEY='sk-your-qwen-api-key'
```

**Get your API key**: https://dashscope.aliyuncs.com/

---

## Step 3: Start Neo4j (1 min)

```bash
cd backend/academic_graph_project
docker-compose up -d
```

**Verify Neo4j is running**:
```bash
curl http://localhost:7474
```

---

## Step 4: Test the Setup (30 sec)

```bash
cd "cse6242_project(frontend)/webpage"
python test_agent.py
```

Expected output:
```
✅ All critical tests passed!
```

---

## Step 5: Run the Application (1 min)

```bash
python app.py
```

You should see:
```
Starting LangGraph-based Academic Advisor Agent...
Open your browser and go to: http://localhost:5001
 * Running on http://0.0.0.0:5001
```

---

## Step 6: Use the Agent!

Open your browser: **http://localhost:5001**

### Try These Queries:

1. **Find Scholars**
   ```
   "Find scholars in machine learning"
   ```

2. **Get Recommendations**
   ```
   "Recommend advisors for deep learning research"
   ```

3. **Analyze Author**
   ```
   "Tell me about https://openalex.org/A1234567890"
   ```

4. **Trending Topics**
   ```
   "What are trending topics in computer vision?"
   ```

5. **Collaboration Network**
   ```
   "Who are the main collaborators of Dr. Zhang?"
   ```

---

## 🎯 What's Happening Behind the Scenes?

```
Your Query
    ↓
[LLM Understanding]
    ↓
[Tool Selection] → One of 5 tools chosen
    ↓
[Neo4j Query] → Real academic data
    ↓
[Result Processing]
    ↓
[Natural Language Response]
```

---

## 🛠️ Troubleshooting

### Neo4j Connection Error
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Restart Neo4j
cd backend/academic_graph_project
docker-compose restart
```

### API Key Error
```bash
# Verify key is set
echo $OPENAI_API_KEY

# Set it again
export OPENAI_API_KEY='your-key'
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Port Already in Use
```bash
# Change port in app.py
app.run(debug=True, host='0.0.0.0', port=5002)
```

---

## 📚 Learn More

- **Full Documentation**: See `README_AGENT.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Test Your Setup**: Run `python test_agent.py`

---

## 🎓 Example Conversations

### Conversation 1: Finding Advisors
```
You: "I need a machine learning advisor"

Agent: "I'll help you find ML advisors.
       [Searching database...]

       Based on research impact and publications,
       I recommend:

       1. Prof. Wang (FWCI: 2.5, 52 papers)
          Specializes in: Deep Learning, Computer Vision

       2. Prof. Chen (FWCI: 2.3, 48 papers)
          Specializes in: NLP, Reinforcement Learning

       Would you like details about any of these?"
```

### Conversation 2: Research Analysis
```
You: "What's trending in NLP?"

Agent: "Analyzing recent NLP publications...
       [Querying Neo4j...]

       Top trending topics (2020-2024):

       1. Large Language Models (2,341 citations)
          - GPT architectures
          - Prompt engineering

       2. Transformers (1,987 citations)
          - Attention mechanisms
          - Multi-modal learning

       3. Efficient Training (1,654 citations)
          - LoRA and adapters
          - Quantization techniques

       Would you like me to recommend experts in any of these areas?"
```

---

## 💡 Tips

1. **Be Specific**: "Find scholars in deep learning" works better than "Find AI people"
2. **Follow-up**: Ask about specific authors from previous results
3. **Iterate**: Use multi-turn conversations to refine your search
4. **Check Metrics**: Pay attention to FWCI (impact score) and citations

---

## 🆘 Need Help?

- Check `README_AGENT.md` for detailed documentation
- Run `python test_agent.py` to diagnose issues
- Review logs in the terminal for error messages

---

**Ready to explore academic advisors and research trends? Start the app and begin your journey!** 🚀
