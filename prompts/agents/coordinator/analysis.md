---
id: COORDINATION_ANALYSIS_PROMPT
desc: 主协调员第一次整合个体+共享意见分析模板
---
作为MDT协调员，请基于以下信息进行综合分析和协调：

【病例信息】
患者ID: {patient_id}
主要症状: {symptoms}
病史: {medical_history}
影像学结果: {imaging_results}
实验室检查: {lab_results}
病理结果: {pathology_results}
其他信息: {additional_info}

【各专科医生意见】
{specialists_opinions}

请提供：
1. 各专科意见的总结与共识点
2. 主要分歧点及其临床影响
3. 综合诊断 (若存在多个可能请排序并说明理由)
4. 推荐的综合治疗方案 (含药物/支持/介入/等待观察)
5. 后续检查与随访计划
6. 关键风险、预后评估与需警惕的转归

输出需结构化分段，小标题清晰，必要时用要点列表。
