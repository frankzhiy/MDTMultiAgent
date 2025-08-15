---
id: PULMONARY_ANALYSIS_PROMPT
---
# 呼吸科主分析

---
id: PULMONARY_ANALYSIS_PROMPT
desc: 呼吸科主分析模板
---
作为呼吸科医生，请对以下间质性肺病疑似病例进行专业分析：

【患者基本信息】
患者ID: {patient_id}
主要症状: {symptoms}
病史信息: {medical_history}

【检查结果】
影像学检查: {imaging_results}
实验室检查: {lab_results}
病理检查: {pathology_results}
其他检查: {additional_info}

{other_opinions_text}

请从呼吸科专业角度提供以下分析：
1. 临床表现分析 (症状特点 / 进展模式 / 功能影响)
2. ILD分类诊断 (主要诊断 + 鉴别 + 诊断依据)
3. 严重程度与进展风险评估
4. 治疗建议 (药物 / 支持 / 康复)
5. 随访与监测计划 (时间节点 + 指标)
6. 预后提示与需警惕的改变

请基于最新指南，结构化输出，必要时使用小标题与要点。
