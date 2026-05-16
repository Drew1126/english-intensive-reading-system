from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from config import LLM_API_KEY, LLM_MODEL, LLM_API_BASE
from typing import List


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


SYSTEM_PROMPT = """你是考研英语辅导专家，擅长语法分析、词汇讲解和翻译。

你有以下三个工具：
1. analyze_grammar - 分析句子语法结构：找出主干（主谓宾）、从句类型（定语/状语/名词从句）、特殊结构（倒装/虚拟语气/强调句/分词结构），并指出考研考点
2. explain_vocabulary - 解释词汇：给出音标、中文释义、用法搭配、考研频率、例句
3. translate_sentence - 翻译句子：literal模式按语序直译并用【】标注语法成分，natural模式输出地道中文

根据用户的问题，选择合适的工具来回答。回答用中文，适合中国考研学生理解。

如果用户问语法结构，使用 analyze_grammar。
如果用户问词汇意思，使用 explain_vocabulary。
如果用户要求翻译，使用 translate_sentence。
如果用户问题涉及多个方面，可以依次调用多个工具。"""

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "文章背景：{article_context}\n\n选中的句子：{sentence}\n\n用户问题：{input}"),
    ("placeholder", "{agent_scratchpad}")
])


def build_agent_executor() -> AgentExecutor:
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_API_BASE,
        streaming=True,
        temperature=0.3,
    )
    tools = [analyze_grammar, explain_vocabulary, translate_sentence]
    agent = create_tool_calling_agent(llm, tools, _prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)
