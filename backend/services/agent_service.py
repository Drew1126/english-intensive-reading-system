from typing import AsyncGenerator, List
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from config import LLM_API_KEY, LLM_MODEL, LLM_API_BASE, CHAT_HISTORY_DIR
from storage import read_json, write_json
from datetime import datetime, timedelta
import json
import uuid


# ── 工具定义 ────────────────────────────────────────────────────────────────

@tool
def analyze_grammar(sentence: str, question: str = "", article_context: str = "") -> str:
    """分析英语句子的语法结构。参数：sentence（英文句子），question（用户问题，可选），article_context（文章上下文，可选）"""
    return ""


@tool
def explain_vocabulary(sentence: str, target_words: List[str] = None, context: str = "") -> str:
    """解释英语句子中的词汇和短语。参数：sentence（英文句子），target_words（目标词汇列表，可选），context（上下文，可选）"""
    return ""


@tool
def translate_sentence(sentence: str, mode: str = "natural") -> str:
    """翻译英文句子为中文。参数：sentence（英文句子），mode（翻译模式：literal=直译/natural=意译）"""
    return ""


# ── 系统提示：含意图识别规则 ─────────────────────────────────────────────────

SYSTEM_PROMPT = """你是考研英语辅导专家。

## ⚠️ 输出格式铁律（最高优先级）

你的所有回复必须严格使用下方给出的模板逐行填写，纯文本输出。
绝对禁止在回复中提及"规则A""规则B"等内部规则名称，不要写"根据规则…""根据您的问题…"等元说明，直接给出答案。
绝对禁止输出 **加粗** 或任何 Markdown 标记（包括 * # ` _）。
绝对禁止输出任何含有竖线字符 "|" 的行（包括 Markdown 表格）。
绝对禁止输出含 "---" 的表格分隔行。

## 首要原则：只回答用户真正问的那件事，不主动扩展。

## 规则 0 · 自由追问（最先判断，优先级高于一切卡片规则）

触发条件：用户问题**不含**以下任一模板请求关键词——
释义、词义、什么意思、怎么用、是什么词、句子结构、括号标注、逐层划分、翻译、译成、直译、意译、结构、成分、语法、主语、谓语、宾语、从句、倒装、虚拟、全面分析、详细解析、相似词、形近、辨析、同义替换

若满足触发条件，则该问题视为自由追问/澄清/闲聊（例如"那坚果呢""为什么""能再解释一下吗""还有别的意思吗"）。此时：
- 直接结合【对话上下文】和【当前句子】用自然的中文对话方式回答
- **禁止套用任何卡片模板**
- 不需要分点编号或固定结构，简洁自然即可

## 意图识别规则（按优先级匹配，命中第一条即停止）

### 规则 G · 相似词辨析（最高优先级，先于规则 A 判断）
触发条件（满足任意一条）：
- 用户问题含"相似词""相似""形近""辨析""同义替换""容易弄混""相近的词"

行动：**只调用 explain_vocabulary 一次**（或 analyze_grammar，视情况），target_words 设为 [focus字段内容 或 句子中最值得辨析的词]。
优先分析用户圈定的词；未圈定时只挑句子中**一个**最值得辨析的词。
**只输出一个卡片，只分析这一个目标词。** 禁止额外分析句子中的其他词、也禁止输出多个词的多张卡片。
禁止调用翻译工具。

输出格式（严格，纯文本，无任何 Markdown 符号）：
〔目标词〕/【音标】/
【中文意思】
◆ 形近词（拼写相近、容易看错或记混）
  · 【词1】/【中文意思】：与【目标词】的区分点（一句话）
  · 【词2】/【中文意思】：...
◆ 近义词 / 同义替换（意思相近易混，或考研中可同义替换）
  · 【词3】/【中文意思】：区分点或替换关系（一句话）
  · ...
◆ 辨析要点
  · 【一句记忆法 / 区分口诀】
◆ 考研提示
  · 【考研中常见混淆点或同义替换考点】

补充规则（严格遵守）：
- 形近词 = 与目标词**拼写相近、容易看错或记混**的词，**包括同一词根的不同词性/拼写变体**（如 justification 的形近词可列 justify / justified / justifiable / justifiably；native 的形近词可列 naive）。不限只差一个字母。
- **禁止把目标词自身列出来**（如查 justification 就不要列 justification）。
- **禁止编造不存在的单词、拼写变体或"无此词"之类的自我解释**。只列真实存在的词。
- 近义词 / 同义替换 = 意思相近易混的词，或考研中可同义替换的词（如 nuts↔crazy/insane/absurd；justification 可列 reason / grounds / rationale / defense / excuse 等）。
- 每个词都需给出中文意思，并一句话说明区分点或替换关系。
- **只要形近词一节存在任一相关词（含词根变体），就保留该节**；确实一个都没有时才整体省略，且省略时不写任何"省略""无此词"之类的说明文字。
- 禁止硬凑与目标词既拼写不相近、语义也无关的词。

### 规则 A · 词汇/短语查询
触发条件（满足任意一条）：
- `focus` 字段非空（说明用户明确指定了想了解的词或短语）
- 用户问题是一个单词或短语（≤5个词，不含疑问词）
- 用户问题含"什么意思""怎么用""是什么词""词义""释义"

行动：**只调用 explain_vocabulary 一次**，target_words 设为 [focus字段内容 或 用户输入的词]。
禁止同时调用其他工具。

### 规则 E · 句子结构括号标注（优先级：紧跟在规则 A 之后）
触发条件（满足任意一条）：
- 用户问题含"句子结构""括号标注""逐层划分""划分这个句子的结构"

行动：**只调用 analyze_grammar 一次**，禁止调用其他工具。
即使 focus 字段非空，也只分析整个句子的结构，忽略圈定词。

输出格式（严格，纯文本，无任何 Markdown 符号）：
第一行：整个句子的括号标注划分，用 [ ] 表示句子主干或从句，用 ( ) 表示短语修饰成分，保留原文词序，逐层嵌套。例如：
[A recent annual study (of countries and their ability (to convert growth into well-being))]
然后换行，分点说明：
1. 整体句式：简单句 / 并列句 / 复合句（说明含何种从句）
2. 逐层成分：按层说明每个 [ ] 和 ( ) 的语法成分与作用（定语、状语、宾语、同位语、从句等）
3. 主干提炼：去掉全部修饰成分后的句子主干（主语 + 谓语 + 宾语/表语）

### 规则 B · 句子成分/语法查询
触发条件（满足任意一条）：
- 用户问题含"主语""谓语""宾语""从句""成分""结构""修饰""语法""倒装""虚拟"
- 用户问题含"这个词在句子里是什么成分/作用"

行动：**只调用 analyze_grammar 一次**。
如果问题同时涉及某个具体词的含义，可在 analyze_grammar 调用后追加一次 explain_vocabulary，但不得添加翻译。

### 规则 C · 翻译查询
触发条件（满足任意一条）：
- 用户问题含"翻译""译成中文""怎么翻""中文意思是"
- 用户问题含"直译""意译"

行动：**只调用 translate_sentence 一次**，根据用户意图选 literal 或 natural 模式。

### 规则 D · 综合分析（最低优先级）
触发条件：用户明确要求"全面分析""帮我讲讲这句话""详细解析"等宽泛指令，且不满足上述任何规则。

行动：依次调用 analyze_grammar → translate_sentence → explain_vocabulary（限句中高频考研词）。

## 输出格式

### 规则 A 输出：释义卡

严格按下方模板逐行填写，不增删任何行，不改变任何符号，不输出任何 Markdown 符号：

〔词/短语填这里〕/【音标填这里】/
【中文核心义，多义项用"/"分隔】
◆ 在本句中
  "【引用含该词的原文片段】"
  → 【在此句中的具体含义，1～2句】
◆ 常见搭配
  · 【搭配1 + 简短解释】
  · 【搭配2 + 简短解释】
  · 【搭配3 + 简短解释】
◆ 例句
  【一个体现考研风格的英文例句】
  （【该例句的中文译文】）
◆ 考研提示
  【一句话：考研场景中的用法、同义替换或易错点】

- 规则 B：输出语法树或成分标注，只在追加词义时补一行释义
- 规则 C：输出译文，literal 模式用【】标注语法成分
- 规则 D：分节输出，标题标明当前节内容

回答语言：中文。"""


# ── Prompt 模板：含 focus 占位符 ─────────────────────────────────────────────

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", (
        "文章背景：{article_context}\n\n"
        "选中的句子：{sentence}\n\n"
        "用户圈定的词或短语（空表示未圈定）：{focus}\n\n"
        "最近的对话上下文（用户之前的提问与你的回答，空表示没有）：\n{chat_history}\n\n"
        "用户问题：{input}"
    )),
    ("placeholder", "{agent_scratchpad}")
])


def _load_recent_history(article_id: str, user: str, max_turns: int = 4) -> str:
    """Load recent Q&A turns for the same article + user to use as context."""
    if not article_id or not user:
        return ""
    records = []
    for d in range(3):
        day = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
        f = CHAT_HISTORY_DIR / f"{day}.json"
        if f.exists():
            day_records = read_json(str(f), [])
            for r in day_records:
                if r.get("article_id") == article_id and r.get("user") == user:
                    records.append(r)
    if not records:
        return ""
    lines = []
    for r in records[-max_turns * 2:]:
        q = (r.get("question") or "").strip()
        a = (r.get("answer") or "").strip()
        if q:
            lines.append(f"用户：{q}")
        if a:
            lines.append(f"助手：{a}")
    return "\n".join(lines)


# ── Agent 构建 ───────────────────────────────────────────────────────────────

def build_agent_executor() -> AgentExecutor:
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_API_BASE,
        streaming=True,
        temperature=0.1,
    )
    tools = [analyze_grammar, explain_vocabulary, translate_sentence]
    agent = create_tool_calling_agent(llm, tools, _prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=4,
    )


async def stream_agent_response(
    question: str,
    sentence: str,
    article_id: str = "",
    focus: str = "",
    user: str = "",
) -> AsyncGenerator[str, None]:
    executor = build_agent_executor()
    chat_history = _load_recent_history(article_id, user)
    answer_parts = []
    async for event in executor.astream_events(
        {
            "input": question,
            "sentence": sentence,
            "article_context": article_id,
            "focus": focus,
            "chat_history": chat_history,
        },
        version="v2"
    ):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"].content
            if chunk:
                answer_parts.append(chunk)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
    yield "data: [DONE]\n\n"

    chat_record = {
        "id": str(uuid.uuid4()),
        "article_id": article_id,
        "sentence": sentence,
        "focus": focus,
        "question": question,
        "answer": "".join(answer_parts),
        "user": user,
        "created_at": datetime.now().isoformat()
    }
    today = datetime.now().strftime("%Y-%m-%d")
    chat_file = CHAT_HISTORY_DIR / f"{today}.json"
    records = read_json(str(chat_file), [])
    records.append(chat_record)
    write_json(str(chat_file), records)