import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

def setup_logging(level: str = "INFO") -> None:
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('mdt_system.log'),
            logging.StreamHandler()
        ]
    )

def format_agent_response(agent_name: str, response: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
    """格式化智能体响应"""
    if timestamp is None:
        timestamp = datetime.now()
    
    return {
        "agent": agent_name,
        "response": response,
        "timestamp": timestamp.isoformat(),
        "formatted_time": timestamp.strftime("%Y-%m-%d %H:%M:%S")
    }

def parse_medical_case(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """解析医疗病例数据"""
    required_fields = ["patient_id", "symptoms", "medical_history"]
    
    for field in required_fields:
        if field not in case_data:
            raise ValueError(f"Missing required field: {field}")
    
    return {
        "patient_id": case_data["patient_id"],
        "symptoms": case_data["symptoms"],
        "medical_history": case_data["medical_history"],
        "imaging_results": case_data.get("imaging_results", ""),
        "lab_results": case_data.get("lab_results", ""),
        "pathology_results": case_data.get("pathology_results", ""),
        "additional_info": case_data.get("additional_info", "")
    }

def save_mdt_session(session_data: Dict[str, Any], filename: Optional[str] = None) -> str:
    """保存MDT会议记录"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mdt_session_{timestamp}.json"
    
    filepath = f"./data/sessions/{filename}"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)
    
    return filepath

def load_mdt_session(filepath: str) -> Dict[str, Any]:
    """加载MDT会议记录"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_consensus_score(agent_responses: List[Dict[str, Any]]) -> float:
    """计算智能体间的共识度（简化版本）"""
    # 这里可以实现更复杂的共识度计算算法
    # 目前返回一个基于响应数量的简单分数
    if not agent_responses:
        return 0.0
    
    # 基于响应的一致性关键词计算共识度
    consensus_keywords = ["同意", "支持", "建议", "推荐", "确诊"]
    total_score = 0
    
    for response in agent_responses:
        content = response.get("response", "").lower()
        score = sum(1 for keyword in consensus_keywords if keyword in content)
        total_score += min(score / len(consensus_keywords), 1.0)
    
    return total_score / len(agent_responses)

import os
