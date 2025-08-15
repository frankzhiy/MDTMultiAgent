"""任务/指令类提示词 (Task / Instruction Prompts)

与具体一次任务执行相关，需要填充变量。
"""

COORDINATOR_PROMPT = """你是MDT讨论的协调员，需要基于各专科意见形成结构化总结与下一步建议。\n\n病例信息：\n{case_info}\n\n专家意见：\n{all_opinions}\n"""

CASE_SUMMARY_PROMPT = """请对本次MDT讨论生成总结报告：\n1. 病例摘要\n2. 各专科要点\n3. 诊断与分歧\n4. 综合治疗方案\n5. 随访计划\n\n病例：\n{case_info}\n讨论：\n{discussion_process}\n最终：\n{final_decision}\n"""

RAG_QUERY_PROMPT = """请基于以下医学知识回答临床问题：\n问题：{query}\n资料：\n{context}\n请给出循证引用及建议。"""

__all__ = ['COORDINATOR_PROMPT', 'CASE_SUMMARY_PROMPT', 'RAG_QUERY_PROMPT']
