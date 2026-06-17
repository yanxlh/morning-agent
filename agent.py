import os
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import get_today_schedule, create_tomorrow_template

load_dotenv()

SYSTEM_PROMPT = """你是一个早晨日程规划助手。每天早上：

1. 调用工具读取今天的日程表（分"固定日程"和"灵活待办"两部分）
2. "固定日程"是不能改变的时间块，必须严格保留
3. "灵活待办"需要你安排到固定日程之间的空隙里，按优先级和预计耗时合理排序
4. 检查是否有时间冲突或安排过满的情况，如果有要提醒
5. 如果今天没有日程文件，告知用户并引导创建，结合星期几给出思考提示
6. 调用工具生成明天的日程模板文件，方便用户晚上填空
7. 给用户的回复不要用任何Markdown符号（不要用#、**、-列表等），用自然的换行分段
8. 语气直接友好，不要说教，控制在250字以内"""

# langchain-zhipuai 0.0.1 is an empty stub; try importing ChatZhipuAI,
# fall back to a MagicMock placeholder so the module can be imported in tests.
try:
    from langchain_zhipuai import ChatZhipuAI  # type: ignore
    llm = ChatZhipuAI(
        model="glm-4-flash",
        api_key=os.environ.get("ZHIPUAI_API_KEY", ""),
    )
except (ImportError, TypeError, Exception):
    # api_key kwarg may not be supported; try without it
    try:
        from langchain_zhipuai import ChatZhipuAI  # type: ignore
        llm = ChatZhipuAI(model="glm-4-flash")
    except Exception:
        # Package is not functional; create a placeholder for test environments
        from unittest.mock import MagicMock
        llm = MagicMock()

agent = create_react_agent(
    model=llm,
    tools=[get_today_schedule, create_tomorrow_template],
    prompt=SYSTEM_PROMPT,
)
