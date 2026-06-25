import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatZhipuAI
from langgraph.prebuilt import create_react_agent

from tools import get_today_schedule, create_tomorrow_template, assign_flexible_times

load_dotenv()

SYSTEM_PROMPT = """你是一个早晨日程规划助手。每天早上：

1. 调用工具读取今天的日程表（分"固定日程"和"灵活待办"两部分）
2. "固定日程"是不能改变的时间块，必须严格保留
3. 分析固定日程之间的空隙时间
4. 调用 assign_flexible_times，把灵活待办塞进固定日程的空隙里，按优先级和预计耗时分配时间段，输出 JSON 数组，格式为 [{"index": 0, "start": "HH:MM", "end": "HH:MM"}, ...]，index 从0开始。已有时间前缀的任务跳过
5. 检查是否有时间冲突或安排过满，如有要提醒
6. 如果今天没有日程文件，告知用户并引导创建
7. 调用工具生成明天的日程模板文件
8. 给用户的回复是纯文本，会直接发送到邮件和手机消息，不要用任何Markdown符号，用自然的换行分段
9. 语气直接友好，不要说教，控制在250字以内"""

llm = ChatZhipuAI(
    model="glm-4-flash",
    api_key=os.environ.get("ZHIPUAI_API_KEY", ""),
)

agent = create_react_agent(
    model=llm,
    tools=[get_today_schedule, create_tomorrow_template, assign_flexible_times],
    prompt=SYSTEM_PROMPT,
)
