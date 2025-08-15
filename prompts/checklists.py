"""分析清单 (Checklists)

拆分出可插拔的结构化分析要点，供各 agent 组合实验。
"""

PULMONARY_ANALYSIS_CHECKLIST = """呼吸科分析重点:\n1. 临床表现\n2. ILD分类与鉴别\n3. 严重程度\n4. 治疗方案\n5. 随访计划"""

IMAGING_ANALYSIS_CHECKLIST = """影像学分析重点:\n1. 模式识别\n2. 分布特征\n3. 密度/结构\n4. 进展评估\n5. 鉴别诊断\n6. 随访建议"""

PATHOLOGY_ANALYSIS_CHECKLIST = """病理学分析要点:\n1. 模式识别\n2. 纤维化\n3. 炎症细胞\n4. 结构改变\n5. 特殊病变\n6. BAL分析\n7. 鉴别诊断"""

CTD_ILD_ANALYSIS_CHECKLIST = """CTD-ILD分析要点:\n1. CTD分类\n2. 自身抗体\n3. 多系统受累\n4. ILD与CTD关系\n5. 预后与风险\n6. 免疫治疗策略"""

DATA_ANALYSIS_CHECKLIST = """数据分析要点:\n1. 肺功能趋势\n2. 生物标志物\n3. 活动度\n4. 进展速度\n5. 预后预测\n6. 治疗反应\n7. 风险分层\n8. 监测建议"""

__all__ = [
    'PULMONARY_ANALYSIS_CHECKLIST', 'IMAGING_ANALYSIS_CHECKLIST', 'PATHOLOGY_ANALYSIS_CHECKLIST',
    'CTD_ILD_ANALYSIS_CHECKLIST', 'DATA_ANALYSIS_CHECKLIST'
]
