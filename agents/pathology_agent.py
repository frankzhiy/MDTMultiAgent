"""
病理科医生智能体

专门负责间质性肺病的病理学诊断，包括肺活检和支气管肺泡灌洗液分析
"""

from typing import Dict, List, Any, Optional
from agents.base_agent import BaseAgent
from prompts import (
    PATHOLOGY_SYSTEM_PROMPT,
    PATHOLOGY_ANALYSIS_PROMPT,
)
from prompts.loader import safe_format, get_prompt
from datetime import datetime

class PathologyAgent(BaseAgent):
    """病理科医生智能体 - 专注ILD病理学诊断"""
    
    def __init__(self):
        super().__init__(
            name="病理科医生",
            specialty="病理学-肺病理",
            system_prompt=PATHOLOGY_SYSTEM_PROMPT
        )
    
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: List[Dict[str, Any]] | None = None, stream: bool = False) -> Any:
        """分析病例并提供ILD病理学意见"""
        if other_opinions is None:
            other_opinions = []

        # 构建ILD病理学分析提示词（外部模板）
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
            PATHOLOGY_ANALYSIS_PROMPT,
            patient_id=case_info.get('patient_id', '未知'),
            symptoms=case_info.get('symptoms', '未提供'),
            medical_history=case_info.get('medical_history', '未提供'),
            imaging_results=case_info.get('imaging_results', '未提供'),
            pathology_results=case_info.get('pathology_results', '未提供病理学检查结果'),
            bal_results=case_info.get('bal_results', '未提供BAL结果'),
            lab_results=case_info.get('lab_results', '未提供'),
            other_opinions_text=other_opinions_text
        )
        if missing:
            filled_prompt += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"

        # 追加RAG上下文
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
    
    # 原主分析内联模板已外置
    
    def analyze_bal_cytology(self, bal_results: str, clinical_context: str) -> Dict[str, Any]:
        """分析支气管肺泡灌洗液细胞学"""
        template = get_prompt("BAL_CYTOLOGY_PROMPT")
        filled, missing = safe_format(
            template,
            bal_results=bal_results,
            clinical_context=clinical_context
        )
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(BAL分析)",
            "specialty": "BAL细胞学",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def assess_fibrosis_pattern(self, histologic_findings: str, imaging_pattern: str) -> Dict[str, Any]:
        """评估纤维化模式"""
        template = get_prompt("FIBROSIS_PATTERN_PROMPT")
        filled, missing = safe_format(
            template,
            histologic_findings=histologic_findings,
            imaging_pattern=imaging_pattern
        )
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(纤维化评估)",
            "specialty": "ILD纤维化病理",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def identify_special_features(self, pathology_findings: str, clinical_scenario: str) -> Dict[str, Any]:
        """识别特殊病理学特征"""
        template = get_prompt("PATHOLOGY_SPECIAL_FEATURES_PROMPT")
        filled, missing = safe_format(
            template,
            pathology_findings=pathology_findings,
            clinical_scenario=clinical_scenario
        )
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(特殊特征)",
            "specialty": "病理学-特殊征象",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def provide_differential_diagnosis(self, pathology_pattern: str, clinical_data: str) -> Dict[str, Any]:
        """提供病理学鉴别诊断"""
        template = get_prompt("PATHOLOGY_DIFFERENTIAL_PROMPT")
        filled, missing = safe_format(
            template,
            pathology_pattern=pathology_pattern,
            clinical_data=clinical_data
        )
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(鉴别诊断)",
            "specialty": "病理学-鉴别诊断",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
