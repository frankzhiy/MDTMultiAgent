"""
影像科医生智能体

专门负责间质性肺病的影像学诊断，主要处理HRCT等影像的文字描述分析
"""

from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from prompts import IMAGING_SYSTEM_PROMPT, IMAGING_ANALYSIS_PROMPT
from prompts.loader import safe_format
from datetime import datetime

class ImagingAgent(BaseAgent):
    """影像科医生智能体 - 专注ILD影像学诊断"""
    
    def __init__(self):
        super().__init__(
            name="影像科医生",
            specialty="影像医学-胸部影像",
            system_prompt=IMAGING_SYSTEM_PROMPT
        )
    
    def analyze_case(self, case_info: Dict[str, Any], other_opinions: List[Dict[str, Any]] | None = None, stream: bool = False) -> Any:
        """分析影像学表现"""
        if other_opinions is None:
            other_opinions = []
        
        try:
            # 构建影像学分析提示（外部模板）
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
                IMAGING_ANALYSIS_PROMPT,
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
                        "focus_areas": ["影像模式", "分布特点", "密度特征", "进展评估"],
                        "is_complete": True
                    }
                
                return stream_generator()
            else:
                # 非流式输出（原有逻辑）
                response = self._call_llm(prompt, stream=stream)
                
                result = {
                    "agent": self.name,
                    "specialty": self.specialty,
                    "response": response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "confidence": self._extract_confidence(response),
                    "focus_areas": ["影像模式", "分布特点", "密度特征", "进展评估"]
                }
                
                return result
            
        except Exception as e:
            return {
                "agent": self.name,
                "specialty": self.specialty,
                "response": f"影像学分析过程出现错误: {str(e)}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "confidence": 0.0,
                "error": str(e)
            }
    
    # 内联影像学分析模板已外置
    
    def _extract_confidence(self, response: str) -> float:
        """提取影像学诊断信心度"""
        confidence_keywords = {
            "典型": 0.9,
            "符合": 0.8,
            "提示": 0.7,
            "疑似": 0.6,
            "可能": 0.5,
            "不除外": 0.4,
            "待确定": 0.3
        }
        
        response_lower = response.lower()
        max_confidence = 0.5
        
        for keyword, confidence in confidence_keywords.items():
            if keyword in response_lower:
                max_confidence = max(max_confidence, confidence)
        
        return max_confidence
