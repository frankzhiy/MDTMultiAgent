"""
呼吸科医生智能体

专门负责间质性肺病的临床诊断和治疗管理
"""

from typing import Dict, Any, List, Optional, Generator
from agents.base_agent import BaseAgent
from prompts import PULMONARY_SYSTEM_PROMPT, PULMONARY_ANALYSIS_PROMPT
from prompts.loader import safe_format, get_prompt
from datetime import datetime

class PulmonaryAgent(BaseAgent):
    """呼吸科医生智能体 - 专注间质性肺病诊断和治疗"""
    
    def __init__(self):
        super().__init__(
            name="呼吸科医生",
            specialty="呼吸内科-间质性肺病",
            system_prompt=PULMONARY_SYSTEM_PROMPT
        )
    
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: Optional[List[Dict[str, Any]]] = None, stream: bool = False) -> Any:
        """分析间质性肺病病例"""
        if other_opinions is None:
            other_opinions = []
        
        try:
            # 构建专门的呼吸科分析提示（外部模板）
            other_opinions_text = ""
            if other_opinions:
                lines = []
                for opinion in other_opinions:
                    if isinstance(opinion, dict):
                        agent_name = opinion.get('agent', '未知专科')
                        response = opinion.get('response') or opinion.get('full_response', '')
                        if response:
                            lines.append(f"【{agent_name}】:\n{response}")
                if lines:
                    other_opinions_text = "\n【其他专科意见参考】\n" + "\n\n".join(lines) + "\n"

            filled_prompt, missing = safe_format(
                PULMONARY_ANALYSIS_PROMPT,
                patient_id=case_info.get('patient_id', 'N/A'),
                symptoms=case_info.get('symptoms', 'N/A'),
                medical_history=case_info.get('medical_history', 'N/A'),
                imaging_results=case_info.get('imaging_results', 'N/A'),
                lab_results=case_info.get('lab_results', 'N/A'),
                pathology_results=case_info.get('pathology_results', 'N/A'),
                additional_info=case_info.get('additional_info', 'N/A'),
                other_opinions_text=other_opinions_text
            )
            if missing:
                filled_prompt += f"\n\n[提示: 缺失占位符 -> {', '.join(missing)}]"
            # 追加RAG上下文
            prompt = self._append_rag(filled_prompt, case_info)
            
            if stream:
                # 流式输出
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
                    
                    # 最终完成的响应
                    yield {
                        "agent": self.name,
                        "specialty": self.specialty,
                        "response": full_response,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "confidence": self._extract_confidence(full_response),
                        "focus_areas": ["临床症状", "肺功能", "疾病分类", "治疗方案"],
                        "is_complete": True
                    }
                
                return stream_generator()
            else:
                # 非流式输出（原有逻辑）
                response = self._call_llm(prompt)
                
                result = {
                    "agent": self.name,
                    "specialty": self.specialty,
                    "response": response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "confidence": self._extract_confidence(response),
                    "focus_areas": ["临床症状", "肺功能", "疾病分类", "治疗方案"]
                }
                
                return result
            
        except Exception as e:
            error_result = {
                "agent": self.name,
                "specialty": self.specialty,
                "response": f"呼吸科分析过程出现错误: {str(e)}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "confidence": 0.0,
                "error": str(e)
            }
            
            if stream:
                def error_generator():
                    error_result["is_complete"] = True
                    yield error_result
                return error_generator()
            else:
                return error_result
    
    # 原内联 prompt 构建已迁移至外部模板，不再需要该函数
    
    def _extract_confidence(self, response: str) -> float:
        """提取诊断信心度"""
        confidence_keywords = {
            "明确诊断": 0.9,
            "高度疑似": 0.8,
            "可能": 0.7,
            "考虑": 0.6,
            "待排除": 0.5,
            "不能排除": 0.4,
            "需要进一步": 0.3
        }
        
        response_lower = response.lower()
        max_confidence = 0.5
        
        for keyword, confidence in confidence_keywords.items():
            if keyword in response_lower:
                max_confidence = max(max_confidence, confidence)
        
        return max_confidence
