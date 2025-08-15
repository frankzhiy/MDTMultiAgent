---
id: FINAL_COORDINATION_PROMPT
desc: 最终协调综合建议模板
---
作为MDT协调员，请基于完整多轮讨论与共识评估结果生成最终综合建议。

【病例信息】
患者ID: {patient_id}
主要症状: {symptoms}
病史: {medical_history}
影像学结果: {imaging_results}

【讨论过程摘要】
- 独立分析专家数: {individual_count}
- 初步讨论专家数: {sharing_count}
- 多轮讨论: {multi_round_status}
- 共识状态: {consensus_status}

【共识评估】
{consensus_summary}

【最终专家意见汇总】
{final_opinions}

请提供：
1. 综合诊断结论（如多诊断请按置信度排序）
2. 治疗与管理方案（药物/支持/康复/介入/监测）
3. 优先级与时间安排（短期/中期/长期）
4. 风险与预后评估（含关键转归指标）
5. 随访与复评计划（时间节点 + 触发条件）
6. 患者与家属沟通要点
7. 若存在分歧：并列列出不同观点与适用情形

输出保持结构清晰、要点化，必要时使用表格。
