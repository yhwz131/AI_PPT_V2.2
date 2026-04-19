# 1. 定义带速率限制的load_chat_model函数
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter
import os
from dotenv import load_dotenv
# 导入 PromptTemplate 类，用于构建可复用的提示词模板
from langchain_core.prompts import PromptTemplate

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

# 1 加载 .env 环境变量
load_dotenv(override=True)

'''
++++++++++++++++++++++++++++++++辅助函数++++++++++++++++++++++++++++++++++
'''
# 3. 配置速率限制器
rate_limiter = InMemoryRateLimiter(
    requests_per_second=5,       # 每秒最多5个请求
    check_every_n_seconds=1.0    # 每1秒检查一次是否超过速率限制
)

# 3. 对模型调用进行封装，后续直接调用传参数就行
def load_chat_model(
    model: str,
    provider: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    base_url: str | None = None,
):
    return init_chat_model(
        model=model,               # 模型名称
        model_provider=provider,   # 模型供应商
        temperature=temperature,   # 温度参数，用于控制模型的随机性，值越小则随机性越小
        max_tokens=max_tokens,     # 最大生成token数
        base_url=base_url,         # 专用于自定义 API Server 或代理
        rate_limiter=rate_limiter  # 自动限速
    )

'''
+++++++++++++++++++++++++++++++添加业务函数+++++++++++++++++++++++++++++++++
'''

# 1. 定义单页ppt的结构
class PptItem(BaseModel):
    """单个城市的天气信息"""
    page_num: int = Field(description="页数")
    title: str = Field(description="每页的ppt主题")
    content: str = Field(description="每页ppt的口播文案")

# 2. 定义列表的包换结构
class PptsInfoList(BaseModel):
    """天气信息列表"""
    ppts_list: List[PptItem] = Field(description="ppt口播文案列表")


STYLE_PRESETS = {
    "brief": {"tokens": "<=85", "style": "简明扼要，只讲核心要点，语言精炼"},
    "normal": {"tokens": "<=175", "style": "主要描述ppt现有内容，告知性"},
    "professional": {"tokens": "<=230", "style": "专业详尽，深入分析每个要点，适合学术或商务场景"},
}


def get_ppt_voice_content(md_content, style="normal"):
    json_parser = JsonOutputParser(pydantic_object=PptsInfoList)

    model = load_chat_model(
        model="deepseek-chat",
        provider="deepseek",
    )
    template_str='''
    你是口播文案专家，针对提供ppt内容生成每一页ppt的口播。
    要求：
        1，讲演篇幅：每页生成口播文档简洁，平均{tokens}个字。
        2.讲稿风格：{style}。
        3.对于每页ppt内容，需要详细介绍，不要遗漏每个细节。
    已知：
        <ppt的内容>
        {md_content}
        </ppt的内容
    输出格式：
         请返回包含以下结构的 JSON：
            {{
                "ppts_list": [
                    {{
                        "page_num": "页码",
                        "title": "每页ppt主题",
                        "content": "每页ppt的口播文案"
                    }}
                ]
            }}
         必须返回严格符合上述结构的 JSON 格式（不要包含任何其他文本）。
         
    输出每页口播文案列表。
    '''
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["normal"])
    prompt_template = PromptTemplate(
        input_variables=["md_content"],
        template=template_str,
        partial_variables={"tokens": preset["tokens"], "style": preset["style"]}
    )
    # formatted_template=prompt_template.format(md_content=md_content)
    runnable = prompt_template | model | json_parser
    ppt_list = runnable.invoke({"md_content":md_content})
    return ppt_list

if __name__ == '__main__':
    #读取md_ppt
    md_content=''
    with open('ppt.md', 'r', encoding='utf-8') as f:
        md_content= f.read()

    ppt_content=get_ppt_voice_content(md_content)
    print(ppt_content)