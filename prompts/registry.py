"""Prompt 文件注册表 (非工程人员只需增删 markdown 文件并在此登记)

键 = 常量名 (保持与原来 Python 常量一致)
值 = 相对 prompts 目录的 markdown 路径
"""

PROMPT_FILES = {
    # 基础 & 通用
    "SYSTEM_BASE_PROMPT": "system/base.md",
    "CASE_SUMMARY_PROMPT": "tasks/case_summary.md",
    "RAG_QUERY_PROMPT": "tasks/rag_query.md",

    # 协调员 (system + phases)
    "COORDINATOR_SYSTEM_PROMPT": "agents/coordinator/system.md",
    "COORDINATOR_PROMPT": "agents/coordinator/legacy_task.md",  # 旧模板保留
    "COORDINATION_ANALYSIS_PROMPT": "agents/coordinator/analysis.md",
    "CONFLICT_DETECTION_PROMPT": "agents/coordinator/conflict_detection.md",
    "CONSENSUS_EVALUATION_PROMPT": "agents/coordinator/consensus_evaluation.md",
    "FINAL_COORDINATION_PROMPT": "agents/coordinator/final_coordination.md",

    # 呼吸科
    "PULMONARY_SYSTEM_PROMPT": "agents/pulmonary/system.md",
    "PULMONARY_ANALYSIS_PROMPT": "agents/pulmonary/analysis.md",
    "PULMONARY_ANALYSIS_CHECKLIST": "agents/pulmonary/checklist.md",

    # 影像科
    "IMAGING_SYSTEM_PROMPT": "agents/imaging/system.md",
    "IMAGING_ANALYSIS_PROMPT": "agents/imaging/analysis.md",
    "IMAGING_ANALYSIS_CHECKLIST": "agents/imaging/checklist.md",

    # 病理科 (含子任务)
    "PATHOLOGY_SYSTEM_PROMPT": "agents/pathology/system.md",
    "PATHOLOGY_ANALYSIS_PROMPT": "agents/pathology/analysis.md",
    "BAL_CYTOLOGY_PROMPT": "agents/pathology/bal_cytology.md",
    "FIBROSIS_PATTERN_PROMPT": "agents/pathology/fibrosis_pattern.md",
    "PATHOLOGY_SPECIAL_FEATURES_PROMPT": "agents/pathology/special_features.md",
    "PATHOLOGY_DIFFERENTIAL_PROMPT": "agents/pathology/differential.md",
    "PATHOLOGY_ANALYSIS_CHECKLIST": "agents/pathology/checklist.md",

    # 风湿免疫 (含子任务)
    "RHEUMATOLOGY_SYSTEM_PROMPT": "agents/rheumatology/system.md",
    "RHEUMATOLOGY_CTD_ILD_PROMPT": "agents/rheumatology/ctd_ild.md",
    "RHEUMATOLOGY_AUTOANTIBODIES_PROMPT": "agents/rheumatology/autoantibodies.md",
    "RHEUMATOLOGY_CTD_CLASSIFICATION_PROMPT": "agents/rheumatology/ctd_classification.md",
    "RHEUMATOLOGY_MULTISYSTEM_PROMPT": "agents/rheumatology/multisystem.md",
    "RHEUMATOLOGY_IMMUNOTHERAPY_PROMPT": "agents/rheumatology/immunotherapy.md",
    "RHEUMATOLOGY_PROGNOSIS_PROMPT": "agents/rheumatology/prognosis.md",
    "CTD_ILD_ANALYSIS_CHECKLIST": "agents/rheumatology/checklist.md",

    # 数据分析 (含子任务)
    "DATA_ANALYSIS_SYSTEM_PROMPT": "agents/data/system.md",
    "DATA_ANALYSIS_MAIN_PROMPT": "agents/data/analysis.md",
    "DATA_PFT_ANALYSIS_PROMPT": "agents/data/pft_analysis.md",
    "DATA_BIOMARKER_ANALYSIS_PROMPT": "agents/data/biomarker_analysis.md",
    "DATA_PROGRESSION_ANALYSIS_PROMPT": "agents/data/progression_analysis.md",
    "DATA_PROGNOSTIC_MODEL_PROMPT": "agents/data/prognostic_model.md",
    "DATA_TREATMENT_RESPONSE_PROMPT": "agents/data/treatment_response.md",
    "DATA_MONITORING_PLAN_PROMPT": "agents/data/monitoring_plan.md",
    "DATA_ANALYSIS_CHECKLIST": "agents/data/checklist.md",
}
