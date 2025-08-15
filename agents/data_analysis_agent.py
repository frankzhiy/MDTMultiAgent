"""
数据分析智能体

专门负责肺功能数据、实验室检查和生物标志物的定量分析
"""

from typing import Dict, List, Any, Optional
from agents.base_agent import BaseAgent
from prompts import (
    DATA_ANALYSIS_SYSTEM_PROMPT,
    DATA_ANALYSIS_MAIN_PROMPT,
)
from prompts.loader import safe_format, get_prompt
from datetime import datetime

class DataAnalysisAgent(BaseAgent):
    """数据分析智能体 - 专注ILD相关定量数据分析"""
    
    def __init__(self):
        super().__init__(
            name="数据分析专家",
            specialty="医学数据分析-ILD",
            system_prompt=DATA_ANALYSIS_SYSTEM_PROMPT
        )
    
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: List[Dict[str, Any]] | None = None, stream: bool = False) -> Any:
        """分析病例并提供数据分析意见"""
        if other_opinions is None:
            other_opinions = []

        other_opinions_text = ""
        if other_opinions:
            lines: List[str] = []
            for op in other_opinions:
                if isinstance(op, dict):
                    agent_name = op.get('agent', '未知专科')
                    response = op.get('response') or op.get('full_response', '')
                    if response:
                        lines.append(f"【{agent_name}】:\n{response}")
            if lines:
                other_opinions_text = "\n【其他专科意见参考】\n" + "\n\n".join(lines) + "\n"

        filled_prompt, missing = safe_format(
            DATA_ANALYSIS_MAIN_PROMPT,
            patient_id=case_info.get('patient_id', '未知'),
            demographics=case_info.get('demographics', '未提供'),
            disease_duration=case_info.get('disease_duration', '未提供'),
            pft_results=case_info.get('pulmonary_function_tests', '未提供肺功能检查'),
            biomarker_results=case_info.get('biomarker_results', '未提供生物标志物结果'),
            serial_data=case_info.get('serial_data', '未提供随访数据'),
            lab_results=case_info.get('lab_results', '未提供'),
            imaging_results=case_info.get('imaging_results', '未提供'),
            other_opinions_text=other_opinions_text
        )
        if missing:
            filled_prompt += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"

        prompt = self._append_rag(filled_prompt, case_info)

        if stream:
            def stream_generator():
                full_response = ""
                for chunk in self._call_llm(prompt, stream=True):
                    full_response += chunk
                    yield {
                        "agent": self.name,
                        "specialty": self.specialty,
                        "response_chunk": chunk,
                        "full_response": full_response,
                        "timestamp": datetime.now().isoformat(),
                        "is_complete": False
                    }
                self.add_to_history(case_info, full_response)
                yield {
                    "agent": self.name,
                    "specialty": self.specialty,
                    "response": full_response,
                    "timestamp": datetime.now().isoformat(),
                    "confidence": self._extract_confidence(full_response),
                    "is_complete": True
                }
            return stream_generator()
        else:
            response = self._call_llm(prompt, stream=False)
            self.add_to_history(case_info, response)
            return {
                "agent": self.name,
                "specialty": self.specialty,
                "response": response,
                "timestamp": datetime.now().isoformat(),
                "confidence": self._extract_confidence(response)
            }
    
    # 原主数据分析内联模板已外置
    
    def analyze_pulmonary_function(self, pft_data: str, reference_values: str) -> Dict[str, Any]:
        """分析肺功能数据"""
        template = get_prompt("DATA_PFT_ANALYSIS_PROMPT")
        filled, missing = safe_format(template, pft_data=pft_data, reference_values=reference_values)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(肺功能分析)",
            "specialty": "肺功能数据分析",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def evaluate_biomarkers(self, biomarker_levels: str, trend_data: str) -> Dict[str, Any]:
        """评估生物标志物"""
        template = get_prompt("DATA_BIOMARKER_ANALYSIS_PROMPT")
        filled, missing = safe_format(template, biomarker_levels=biomarker_levels, trend_data=trend_data)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(生物标志物)",
            "specialty": "生物标志物分析",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def calculate_disease_progression(self, serial_measurements: str, time_intervals: str) -> Dict[str, Any]:
        """计算疾病进展速度"""
        template = get_prompt("DATA_PROGRESSION_ANALYSIS_PROMPT")
        filled, missing = safe_format(template, serial_measurements=serial_measurements, time_intervals=time_intervals)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(进展分析)",
            "specialty": "疾病进展分析",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def build_prognostic_model(self, clinical_variables: str, outcome_data: str) -> Dict[str, Any]:
        """构建预后预测模型"""
        template = get_prompt("DATA_PROGNOSTIC_MODEL_PROMPT")
        filled, missing = safe_format(template, clinical_variables=clinical_variables, outcome_data=outcome_data)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(预后建模)",
            "specialty": "预后预测建模",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def assess_treatment_response(self, baseline_data: str, followup_data: str, treatment_info: str) -> Dict[str, Any]:
        """评估治疗反应"""
        template = get_prompt("DATA_TREATMENT_RESPONSE_PROMPT")
        filled, missing = safe_format(
            template,
            baseline_data=baseline_data,
            followup_data=followup_data,
            treatment_info=treatment_info
        )
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(治疗反应)",
            "specialty": "治疗反应评估",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def generate_monitoring_plan(self, current_status: str, risk_factors: str) -> Dict[str, Any]:
        """生成监测计划"""
        template = get_prompt("DATA_MONITORING_PLAN_PROMPT")
        filled, missing = safe_format(template, current_status=current_status, risk_factors=risk_factors)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(监测计划)",
            "specialty": "监测策略制定",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
