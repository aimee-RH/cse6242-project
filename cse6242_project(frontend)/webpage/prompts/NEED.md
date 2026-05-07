# Scholar Compass 系统：从固定Pipeline到图原生RAG+Agent 完整升级方案
先给核心结论：你的系统已经具备**图数据库底座、基础RAG检索链路、学术场景Schema、可视化能力**四大核心地基，升级的核心不是推翻重写，而是把「固定写死的检索逻辑」升级为**Agent可自主调用的动态图检索能力**，把「单轮问答Pipeline」升级为「规划-检索-校验-生成-反思」的Agent闭环，充分释放Neo4j图数据库的多跳推理、关联分析优势，彻底解决现有系统的检索固化、复杂任务无法处理、多轮对话能力缺失的核心瓶颈。

## 一、现有系统核心瓶颈诊断（精准对应你的代码与论文）
先明确你当前系统的定位：**基于固定Cypher查询的单轮基础RAG系统**，而非真正的图原生RAG，更无Agent能力，核心短板如下：
| 模块 | 现有系统瓶颈 | 升级核心目标 |
|------|--------------|--------------|
| 检索引擎 | 所有Cypher查询硬编码写死，仅能返回预设的4类信息（合作者、论文、主题、基础信息），用户问题超出预设范围就无法召回数据，检索能力上限极低 | 实现动态Text2Cypher，让Agent可根据用户问题自主生成查询语句，充分释放图数据库的多跳、子图、路径检索能力 |
| RAG链路 | 仅实现「检索-增强-生成」线性流程，无事实校验、错误重试、上下文动态筛选，幻觉抑制仅靠Prompt约束，复杂场景极易失效 | 构建图增强RAG闭环，新增Query解析、检索结果重排序、事实一致性校验、错误重试机制，从根源抑制幻觉 |
| 核心能力 | 仅支持单轮问答，无任务拆解、多工具调用、多轮对话、记忆管理能力，无法处理复杂选导需求（如学者对比、条件筛选、报告生成） | 构建以图检索为核心的Agent框架，实现任务自主规划、多工具协同、多轮对话、长期记忆管理 |
| 图数据库价值 | 仅用Neo4j做了基础的单跳关联查询，和MySQL关系型查询无本质区别，完全未发挥图的多跳推理、关联分析、社区发现核心优势 | 把Neo4j作为系统唯一主检索库，所有知识调用、推理、记忆全基于图结构展开，实现「先图推理、后检索生成」 |
| 交互体验 | 无会话记忆，无法处理指代消解（如用户问“他的Top合作者是谁”，系统无法识别“他”的指代），每次都需重新输入学者名 | 用图数据库存储会话记忆与用户画像，实现自然多轮对话，支持指代消解、上下文关联 |

## 二、升级后的目标架构（贴合你的学术选导场景）
核心设计原则：**以Neo4j图数据库为唯一主检索库，Agent为任务执行核心，图增强RAG为知识底座**，完全适配「学生选导」全流程需求，架构分层完全兼容你现有代码，可渐进式升级：

```
┌─ 应用层 ──────────────────────────────────┐
│ 原有可视化界面 + 多轮对话窗口 + Agent任务面板 + 报告生成模块 │
├─ Agent核心层 ─────────────────────────────────┐
│ 规划Agent → 图检索Agent → 校验Agent → 报告生成Agent │
│ （任务拆解/工具调用/记忆管理/反思纠错/多轮协同）      │
├─ 图增强RAG层 ─────────────────────────────────┐
│ Query解析器 → Text2Cypher模块 → 上下文融合器 → 事实校验器 │
├─ 检索引擎层 ─────────────────────────────────┐
│ 图检索核心（多跳/路径/子图/对比）+ 向量辅助检索 + 重排序模块 │
├─ 数据核心层 ─────────────────────────────────┐
│ Neo4j图数据库（学术知识图谱 + 会话记忆图谱 + 向量索引） │
└─────────────────────────────────────────────┘
```

## 三、分阶段落地升级方案（可直接执行，最小改动兼容现有代码）
### 第一阶段：MVP快速升级（1-2周可落地，核心能力闭环）
**核心目标**：基于现有代码最小改动，实现Agent框架+动态图RAG，解决现有系统的核心瓶颈，支持复杂问题动态检索、多轮对话、基础工具调用。

#### 动作1：重构检索核心，实现动态Text2Cypher（替代硬编码Cypher）
这是升级的最核心一步，把你写死的4条Cypher查询，升级为Agent可自主调用的、能根据用户问题动态生成Cypher的通用检索能力。
- 核心优化点：
  1.  给LLM注入你的完整图Schema，搭配学术场景Few-shot示例，让模型精准生成Cypher；
  2.  新增Cypher执行报错重试机制，自动修正语法错误、逻辑错误；
  3.  兼容你现有的作者名消歧逻辑（PageRank排序），解决同名问题。

- 可直接复用的代码改造（基于你的rag.py新增）：
```python
# --- 新增：Text2Cypher核心模块 ---
def _get_graph_schema() -> str:
    """获取Neo4j图Schema，注入LLM用于生成Cypher"""
    schema_query = """
    CALL db.schema.visualization()
    """
    schema_data = run_cypher_query(schema_query)
    # 简化Schema描述，适配Prompt注入
    schema_desc = """
    【图数据库Schema说明】
    节点标签(Node Labels)及核心属性：
    1. Author: 学者节点，属性包括id(唯一标识)、display_name(姓名)
    2. Paper: 论文节点，属性包括id、title(标题)、publication_year(发表年份)、cited_by_count(被引量)
    3. Subfield: 研究子领域节点，属性包括id、display_name(子领域名称)
    4. Source: 发表期刊/会议节点，属性包括id、display_name(名称)
    
    关系类型(Relationships)：
    - (:Author)-[:AUTHORED]->(:Paper): 学者发表了论文
    - (:Paper)-[:IN_SUBFIELD]->(:Subfield): 论文属于某个研究子领域
    - (:Paper)-[:PUBLISHED_IN]->(:Source): 论文发表在某个期刊/会议
    
    【查询规则】
    1.  严格使用上述节点和关系，禁止编造不存在的标签/关系/属性
    2.  学者姓名模糊匹配使用：toLower(a.display_name) CONTAINS toLower($name)
    3.  同名学者优先选择论文数量多的，按count(p) DESC排序
    4.  所有查询必须限制返回条数，避免数据量过大，最多返回20条
    """
    return schema_desc

def _generate_cypher_from_query(user_query: str, scholar_name: str = None) -> str:
    """根据用户问题动态生成Cypher语句"""
    schema = _get_graph_schema()
    system_prompt = f"""
    你是专业的Neo4j Cypher生成专家，严格遵循以下规则生成Cypher语句：
    1.  仅基于下方提供的图Schema生成，禁止编造任何不存在的节点、关系、属性
    2.  生成的Cypher必须可直接执行，无语法错误，适配Neo4j 5.x版本
    3.  若用户问题涉及特定学者，必须先通过display_name匹配Author节点，优先匹配论文数量最多的学者
    4.  禁止生成全表扫描的查询，所有查询必须带过滤条件，结果最多返回20条
    5.  仅输出Cypher语句本身，不要任何解释、注释、markdown格式
    
    【图Schema】
    {schema}
    
    【示例】
    用户问题：Yao Xie的Top3高被引论文是什么？
    输出：
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
    RETURN p.title as title, p.cited_by_count as citations
    ORDER BY p.cited_by_count DESC
    LIMIT 3
    """
    # 拼接用户问题
    full_query = user_query
    if scholar_name:
        full_query = f"学者{scholar_name}：{user_query}"
    
    # 调用LLM生成Cypher
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_query}
        ],
        temperature=0, # 温度设为0，保证生成确定性
    )
    cypher = completion.choices[0].message.content.strip()
    print(f"[Backend] 生成Cypher: {cypher}")
    return cypher

def dynamic_graph_retrieval(user_query: str, scholar_name: str = None, max_retry: int = 3) -> list:
    """动态图检索核心函数：生成Cypher→执行→报错重试"""
    retry_count = 0
    while retry_count < max_retry:
        try:
            # 生成Cypher
            cypher = _generate_cypher_from_query(user_query, scholar_name)
            # 执行查询
            result = run_cypher_query(cypher)
            print(f"[Backend] 动态检索成功，返回{len(result)}条结果")
            return result
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            print(f"[Backend] Cypher执行失败，重试{retry_count}/{max_retry}，错误：{error_msg}")
            # 把报错信息返回给LLM，重新生成Cypher
            if retry_count < max_retry:
                user_query = f"{user_query}\n之前生成的Cypher执行报错：{error_msg}，请修正后重新生成正确的Cypher语句"
    return []
```

#### 动作2：基于LangChain封装Agent框架，把现有能力标准化为工具
把你现有的可视化数据检索、新增的动态图检索、RAG问答能力，封装成Agent可自主调用的标准化工具，实现任务自主规划执行。
- 核心工具集设计（完全贴合你的业务场景）：
  | 工具名称 | 核心功能 | Agent调用场景 |
  |----------|----------|--------------|
  | dynamic_graph_retrieval_tool | 动态图检索，根据问题生成Cypher并返回结果 | 所有需要查询学术数据的场景，核心工具 |
  | scholar_visual_data_tool | 获取学者的合作网络、主题演变可视化数据 | 用户需要查看图表、分析合作/主题趋势时调用 |
  | scholar_comparison_tool | 对比两位学者的研究方向、被引量、合作网络 | 用户需要对比多位导师时调用 |
  | fact_check_tool | 校验生成内容与图数据库事实的一致性 | 答案生成后做幻觉校验 |

- 基于你的现有代码，快速实现Agent核心逻辑（无需重构原有接口，兼容现有前端）：
```python
# 安装依赖：pip install langchain langchain-openai
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# 初始化LLM
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.3,
    api_key="你的API Key",
    base_url="https://api2.aigcbest.top/v1",
)

# 封装工具1：动态图检索工具
def dynamic_graph_retrieval_wrapper(query: str) -> str:
    """工具包装：动态图检索，输入用户问题，返回检索到的学术事实"""
    # 提取学者姓名（简单处理，可优化为NER提取）
    scholar_name = None
    if "学者" in query or "教授" in query:
        # 简单提取，可替换为专业NER模型
        import re
        name_match = re.search(r"(?:学者|教授)([\u4e00-\u9fa5A-Za-z\s]+)", query)
        if name_match:
            scholar_name = name_match.group(1).strip()
    result = dynamic_graph_retrieval(query, scholar_name)
    if not result:
        return "未在数据库中检索到相关信息，请调整问题后重试。"
    # 把检索结果转为自然语言，适配LLM理解
    result_str = "【检索到的事实信息】\n"
    for i, record in enumerate(result, 1):
        result_str += f"{i}. {json.dumps(record, ensure_ascii=False)}\n"
    return result_str

# 封装工具2：学者可视化数据工具
def scholar_visual_data_wrapper(scholar_name: str) -> str:
    """工具包装：获取学者的可视化数据，输入学者姓名，返回合作网络、主题演变数据"""
    scholar_data = _retrieve_scholar_data(scholar_name)
    if not scholar_data:
        return f"未找到学者{scholar_name}的相关数据。"
    visual_data = scholar_data.get("visual_data", {})
    context = scholar_data.get("retrieval_context", {})
    return f"""
    【学者{context.get('name')}可视化数据】
    1. 基础信息：总论文数{context.get('pagerank')}篇
    2. 核心合作者：{', '.join(context.get('key_collaborators', []))}
    3. 合作网络节点数：{len(visual_data.get('collaboration_network', {}).get('nodes', []))}
    4. 主题演变数据：共{len(visual_data.get('topic_evolution', []))}条年度主题记录
    """

# 定义工具列表
tools = [
    Tool(
        name="dynamic_graph_retrieval",
        func=dynamic_graph_retrieval_wrapper,
        description="""
        核心工具，用于从学术知识图谱中检索所有与学者、论文、研究主题相关的事实信息。
        输入用户的完整问题，返回精准的检索结果。
        所有需要查询学术数据的问题，必须优先调用此工具。
        """
    ),
    Tool(
        name="scholar_visual_data",
        func=scholar_visual_data_wrapper,
        description="""
        用于获取指定学者的合作网络、主题演变、论文统计等可视化相关数据。
        输入学者姓名，返回对应的可视化数据摘要。
        当用户需要查看学者的图表、分析研究趋势、合作情况时，调用此工具。
        """
    )
]

# 定义Agent Prompt（适配你的Scholar Compass场景）
agent_prompt = PromptTemplate.from_template("""
你是Scholar Compass，专为学生选导设计的AI助手，核心能力是基于学术知识图谱提供精准、 factual 的导师信息查询与分析服务。

你必须严格遵循以下规则：
1.  所有回答必须基于工具检索到的事实信息，禁止编造任何数据库中不存在的内容；
2.  若检索结果中没有相关信息，必须明确告知用户，禁止补充外部知识；
3.  优先使用dynamic_graph_retrieval工具获取信息，仅当用户需要可视化数据时调用scholar_visual_data工具；
4.  回答要简洁、专业、贴合学生选导的需求，避免无关内容；
5.  严格按照ReAct框架执行：Thought → Action → Action Input → Observation → 重复直到获得足够信息 → Final Answer

【工具列表】
{tools}

【工具名称】
{tool_names}

【用户输入】
{input}

【Agent执行日志】
{agent_scratchpad}
""")

# 初始化Agent
agent = create_react_agent(llm, tools, agent_prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10, # 限制最大迭代次数，避免死循环
)

# --- 重构你的/qanda接口，替换为Agent驱动 ---
@app.route('/api/agent_chat', methods=['POST'])
def agent_chat():
    """Agent多轮对话接口，替代原有单轮/qanda接口，兼容前端"""
    print("[Backend] /api/agent_chat 已被调用")
    try:
        data = request.json
        scholar_name = data.get('scholar_name', None)
        user_question = data.get('question')
        session_id = data.get('session_id', 'default') # 会话ID，用于多轮记忆
        if not user_question:
            return jsonify({'error': 'question字段必填'}), 400
        
        # 拼接学者名，优化检索
        full_input = user_question
        if scholar_name:
            full_input = f"针对学者{scholar_name}，{user_question}"
        
        # 调用Agent执行
        result = agent_executor.invoke({"input": full_input})
        answer = result.get('output', '抱歉，我无法处理这个问题，请调整后重试。')
        
        return jsonify({
            'success': True,
            'llm_answer': answer,
            'session_id': session_id
        })
    except Exception as e:
        print(f"Error in /agent_chat: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500
```

#### 动作3：新增会话记忆管理，支持多轮对话与指代消解
用Neo4j图数据库存储会话记忆，彻底解决现有系统无记忆、无法处理指代的问题，同时把用户偏好、历史查询存入图谱，实现个性化服务。
- 核心实现：新增会话记忆图谱Schema，和原有学术图谱打通
  ```
  节点标签：
  - Session: 会话节点，属性session_id(唯一)、user_id、create_time、update_time
  - User: 用户节点，属性user_id、name、preference(偏好)
  - Message: 消息节点，属性id、content、role(user/assistant)、create_time
  关系：
  - (:User)-[:HAS_SESSION]->(:Session): 用户拥有会话
  - (:Session)-[:HAS_MESSAGE]->(:Message): 会话包含消息
  - (:Message)-[:REFERENCES]->(:Author): 消息引用了某个学者节点
  ```
- 代码改造：在Agent执行前，先获取历史会话上下文，注入Prompt，实现指代消解

#### 动作4：新增基础事实校验模块，抑制幻觉
在Agent生成最终答案前，自动校验答案中的实体、关系、数据是否和Neo4j中的信息一致，从根源抑制幻觉，对应你论文中提到的「Visual-Grounded Truth Verification」能力。
```python
def fact_check(answer: str, scholar_name: str = None) -> tuple[bool, str]:
    """事实校验：校验答案是否与图数据库中的事实一致"""
    check_prompt = f"""
    你是专业的事实校验专家，需要校验以下回答是否与学术知识图谱中的事实一致。
    步骤：
    1.  提取回答中所有的事实性信息（学者姓名、论文数量、被引量、合作者、研究主题、发表期刊等）
    2.  调用dynamic_graph_retrieval工具，校验每一条事实是否正确
    3.  输出校验结果：是否通过，以及错误的事实信息
    
    待校验回答：{answer}
    关联学者：{scholar_name if scholar_name else '无'}
    """
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": check_prompt},
            {"role": "user", "content": "请执行事实校验，输出结果"}
        ],
        temperature=0,
    )
    check_result = completion.choices[0].message.content.strip()
    # 简单判断是否通过，可优化为结构化输出
    is_pass = "未发现错误" in check_result or "全部正确" in check_result
    return is_pass, check_result
```

### 第二阶段：进阶深度升级（3-4周，完善全链路能力）
**核心目标**：充分释放图数据库的能力，完善多Agent协同、复杂任务处理、多跳推理能力，覆盖学生选导全流程需求。
1.  **扩展图检索核心能力**
    - 新增多跳推理检索：比如“这位学者的学生有哪些，现在都在哪些机构任职？”（3跳查询：Author→Paper→Co-author→Institution）
    - 新增学者对比检索：支持两位及以上学者的研究方向、被引量、活跃度、合作网络的横向对比
    - 新增条件筛选检索：比如“帮我找近3年在计算机网络领域发表过Top会议论文、被引量Top20的华人学者”
    - 新增社区发现与PageRank深度应用：基于合作网络做社区聚类，识别学者的核心团队、学术圈子

2.  **扩展Agent工具集，实现全流程选导服务**
    - 新增导师匹配度打分工具：根据学生的研究方向、背景，匹配最适合的导师，输出匹配度评分与理由
    - 新增学术趋势分析工具：分析某个研究领域的发展趋势、核心学者、热门主题
    - 新增报告生成工具：自动生成学者分析报告、导师对比报告、选导建议报告，支持导出PDF
    - 新增文献解析工具：解析导师的代表性论文，提炼核心研究内容、创新点，帮助学生快速了解导师的研究方向

3.  **优化RAG全链路，提升准确率与性能**
    - 新增检索结果重排序：用BGE-reranker模型对动态检索的结果做相关性排序，过滤噪声，提升上下文质量
    - 优化Text2Cypher模块：补充100+学术场景的Few-shot示例，针对高频错误做专项优化，提升Cypher生成准确率到95%以上
    - 新增缓存机制：对高频查询的Cypher结果、学者数据做缓存，大幅提升响应速度，解决你论文中提到的后端接口延迟瓶颈
    - 优化上下文融合：动态筛选检索结果，控制上下文长度，避免溢出，提升LLM的回答质量

4.  **构建多Agent协同架构**
    把单一Agent拆分为多Agent分工协同，提升复杂任务处理能力，适配你的业务场景：
    - 规划Agent：负责拆解用户的复杂需求，制定执行计划，分配子任务给其他Agent
    - 图检索Agent：专职负责图查询、数据召回，给其他Agent提供精准的知识支撑
    - 校验Agent：专职负责事实校验、幻觉检测，确保所有输出内容的准确性
    - 报告生成Agent：负责把检索结果整合成结构化的分析报告，适配学生选导需求

### 第三阶段：生产级优化（长期迭代）
**核心目标**：提升系统的稳定性、性能、扩展性，适配大规模学术数据与用户量。
1.  **Neo4j数据库优化**：优化索引设计，新增向量索引、全文索引，实现集群部署，支持亿级节点的高效检索；优化作者名消歧算法，提升同名学者的匹配准确率。
2.  **模型微调**：用学术场景的Query-Cypher数据集微调Text2Cypher模型，用选导场景的对话数据微调RAG模型，提升垂直场景的适配性。
3.  **用户画像与个性化推荐**：构建用户画像图谱，记录用户的研究方向、偏好、历史查询，实现个性化的导师推荐，解决你论文中提到的「开放搜索能力不足」的问题。
4.  **监控与效果评估**：搭建全链路监控体系，监控Agent调用、检索准确率、接口性能、幻觉率；构建自动化评估数据集，持续迭代优化系统效果。

## 四、升级后核心能力提升（和现有系统的本质区别）
| 能力维度 | 现有系统 | 升级后的RAG+Agent系统 |
|----------|----------|------------------------|
| 检索能力 | 固定硬编码查询，仅支持4类预设信息 | 动态图检索，支持任意学术相关问题的精准查询，充分发挥图数据库多跳推理能力 |
| 任务处理 | 仅支持单轮问答，无法处理复杂需求 | 支持复杂任务自主规划执行，比如学者对比、条件筛选、报告生成、导师匹配 |
| 多轮对话 | 无记忆能力，无法处理指代消解 | 基于图数据库的会话记忆，支持自然多轮对话，精准识别上下文指代 |
| 幻觉抑制 | 仅靠Prompt约束，无实际校验机制 | 检索-生成-校验闭环，每一条事实都和图数据库交叉验证，幻觉率降至5%以下 |
| 扩展性 | 新增需求必须修改代码，硬编码Cypher | 新增能力仅需封装工具，Agent可自主调用，扩展性极强 |
| 业务价值 | 仅能展示学者信息，辅助学生选导 | 覆盖选导全流程，从导师筛选、对比、分析到报告生成，全链路AI辅助 |

## 五、核心避坑指南（贴合你的学术场景）
1.  **Text2Cypher生成准确率是生命线**：学术场景的查询逻辑复杂，必须严格限制Schema注入的范围，搭配大量Few-shot示例，温度设为0，同时做好报错重试机制，避免生成无效Cypher。
2.  **控制图检索的跳数**：多跳查询能力很强，但超过3跳的查询极易引入噪声，同时导致查询性能急剧下降，MVP阶段优先控制在3跳以内。
3.  **禁止让LLM直接生成结论，必须先检索后生成**：严格遵循ReAct框架，所有事实性内容必须先调用工具检索，再生成回答，从根源避免幻觉。
4.  **做好同名学者消歧**：学术场景同名问题极常见，必须在检索环节优先处理，通过论文数量、机构、研究领域多维度匹配，避免检索到错误的学者数据。
5.  **避免上下文溢出**：动态图检索可能返回大量数据，必须做好结果筛选与重排序，控制注入LLM的上下文长度，避免关键信息被淹没。

需要我基于你的代码，给你一套可直接替换运行的完整rag.py升级文件，包含Agent核心、Text2Cypher、多轮记忆和事实校验模块吗？