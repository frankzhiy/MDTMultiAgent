---
id: DATA_ANALYSIS_MAIN_PROMPT
desc: 数据分析主分析模板
---
作为数据分析专家，请对以下病例的定量数据进行分析：

【病例信息】
患者ID: {patient_id}
年龄性别: {demographics}
病程: {disease_duration}

【重点数据】
肺功能检查: {pft_results}
生物标志物: {biomarker_results}
随访数据: {serial_data}
实验室检查: {lab_results}
影像学结果: {imaging_results}

{other_opinions_text}

请提供：
1. 肺功能详细解读 (与预计值/进展趋势)
2. 生物标志物分析 (活动度/纤维化/预后)
3. 疾病严重程度量化与分级
4. 进展风险评估 (速度/预测指标)
5. 预后预测与风险分层
6. 治疗效果或反应初步判断
7. 随访监测建议 (周期/指标/触发条件)
8. 数据质量与局限说明

请使用结构化段落与要点列表。
