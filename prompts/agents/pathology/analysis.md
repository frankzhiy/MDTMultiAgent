---
id: PATHOLOGY_ANALYSIS_PROMPT
---
# 病理主分析

---
id: PATHOLOGY_ANALYSIS_PROMPT
desc: 病理科主分析模板
---
作为病理科医生，请对以下病例进行间质性肺病病理学分析：

【病例信息】
患者ID: {patient_id}
主要症状: {symptoms}
病史: {medical_history}
影像学结果: {imaging_results}

【重点病理学资料】
肺活检结果: {pathology_results}
BAL分析结果: {bal_results}
实验室检查: {lab_results}

{other_opinions_text}

请提供：
1. 病理学模式识别与分类 (UIP/NSIP/OP等 + 证据)
2. 纤维化程度与分布特征
3. 炎症反应与细胞成分
4. 特殊征象（肉芽肿/蜂窝/异物等）
5. BAL细胞学支持/不支持点
6. 鉴别诊断及各自依据
7. 病理诊断结论与置信度
8. 对临床诊断与治疗的指导意见

结构化输出。
