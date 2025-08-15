"""
风湿免疫科医生智能体

专门负责结缔组织病相关间质性肺病(CTD-ILD)和免疫相关ILD的诊断
"""

from typing import Dict, List, Any, Optional
from agents.base_agent import BaseAgent
from prompts import (
    RHEUMATOLOGY_SYSTEM_PROMPT,
    RHEUMATOLOGY_CTD_ILD_PROMPT,
)
from prompts.loader import safe_format, get_prompt
from datetime import datetime

class RheumatologyAgent(BaseAgent):
    """风湿免疫科医生智能体 - 专注CTD-ILD和免疫相关ILD诊断"""
    
    def __init__(self):
        super().__init__(
            name="风湿免疫科医生",
            specialty="风湿免疫-CTD-ILD",
            system_prompt=RHEUMATOLOGY_SYSTEM_PROMPT
        )
    
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: List[Dict[str, Any]] | None = None, stream: bool = False) -> Any:
        """分析病例并提供CTD-ILD诊断意见"""
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
            RHEUMATOLOGY_CTD_ILD_PROMPT,
            patient_id=case_info.get('patient_id', '未知'),
            symptoms=case_info.get('symptoms', '未提供'),
            medical_history=case_info.get('medical_history', '未提供'),
            family_history=case_info.get('family_history', '未提供'),
            imaging_results=case_info.get('imaging_results', '未提供'),
            pathology_results=case_info.get('pathology_results', '未提供'),
            lab_results=case_info.get('lab_results', '未提供'),
            autoantibody_results=case_info.get('autoantibody_results', '未提供自身抗体检测结果'),
            joint_symptoms=case_info.get('joint_symptoms', '未提供关节症状'),
            skin_manifestations=case_info.get('skin_manifestations', '未提供皮肤表现'),
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
    
    # 原主分析内联模板已外置
    
    def analyze_autoantibodies(self, antibody_results: str, clinical_features: str) -> Dict[str, Any]:
        """分析自身抗体谱"""
        template = get_prompt("RHEUMATOLOGY_AUTOANTIBODIES_PROMPT")
        filled, missing = safe_format(
            template,
            antibody_results=antibody_results,
            clinical_features=clinical_features
        )
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(抗体分析)",
            "specialty": "自身抗体分析",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def assess_ctd_classification(self, clinical_data: str, lab_results: str) -> Dict[str, Any]:
        """评估CTD分类诊断"""
        template = get_prompt("RHEUMATOLOGY_CTD_CLASSIFICATION_PROMPT")
        filled, missing = safe_format(template, clinical_data=clinical_data, lab_results=lab_results)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(CTD分类)",
            "specialty": "CTD分类诊断",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def evaluate_multisystem_involvement(self, system_review: str, examination_findings: str) -> Dict[str, Any]:
        """评估多系统受累"""
        template = get_prompt("RHEUMATOLOGY_MULTISYSTEM_PROMPT")
        filled, missing = safe_format(template, system_review=system_review, examination_findings=examination_findings)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(多系统评估)",
            "specialty": "多系统受累评估",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def recommend_immunotherapy(self, ctd_diagnosis: str, ild_severity: str) -> Dict[str, Any]:
        """推荐免疫治疗方案"""
        template = get_prompt("RHEUMATOLOGY_IMMUNOTHERAPY_PROMPT")
        filled, missing = safe_format(template, ctd_diagnosis=ctd_diagnosis, ild_severity=ild_severity)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(免疫治疗)",
            "specialty": "CTD-ILD免疫治疗",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
    
    def assess_prognosis_factors(self, ctd_type: str, ild_pattern: str, biomarkers: str) -> Dict[str, Any]:
        """评估预后因素"""
        template = get_prompt("RHEUMATOLOGY_PROGNOSIS_PROMPT")
        filled, missing = safe_format(template, ctd_type=ctd_type, ild_pattern=ild_pattern, biomarkers=biomarkers)
        if missing:
            filled += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
        response = self._call_llm(filled)
        
        return {
            "agent": f"{self.name}(预后评估)",
            "specialty": "CTD-ILD预后",
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "confidence": self._extract_confidence(response)
        }
