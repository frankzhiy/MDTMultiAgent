"""
间质病MDT智能诊疗系统 - Streamlit界面
专业的多学科团队讨论平台，为间质性肺病诊疗提供智能化支持
"""

import streamlit as st
import time
import json
import markdown
import html
import re
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator
import threading
import queue
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from mdt_system.orchestrator import MDTOrchestrator
from utils.config import config
from test_data import get_test_mdt_result
import logging
from prompts import list_prompts as _list_prompts  # type: ignore
from prompts import reload_all_prompts as _reload_all_prompts  # type: ignore
from prompts import get_prompt as _get_prompt  # type: ignore
from prompts.loader import safe_format as _safe_format, get_prompt_meta as _get_prompt_meta  # type: ignore
from knowledge.vector_store import get_knowledge_store  # 惰性获取实例

# 使用 Streamlit 资源级缓存，避免每次脚本重跑都重复初始化
@st.cache_resource(show_spinner=False)
def _get_cached_knowledge_store():
    return get_knowledge_store()

# 轻量实例（内部惰性加载索引/嵌入），避免模块导入时阻塞
knowledge_store = _get_cached_knowledge_store()

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 页面配置
st.set_page_config(
    page_title="间质病MDT智能系统",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS - 为专业MDT界面优化
st.markdown("""
<style>
    /* 隐藏默认UI */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* 背景与容器 */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }
    
    /* 卡片样式 - 融合原 stream + 统一风格 */
    .stream-card {
        background: linear-gradient(145deg, #ffffff, #f8f9fa);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.06);
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .stream-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px rgba(0,0,0,0.12);
    }
    
    /* 专家头像区域 - 三栏式布局 */
    .expert-header {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 2px solid rgba(0,0,0,0.05);
    }
    
    .expert-avatar {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        margin-right: 16px;
        font-size: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border: 3px solid white;
    }
    
    .expert-info {
        flex: 1;
    }
    
    .expert-info h3 {
        margin: 0 0 4px 0;
        color: #2c3e50;
        font-size: 20px;
        font-weight: 600;
    }
    
    .expert-info p {
        margin: 0;
        color: #7f8c8d;
        font-size: 14px;
        font-weight: 500;
    }
    
    /* 动态内容区域 */
    .stream-content {
        min-height: 120px;
        line-height: 1.7;
        font-size: 15px;
        color: #34495e;
        background: rgba(255,255,255,0.7);
        border-radius: 12px;
        padding: 20px;
        margin-top: 12px;
        /* 新增：限制卡片高度并允许内部滚动 */
        max-height: 340px;
        overflow-y: auto;
        scrollbar-width: thin; /* Firefox */
        scrollbar-color: rgba(0,0,0,0.25) transparent;
    }

    /* WebKit滚动条美化 */
    .stream-content::-webkit-scrollbar {
        width: 8px;
    }
    .stream-content::-webkit-scrollbar-track {
        background: transparent;
    }
    .stream-content::-webkit-scrollbar-thumb {
        background: rgba(0,0,0,0.18);
        border-radius: 4px;
    }
    .stream-content::-webkit-scrollbar-thumb:hover {
        background: rgba(0,0,0,0.33);
    }
    
    /* 打字机效果 */
    .typing-indicator {
        display: inline-block;
        animation: pulse 1.5s infinite;
        color: #3498db;
        font-weight: bold;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.1); }
    }
    
    /* 状态指示器 - 右上角徽章 */
    .status-indicator {
        position: absolute;
        top: 20px;
        right: 20px;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .status-thinking {
        background: linear-gradient(135deg, #f39c12, #e67e22);
        color: white;
    }
    
    .status-typing {
        background: linear-gradient(135deg, #27ae60, #2ecc71);
        color: white;
        animation: pulse 2s infinite;
    }
    
    .status-complete {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
    }
    
    /* 阶段进度卡片 */
    .phase-progress {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 16px;
        padding: 24px;
        margin: 24px 0;
        color: white;
        text-align: center;
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
    }
    
    .phase-progress h3 {
        margin: 0 0 8px 0;
        font-size: 24px;
        font-weight: 700;
    }
    
    .phase-progress p {
        margin: 0;
        font-size: 16px;
        opacity: 0.9;
    }
    
    /* 专家回复文本容器 */
    .stream-text {
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    
    /* 响应式列 */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        .stream-card {
            margin: 8px 0;
            padding: 16px;
        }
        
        .expert-header {
            flex-direction: column;
            text-align: center;
        }
        
        .expert-avatar {
            margin: 0 0 12px 0;
        }
        
        .stream-content {
            margin-top: 16px;
            padding: 16px;
        }
        
        .status-indicator {
            position: static;
            margin: 12px 0 0 0;
            display: inline-block;
        }
    }
    
    /* 页面标题和布局 */
    .main-title {
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        font-size: 36px;
        font-weight: 800;
        margin: 24px 0;
        letter-spacing: -0.5px;
    }
    
    .section-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #667eea, transparent);
        margin: 32px 0;
        border: none;
    }
    
    /* 加载动画 */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #3498db;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-right: 8px;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* 指标卡片 / 结果总结卡片 */
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .summary-card {
        background: linear-gradient(135deg, #74b9ff, #0984e3);
        border-radius: 16px;
        padding: 32px;
        margin: 24px 0;
        color: white;
        box-shadow: 0 12px 32px rgba(116, 185, 255, 0.3);
    }
    
    .summary-card h2 {
        margin: 0 0 16px 0;
        font-size: 28px;
        font-weight: 700;
    }
    
    .summary-card .content {
        font-size: 16px;
        line-height: 1.8;
        opacity: 0.95;
    }

    /* 静态结果展示卡片可滚动区域 */
    .card-scroll {
        max-height: 340px;
        overflow-y: auto;
        padding-right: 4px;
        scrollbar-width: thin;
        scrollbar-color: rgba(0,0,0,0.25) transparent;
    }
    .card-scroll::-webkit-scrollbar { width: 8px; }
    .card-scroll::-webkit-scrollbar-track { background: transparent; }
    .card-scroll::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius:4px; }
    .card-scroll::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.33); }
    
    /* 错误提示 */
    .error-message {
        background: linear-gradient(135deg, #e74c3c, #c0392b);
        color: white;
        padding: 20px;
        border-radius: 12px;
        margin: 16px 0;
        box-shadow: 0 6px 20px rgba(231, 76, 60, 0.3);
    }
    
    .error-message .icon {
        font-size: 24px;
        margin-right: 12px;
        vertical-align: middle;
    }

    /* ===== 新增：后期阶段全宽卡片与专业Markdown样式 ===== */
    .phase-wide-card {
        background: linear-gradient(145deg,#ffffff,#f6f7fb);
        border: 1px solid rgba(0,0,0,0.06);
        border-radius: 18px;
        padding: 28px 34px;
        margin: 26px 0 34px 0;
        box-shadow: 0 10px 30px -5px rgba(0,0,0,0.08);
        position: relative;
        overflow: hidden;
    }
    .phase-wide-card:before {
        content: "";
        position: absolute;
        top:0;left:0;right:0;height:6px;
        background: linear-gradient(90deg,#667eea,#764ba2,#4facfe);
        opacity:.85;
    }
    .phase-wide-card h3.section-title {
        margin:0 0 14px 0;
        font-size:22px;
        font-weight:700;
        background: linear-gradient(135deg,#2c3e50,#667eea);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
        letter-spacing:.5px;
    }
    .phase-wide-card .sub-note {margin:0 0 18px 0;color:#566176;font-size:14px;}
    .phase-wide-card .metric-badges {display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 18px 0;}
    .phase-wide-card .metric-badge {background:#eef1f7;padding:8px 14px;border-radius:30px;font-size:12px;font-weight:600;color:#415061;box-shadow:0 2px 4px rgba(0,0,0,0.05);}    

    /* 专业Markdown容器 */
    .mdt-md {font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;line-height:1.7;font-size:15px;color:#2c3e50;}
    .mdt-md h1,.mdt-md h2,.mdt-md h3,.mdt-md h4 {font-weight:700;line-height:1.25;margin:1.4em 0 .6em;position:relative;}
    .mdt-md h1 {font-size:1.9rem;border-bottom:2px solid #e0e4ec;padding-bottom:.4rem;}
    .mdt-md h2 {font-size:1.55rem;border-left:6px solid #667eea;padding-left:.6rem;background:linear-gradient(90deg,#f0f3fa,#ffffff);} 
    .mdt-md h3 {font-size:1.25rem;}
    .mdt-md h4 {font-size:1.05rem;color:#374151;}
    .mdt-md p {margin:0 0 1em;}
    .mdt-md ul, .mdt-md ol {margin:0 0 1.1em 1.4em;padding:0;}
    .mdt-md li {margin:.3em 0;}
    .mdt-md code {background:#f3f4f7;padding:2px 5px;border-radius:4px;font-size:90%;}
    .mdt-md pre {background:#1e293b;color:#e2e8f0;padding:14px 16px;border-radius:10px;overflow:auto;font-size:13px;line-height:1.5;}
    .mdt-md table {border-collapse:collapse;width:100%;margin:1.2em 0;}
    .mdt-md th, .mdt-md td {border:1px solid #dfe3eb;padding:8px 10px;font-size:13px;}
    .mdt-md th {background:#f1f4fa;font-weight:600;}
    .mdt-md blockquote {margin:1em 0;padding:12px 18px;border-left:6px solid #667eea;background:#f5f7fc;border-radius:8px;color:#394b63;}
    .mdt-md hr {border:none;border-top:1px solid #e1e5ec;margin:2rem 0;}
    .mdt-md strong {color:#1f2d3d;}
    .mdt-md .callout-title {display:inline-block;background:#667eea;color:#fff;padding:2px 10px;border-radius:6px;margin-right:8px;font-size:12px;letter-spacing:.5px;}
    .mdt-md .emphasis {background:linear-gradient(90deg,#fff6e5,#fff);padding:6px 10px;border-left:4px solid #ffb347;border-radius:6px;}
    .mdt-md a {color:#2563eb;text-decoration:none;}
    .mdt-md a:hover {text-decoration:underline;}
    .mdt-md .section-anchor {position:absolute;left:-12px;opacity:0;transition:.2s;font-size:14px;}
    .mdt-md h2:hover .section-anchor, .mdt-md h3:hover .section-anchor {opacity:.55;}

    /* 下载报告预览 */
    .report-preview {background:#ffffff;border:1px solid #e2e6ef;border-radius:16px;padding:28px 32px;margin:20px 0;box-shadow:0 6px 18px -4px rgba(0,0,0,0.08);}    

    /* ===== 动态流程图（水平步骤流） ===== */
    .mdt-flow-wrapper {background:linear-gradient(145deg,#ffffff,#f5f7fb);border:1px solid #e1e5ec;border-radius:18px;padding:20px 28px;margin:18px 0 30px 0;box-shadow:0 6px 22px -6px rgba(0,0,0,0.08);}
    .mdt-flow-steps {display:flex;flex-wrap:wrap;gap:12px 32px;align-items:flex-start;}
    .mdt-flow-step {position:relative;padding:10px 14px 10px 52px;min-width:180px;background:#ffffff;border:1px solid #dde2eb;border-radius:14px;box-shadow:0 4px 12px -4px rgba(0,0,0,.06);transition:.25s;}
    .mdt-flow-step:hover {box-shadow:0 8px 20px -6px rgba(0,0,0,.12);}    
    .mdt-flow-step.pending {opacity:.55;}
    .mdt-flow-step.current {border-color:#667eea;box-shadow:0 6px 18px -4px rgba(102,126,234,.45);} 
    .mdt-flow-step.done {background:linear-gradient(145deg,#eef7ff,#ffffff);border-color:#6abf69;}
    .mdt-flow-circle {position:absolute;left:14px;top:50%;transform:translateY(-50%);width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600;color:#fff;box-shadow:0 2px 6px rgba(0,0,0,.25);}    
    .mdt-flow-circle.pending {background:#b0b8c6;}
    .mdt-flow-circle.current {background:linear-gradient(135deg,#667eea,#764ba2);} 
    .mdt-flow-circle.done {background:#2ecc71;}
    .mdt-flow-title {margin:0 0 4px 0;font-size:14px;font-weight:600;color:#2d3748;}
    .mdt-flow-desc {margin:0;font-size:11px;line-height:1.3;color:#5a6475;}
    .mdt-flow-metrics {display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;}
    .mdt-flow-badge {background:#eef1f7;padding:3px 8px;border-radius:12px;font-size:10px;font-weight:600;color:#445268;}
    .mdt-flow-rounds {margin-top:6px;font-size:11px;color:#37486b;font-weight:600;}
    .mdt-flow-active-agents {margin-top:4px;font-size:10px;color:#5b6472;}
    .mdt-flow-divider {height:1px;background:linear-gradient(90deg,transparent,#c8d2e2,transparent);margin:12px 0;}
</style>
""", unsafe_allow_html=True)

# 专家配色方案
EXPERT_COLORS = {
    "呼吸科专家": "#667eea",
    "影像科专家": "#f093fb", 
    "病理科专家": "#4facfe",
    "风湿免疫科专家": "#43e97b",
    "数据分析专家": "#fa709a",
    "MDT协调员": "#a8edea"
}

# 全局专家名称映射（统一别名匹配，避免各函数重复定义）
EXPERT_NAME_MAPPING = {
    "呼吸科专家": ["pulmonary", "respiratory", "呼吸科", "呼吸科医生"],
    "影像科专家": ["imaging", "radiology", "影像科", "影像科医生"],
    "病理科专家": ["pathology", "病理科", "病理科医生"],
    "风湿免疫科专家": ["rheumatology", "风湿免疫科", "风湿免疫科医生"],
    "数据分析专家": ["data_analysis", "数据分析", "数据分析专家"],
    # 协调员不参与过滤逻辑，仅在最终阶段显示
    "MDT协调员": ["coordinator", "协调员", "mdt协调员"]
}

def get_expert_color(expert_name: str) -> str:
    """获取专家对应的颜色"""
    for key, color in EXPERT_COLORS.items():
        if key in expert_name:
            return color
    return "#6c757d"  # 默认颜色

def is_expert_selected(expert_name: str, selected_experts: List[str]) -> bool:
    """检查专家是否被选中"""
    # 协调员（MDT协调员）应始终显示（冲突检测 / 共识评估 / 最终协调阶段需要它的输出）
    if any(key.lower() in expert_name.lower() for key in ["协调员", "mdt协调员", "coordinator"]):
        return True
    for selected in selected_experts:
        # 直接名称包含匹配
        if selected in expert_name or expert_name in selected:
            return True
        # 别名匹配
        for alias in EXPERT_NAME_MAPPING.get(selected, []):
            if alias.lower() in expert_name.lower():
                return True
    return False

def display_expert_response(container, expert_name: str, full_text: str, status: str = "typing"):
    """显示专家回复内容"""
    color = get_expert_color(expert_name)
    
    # 状态样式
    status_class = f"status-{status}"
    status_text = {
        "thinking": "思考中...",
        "typing": "回复中...", 
        "complete": "完成"
    }.get(status, "处理中...")
    
    # 使用 render_markdown_content 处理文本内容
    if full_text.strip():
        rendered_content = render_markdown_content(full_text)
        # 移除外层 div 样式，只保留内部 HTML
        import re
        # 提取 div 内的内容
        content_match = re.search(r'<div[^>]*>(.*)</div>', rendered_content, re.DOTALL)
        if content_match:
            processed_text = content_match.group(1)
        else:
            processed_text = full_text
    else:
        processed_text = full_text
    
    # 构建完整的HTML
    html_content = f"""
    <div class="stream-card">
        <div class="expert-header">
            <div class="expert-avatar" style="background: {color};">
                {expert_name[0]}
            </div>
            <div class="expert-info">
                <h3>{expert_name}</h3>
                <p>{expert_name.replace('专家', '').replace('MDT', '多学科')}</p>
            </div>
        </div>
        <div class="status-indicator {status_class}">{status_text}</div>
        <div class="stream-content">
            <div class="stream-text">{processed_text}{'<span class="typing-indicator">●</span>' if status == 'typing' else ''}</div>
        </div>
    </div>
    """
    
    container.markdown(html_content, unsafe_allow_html=True)

def render_phase_header(phase_name: str, description: str):
    """渲染阶段标题"""
    st.markdown(f"""
    <div class="phase-progress">
        <h3>🔄 {phase_name}</h3>
        <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)

def render_markdown_content(content: str) -> str:
    """
    使用 Python markdown 包渲染 Markdown 内容
    支持更好的格式化和扩展功能
    """
    if not content:
        return ""
    
    # 清理内容：移除过多的空行
    cleaned_content = re.sub(r"\n{3,}", "\n\n", content.strip())
    
    try:
        # 使用 markdown 包转换，只使用兼容的扩展
        md = markdown.Markdown(extensions=[
            'extra',          # 支持表格、代码块等
            'nl2br'          # 换行转换为 <br>
        ])
        
        # 转换为 HTML
        html_content = md.convert(cleaned_content)
        
        # 简化的样式处理，避免与 Streamlit 冲突
        # 为 h2/h3 添加锚点符号
        import re as _re
        def _add_anchor(match):
            tag = match.group(1)
            title = match.group(2)
            anchor_id = _re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]+', '-', title).strip('-').lower()
            return f'<{tag} id="{anchor_id}"><span class="section-anchor">#</span>{title}</{tag}>'
        html_content = _re.sub(r'<(h[23])>(.*?)</h[23]>', _add_anchor, html_content)

        styled_content = f"""
        <div class="mdt-md">
            {html_content}
        </div>
        """
        
        return styled_content
        
    except Exception as e:
        # 如果 markdown 处理失败，回退到简单的文本处理
        logger.warning(f"Markdown rendering failed: {e}")
        # 简单的文本处理：保留换行和基本格式
        escaped_content = html.escape(cleaned_content)
        formatted_content = escaped_content.replace('\n', '<br>')
        
    return f"""
    <div class=\"mdt-md\">{formatted_content}</div>
    """

def display_case_summary():
    """显示病例摘要信息（只读模式）"""
    case_data = st.session_state.get("case_data", {})
    
    if not case_data:
        st.warning("未找到病例信息")
        return
    
    st.header("📋 当前病例信息")
    
    # 第一行
    col1_1, col1_2, col1_3 = st.columns(3)
    
    with col1_1:
        st.markdown(f"**患者ID:** {case_data.get('patient_id', 'N/A')}")
    
    with col1_2:
        st.markdown("**主要症状:**")
        st.text(case_data.get('chief_complaint', ''))
    
    with col1_3:
        st.markdown("**既往史:**")
        st.text(case_data.get('medical_history', ''))
    
    # 第二行
    col2_1, col2_2, col2_3 = st.columns(3)
    
    with col2_1:
        st.markdown("**现病史:**")
        st.text(case_data.get('present_illness', ''))
    
    with col2_2:
        st.markdown("**检查结果:**")
        st.text(case_data.get('examination_results', ''))
    
    with col2_3:
        st.markdown("**体格检查:**")
        st.text(case_data.get('physical_examination', ''))
    
    # 第三行
    col3_1, col3_2, col3_3 = st.columns(3)
    
    with col3_1:
        st.markdown("**实验室检查:**")
        st.text(case_data.get('lab_results', ''))
    
    with col3_2:
        st.markdown("**生物标志物:**")
        st.text(case_data.get('biomarker_results', ''))
    
    with col3_3:
        st.markdown("**肺功能检查:**")
        st.text(case_data.get('pulmonary_function_tests', ''))

def main():
    """主应用程序"""
    # 使用新的样式标题
    st.markdown('<h1 class="main-title">🏥 间质病MDT智能诊疗系统</h1>', unsafe_allow_html=True)
    st.markdown("**专业的多学科团队讨论平台 - 为间质性肺病诊疗提供智能化支持**")
    
    # 分割线
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # 侧边栏配置
    with st.sidebar:
        st.header("📋 系统配置")

        # 专家选择
        st.subheader("👥 参与专家")
        available_experts = [
            "呼吸科专家", "影像科专家", "病理科专家",
            "风湿免疫科专家", "数据分析专家"
        ]
        selected_experts = st.multiselect(
            "选择参与讨论的专家",
            available_experts,
            default=available_experts
        )

        if st.button(
            "🚀 开始MDT讨论",
            type="primary",
            use_container_width=True
        ):
            st.session_state.start_stream = True
            st.session_state.stream_complete = False
            st.session_state.current_phase = None
            st.session_state.expert_containers = {}

        st.markdown("---")
        # 知识库 / RAG 管理面板
        st.subheader("📚 知识库管理")
        
        # 显示当前状态
        stats = knowledge_store.get_collection_stats()
        backend = stats.get('backend','N/A')
        total_docs = stats.get('total_documents', 0)
        st.caption(f"Backend: {backend} | 向量片段: {total_docs} | 状态: {stats.get('status')}")
        
        # 显示当前知识库中的文件列表
        with st.expander("📋 已加载文件列表", expanded=False):
            docs_dir = os.path.join(project_root, 'knowledge', 'documents')
            if os.path.isdir(docs_dir):
                files = []
                for ext in ['*.txt', '*.md', '*.pdf', '*.csv']:
                    files.extend(glob.glob(os.path.join(docs_dir, ext)))
                
                if files:
                    st.write(f"📁 文件目录: `{docs_dir}`")
                    for i, file_path in enumerate(sorted(files), 1):
                        file_name = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path)
                        size_kb = file_size / 1024
                        file_ext = os.path.splitext(file_name)[1].upper()
                        st.write(f"{i}. **{file_name}** ({file_ext}, {size_kb:.1f}KB)")
                else:
                    st.info("📭 documents 文件夹为空")
            else:
                st.warning("📁 documents 目录不存在")
        
        # 文件上传功能
        st.markdown("#### 📤 上传新文件")
        uploaded_files = st.file_uploader(
            "选择文件上传到知识库", 
            type=["txt", "md", "pdf", "csv"], 
            accept_multiple_files=True,
            help="支持 TXT, MD, PDF, CSV 格式，上传后将保存到 knowledge/documents 文件夹"
        )
        
        if uploaded_files:
            docs_dir = os.path.join(project_root, 'knowledge', 'documents')
            os.makedirs(docs_dir, exist_ok=True)
            
            saved_files = []
            for uploaded_file in uploaded_files:
                # 保存文件到 documents 目录
                file_path = os.path.join(docs_dir, uploaded_file.name)
                
                # 检查文件是否已存在
                if os.path.exists(file_path):
                    st.warning(f"⚠️ 文件 {uploaded_file.name} 已存在，将被覆盖")
                
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_files.append(uploaded_file.name)
            
            if saved_files:
                st.success(f"✅ 已保存 {len(saved_files)} 个文件到 documents 文件夹")
                for fname in saved_files:
                    st.write(f"   📄 {fname}")
                st.info("💡 点击下方「增量更新」按钮将新文件添加到向量库")
        
        # 知识库操作按钮
        st.markdown("#### 🔧 知识库操作")
        col_kb1, col_kb2, col_kb3 = st.columns(3)
        
        with col_kb1:
            if st.button('🔄 完全重建', help='清空现有向量库，重新处理所有文件'):
                with st.spinner('正在重建知识库...'):
                    docs_dir = os.path.join(project_root, 'knowledge', 'documents')
                    if knowledge_store.clear_collection() and os.path.isdir(docs_dir):
                        summary = knowledge_store.rebuild_from_directory(
                            docs_dir, 
                            patterns=['*.txt','*.md'], 
                            include_pdf=True, 
                            include_csv=True
                        )
                        st.success(f"🎉 重建完成！\n📊 chunks={summary['chunks_added']} | txt={summary['txt_files']} | pdf={summary['pdf_files']} | csv={summary['csv_files']}")
                        if summary.get('errors'):
                            st.error(f"⚠️ 处理错误: {len(summary['errors'])} 个")
                    else:
                        st.warning('目录不存在或清空失败')
        
        with col_kb2:
            if st.button('➕ 增量更新', help='仅处理新文件，添加到现有向量库'):
                with st.spinner('正在增量更新...'):
                    docs_dir = os.path.join(project_root, 'knowledge', 'documents')
                    if os.path.isdir(docs_dir):
                        summary = knowledge_store.add_new_files_only(
                            docs_dir, 
                            patterns=['*.txt','*.md'], 
                            include_pdf=True, 
                            include_csv=True
                        )
                        if summary['files_processed'] > 0:
                            st.success(f"📈 增量更新完成！\n新处理文件: {summary['files_processed']} | 新增chunks: {summary['chunks_added']} | 跳过已处理: {summary['skipped_files']}")
                        else:
                            st.info("💡 没有发现新文件，知识库保持不变")
                        if summary.get('errors'):
                            st.error(f"⚠️ 处理错误: {len(summary['errors'])} 个")
                    else:
                        st.warning('documents 目录不存在')
        
        with col_kb3:
            if st.button('🧹 清空', help='删除所有向量数据'):
                if st.session_state.get('confirm_clear'):
                    if knowledge_store.clear_collection():
                        st.success('✅ 已清空知识库')
                        st.session_state.confirm_clear = False
                else:
                    st.session_state.confirm_clear = True
                    st.warning('⚠️ 确认清空？请再次点击确认')
        
        # 检索测试
        with st.expander('🔍 检索测试', expanded=False):
            test_query = st.text_input('测试查询', placeholder='输入关键词测试检索效果')
            test_specialty = st.selectbox('专科上下文', ['(自动)','pulmonary','imaging','pathology','rheumatology','data_analysis','coordinator'])
            col_test1, col_test2 = st.columns(2)
            with col_test1:
                multi_flag = st.checkbox('Multi-Query', value=False)
                topk = st.slider('返回数量', 1, 10, 5)
            with col_test2:
                if st.button('🔍 执行检索', disabled=not test_query.strip()):
                    spec = '' if test_specialty == '(自动)' else (test_specialty or '')
                    if multi_flag:
                        case_info = {'symptoms': test_query.strip(), 'medical_history': ''}
                        context_preview = knowledge_store.multi_query_context(case_info, spec or 'pulmonary', n_queries=4, per_query_k=topk)
                        st.code(context_preview[:1500] or '无结果', language='markdown')
                    else:
                        results = knowledge_store.search_relevant_knowledge(test_query.strip(), spec, k=topk)
                        if not results:
                            st.info('📭 无检索结果')
                        else:
                            for i, r in enumerate(results, 1):
                                st.markdown(f"**#{i}** (相关度: {r.get('relevance_score'):.3f}) | 来源: `{r.get('source','未知')}`")
                                st.code(r.get('content','')[:400], language='text')
        st.markdown("---")
        st.subheader("🧩 Prompt 管理")
        if st.button("♻️ 热加载全部", use_container_width=True):
            _reload_all_prompts()
            st.success("Prompt 已热加载")
        # 友好标签 & 分类过滤
        col_pf, col_cat = st.columns([2,1])
        with col_pf:
            prompt_filter = st.text_input("按 ID 过滤 (前缀)", "")
        with col_cat:
            cat_filter = st.selectbox(
                "分类过滤",
                options=["(全部)", "系统提示", "主分析", "协调流程", "病理子任务", "风湿子任务", "数据子任务", "通用任务", "清单"],
                index=0
            )
        try:
            _all_prompts = _list_prompts()
            # 读取全部元数据并按 group 聚合
            from prompts.loader import get_prompt_meta as __pm
            group_map: dict[str, list[str]] = {}
            for pid in _all_prompts.keys():
                meta = __pm(pid) or {}
                g = meta.get('group', '未分组') or '未分组'
                group_map.setdefault(g, []).append(pid)
            keys_raw = sorted(_all_prompts.keys())
            def _visible(pid: str) -> bool:
                if prompt_filter and not pid.startswith(prompt_filter.upper()):
                    return False
                if cat_filter and cat_filter != "(全部)":
                    meta = _get_prompt_meta(pid)
                    if not meta or meta.get('category') != cat_filter:
                        return False
                return True
            keys = [k for k in keys_raw if _visible(k)]
            # 树形分组展示
            with st.expander("按智能体分组浏览 (Group → Prompts)", expanded=False):
                for g_name in sorted(group_map.keys()):
                    with st.container():
                        st.markdown(f"**📂 {g_name}**")
                        sub_cols = st.columns(2)
                        col_idx = 0
                        for pid in sorted(group_map[g_name]):
                            if pid not in keys:  # 过滤后不可见
                                continue
                            meta = _get_prompt_meta(pid) or {}
                            label = meta.get('label', pid)
                            short_desc = meta.get('description', '')[:40]
                            with sub_cols[col_idx % 2]:
                                if st.button(f"{label}\n{pid}", key=f"btn_{pid}", help=short_desc):
                                    st.session_state['__prompt_selected_pid'] = pid
                            col_idx += 1
                        st.markdown("---")
            # 回退：下拉快速定位 + 与按钮互通
            display_options = ["(选择以预览)"]
            id_map: dict[str, str | None] = {"(选择以预览)": None}
            for pid in keys:
                meta = _get_prompt_meta(pid) or {}
                label = meta.get('label', pid)
                display_text = f"{label} · {pid}"
                display_options.append(display_text)
                id_map[display_text] = pid
            selected_display = st.selectbox("快速选择", options=display_options, key="select_prompt_dropdown")
            selected_pid = (id_map.get(selected_display) if selected_display else None) or st.session_state.get('__prompt_selected_pid')
            if selected_pid:
                raw_text = _get_prompt(selected_pid)
                meta = _get_prompt_meta(selected_pid) or {}
                st.caption(f"文件: {_all_prompts[selected_pid]}")
                st.markdown(f"**名称:** {meta.get('label', selected_pid)}  ")
                if meta.get('description'):
                    st.markdown(f"**说明:** {meta['description']}")
                badge_cols = st.columns(3)
                with badge_cols[0]:
                    st.metric("分类", meta.get('category', '—'))
                with badge_cols[1]:
                    st.metric("角色", meta.get('role', '—'))
                with badge_cols[2]:
                    st.metric("ID", selected_pid)
                with st.expander("查看原始Markdown", expanded=False):
                    st.code(raw_text[:4000], language="markdown")
                # 占位符检测
                import re as _re
                ph = sorted(set(_re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", raw_text)))
                if ph:
                    st.write("占位符:", ", ".join(ph))
                # 演示安全格式化
                if st.checkbox("⚙️ 演示 safe_format", key=f"sf_{selected_pid}"):
                    demo_json = st.text_area("提供 JSON 格式数据 (可缺失)", value="{}", height=120)
                    try:
                        import json as _json
                        data_obj = _json.loads(demo_json or '{}')
                        formatted, missing = _safe_format(raw_text, **data_obj)
                        st.markdown("**格式化结果 (截断前 800 字):**")
                        st.code(formatted[:800], language="markdown")
                        if missing:
                            st.warning("缺失变量: " + ", ".join(missing))
                        else:
                            st.success("无缺失变量")
                    except Exception as _e:
                        st.error(f"解析/格式化失败: {_e}")
        except Exception as _e:
            st.warning(f"加载 Prompt 列表失败: {_e}")
    
    # 病例信息显示/输入
    if not st.session_state.get("start_stream", False):
        st.header("📝 病例信息录入")
        
        # 添加示例病例选择功能
        with st.expander("📁 示例病例选择", expanded=True):
            sample_cases = {
                "CTD-ILD": {
                    "file": "ctd_ild_case.json",
                    "description": "类风湿关节炎相关间质性肺病，UIP模式"
                },
                "IPF": {
                    "file": "ipf_case.json", 
                    "description": "特发性肺纤维化，典型UIP模式，快速进展"
                },
                "过敏性肺炎": {
                    "file": "hp_case.json",
                    "description": "慢性过敏性肺炎，鸽子暴露相关"
                },
                "机化性肺炎": {
                    "file": "op_case.json",
                    "description": "机化性肺炎，激素敏感型"
                },
                "肺癌": {
                    "file": "lung_cancer_case.json",
                    "description": "肺腺癌，分期和治疗决策"
                },
                "乳腺癌": {
                    "file": "breast_cancer_case.json", 
                    "description": "乳腺癌，多学科综合治疗"
                }
            }
            
            col_select, col_load = st.columns([3, 1])
            
            with col_select:
                selected_case = st.selectbox(
                    "选择示例病例类型",
                    options=list(sample_cases.keys()),
                    help="选择不同类型的病例进行测试"
                )
            
            with col_load:
                st.write("")  # 添加空行对齐
                if st.button(f"📁 加载", key="load_case"):
                    try:
                        if selected_case and selected_case in sample_cases:
                            case_file = sample_cases[selected_case]["file"]
                            case_path = os.path.join(project_root, "data", "sample_cases", case_file)
                            with open(case_path, 'r', encoding='utf-8') as f:
                                sample_case = json.load(f)
                            st.session_state.sample_case = sample_case
                            st.success(f"✅ {selected_case}示例病例已加载")
                            st.info(f"📝 {sample_cases[selected_case]['description']}")
                            st.rerun()
                        else:
                            st.error("请先选择一个病例")
                    except Exception as e:
                        st.error(f"加载示例病例失败: {e}")
            
            if selected_case and selected_case in sample_cases:
                st.markdown(f"**{selected_case}**: {sample_cases[selected_case]['description']}")
        
        # 病例信息表单 - 3行3列布局
        # 如果有加载的示例病例，使用其数据作为默认值，否则显示填写说明
        sample_data = st.session_state.get('sample_case', {})
        has_loaded_case = bool(sample_data)
        
        # 显示状态提示
        if not has_loaded_case:
            st.info("💡 **填写指导**：请填写患者的详细信息，或从上方加载示例病例。所有字段都提供了详细的填写说明。")
        else:
            st.success("✅ **已加载病例数据**：您可以修改以下信息或直接开始 MDT 讨论。")
        
        # 第一行
        col1_1, col1_2, col1_3 = st.columns(3)
        
        with col1_1:
            patient_id = st.text_input("患者ID", 
                value=sample_data.get("patient_id", ""),
                placeholder="请输入患者唯一标识码，如：ILD_001" if not has_loaded_case else "")
        
        with col1_2:
            chief_complaint = st.text_area("主要症状", 
                value=sample_data.get("chief_complaint", ""),
                placeholder="请描述患者主要症状，如：\n• 呼吸困难的性质和程度\n• 咳嗽特点（干咳/有痰）\n• 症状持续时间\n• 诱发或缓解因素" if not has_loaded_case else "",
                height=100)
        
        with col1_3:
            medical_history = st.text_area("既往史", 
                value=sample_data.get("medical_history", ""),
                placeholder="请详细记录患者既往病史，如：\n• 自身免疫性疾病史\n• 长期用药史\n• 职业暴露史\n• 家族史等" if not has_loaded_case else "",
                height=100)
        
        # 第二行
        col2_1, col2_2, col2_3 = st.columns(3)
        
        with col2_1:
            present_illness = st.text_area("现病史", 
                value=sample_data.get("symptoms", ""),
                placeholder="请描述现病史，如：\n• 起病时间和方式\n• 症状演变过程\n• 就诊经过\n• 治疗效果等" if not has_loaded_case else "",
                height=120)
        
        with col2_2:
            examination_results = st.text_area("检查结果", 
                value=sample_data.get("imaging_results", ""),
                placeholder="请填写影像学检查结果，如：\n• HRCT表现\n• X线胸片\n• 其他影像学检查\n• 典型征象描述" if not has_loaded_case else "",
                height=120)
        
        with col2_3:
            physical_examination = st.text_area("体格检查", 
                value=sample_data.get("physical_examination", ""),
                placeholder="请记录体格检查结果，如：\n• 胸部听诊所见\n• 呼吸音特点\n• 啰音分布\n• 其他阳性体征" if not has_loaded_case else "",
                height=120)
        
        # 第三行
        col3_1, col3_2, col3_3 = st.columns(3)
        
        with col3_1:
            lab_results = st.text_area("实验室检查", 
                value=sample_data.get("lab_results", ""),
                placeholder="请填写实验室检查结果，如：\n• 血常规\n• 生化指标\n• 炎症标志物\n• 免疫指标等" if not has_loaded_case else "",
                height=100)
        
        with col3_2:
            biomarker_results = st.text_area("生物标志物", 
                value=sample_data.get("biomarker_results", ""),
                placeholder="请填写生物标志物检测结果，如：\n• 自身抗体\n• ILD相关标志物\n• KL-6、SP-A、SP-D等\n• 其他特异性标志物" if not has_loaded_case else "",
                height=100)
        
        with col3_3:
            pulmonary_function_tests = st.text_area("肺功能检查", 
                value=sample_data.get("pulmonary_function_tests", ""),
                placeholder="请填写肺功能检查结果，如：\n• FVC、FEV1等指标\n• DLCO检测结果\n• 通气功能评估\n• 气体交换功能" if not has_loaded_case else "",
                height=100)
            
        # 保存病例数据到session state（包含所有字段）
        st.session_state.case_data = {
            "patient_id": patient_id,
            "chief_complaint": chief_complaint,
            "present_illness": present_illness,
            "medical_history": medical_history,
            "examination_results": examination_results,
            "physical_examination": physical_examination,
            "lab_results": lab_results,
            "biomarker_results": biomarker_results,
            "pulmonary_function_tests": pulmonary_function_tests,
            "timestamp": datetime.now().isoformat(),
            "full_case_data": sample_data  # 保存完整的病例数据
        }
    
    # 在MDT讨论时显示病例信息并执行MDT
    elif st.session_state.get("start_stream", False) and not st.session_state.get("stream_complete", False):
        display_case_summary()
        st.markdown("---")
        # 执行MDT讨论
        run_real_stream_mdt(selected_experts)
    
    # 显示完成状态
    elif st.session_state.get("stream_complete", False):
        display_case_summary()
        st.markdown("---")
        st.success("🎉 MDT讨论已完成！")
        
        # 显示完整的MDT结果（参考原应用的显示逻辑）
        if st.session_state.get("mdt_result"):
            display_mdt_results(st.session_state.mdt_result, st.session_state.get("case_data", {}))
        
        if st.button("🔄 开始新的讨论"):
            # 重置状态
            for key in ["start_stream", "stream_complete", "current_phase", "expert_containers", "mdt_result"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

def display_mdt_results(result: Dict[str, Any], case_data: Dict[str, Any]):
    """显示完整的MDT结果（参考原应用的显示逻辑）"""
    
    # 获取参与的专家列表
    selected_experts = result.get("participants", [])
    
    # 基本信息
    st.subheader("📄 会议基本信息")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("会议ID", result.get("session_id", "N/A"))
    with col2:
        st.metric("参与专家", len(selected_experts))
    with col3:
        st.metric("会议时长", result.get("duration", "N/A"))
    
    # 各阶段结果
    st.subheader("🔍 多轮MDT讨论结果")
    
    phases = result.get("phases", {})
    
    # 第1步：各专科独立分析
    if "individual_analysis" in phases:
        display_individual_analysis(phases["individual_analysis"], selected_experts)
    
    # 第2步：专科间初步讨论
    if "sharing_discussion" in phases:
        display_sharing_discussion(phases["sharing_discussion"], selected_experts)
    
    # 第3步：意见冲突检测
    if "conflict_detection" in phases:
        display_conflict_detection(phases["conflict_detection"])
    
    # 第4步：多轮讨论阶段
    if "multi_round_discussion" in phases:
        display_multi_round_discussion(phases["multi_round_discussion"], selected_experts)
    
    # 第5步：共识评估
    if "consensus_evaluation" in phases:
        display_consensus_evaluation(phases["consensus_evaluation"])
    
    # 第6步：最终协调建议
    if "final_coordination" in phases:
        display_final_coordination(phases["final_coordination"])
    
    # 下载结果
    display_download_section(result, case_data)

def display_individual_analysis(individual_data: Dict[str, Any], selected_experts: List[str]):
    """显示各专科独立分析"""
    st.markdown("### 🏥 各专科独立分析")
    st.markdown("每位专家基于病例信息进行独立分析，确保观点的客观性和多样性")
    
    # 过滤只显示选中的专家
    filtered_data = {}
    for key, value in individual_data.items():
        expert_found = False
        for expert_name in selected_experts:
            possible_keys = EXPERT_NAME_MAPPING.get(expert_name, [expert_name])
            if key in possible_keys or expert_name in key:
                filtered_data[key] = value
                expert_found = True
                break
        
        # 如果没有找到匹配，检查 agent 字段
        if not expert_found and isinstance(value, dict):
            agent_name = value.get('agent', '')
            for expert_name in selected_experts:
                if expert_name in agent_name or any(keyword in agent_name for keyword in EXPERT_NAME_MAPPING.get(expert_name, [])):
                    filtered_data[key] = value
                    break
    
    agent_list = list(filtered_data.items())

    # 响应式布局：每行2-3个卡片（保护空数据）
    num_agents = len(agent_list)
    if num_agents == 0:
        st.info("暂无可显示的专家独立分析。")
        st.markdown("---")
        return
    cols_per_row = min(3, num_agents)

    # 分批显示卡片
    for i in range(0, num_agents, cols_per_row):
        batch = agent_list[i:i + cols_per_row]
        cols = st.columns(len(batch))
        
        for j, (agent_name, response) in enumerate(batch):
            with cols[j]:
                display_expert_card(response, i + j, "individual")
    
    st.markdown("---")

def display_sharing_discussion(sharing_data: Dict[str, Any], selected_experts: List[str]):
    """显示专科间初步讨论"""
    st.markdown("### 🔄 专科间初步讨论")
    st.markdown("专家们查看彼此的意见后进行初步交流和补充")
    
    # 过滤只显示选中的专家
    filtered_data = {}
    for key, value in sharing_data.items():
        expert_found = False
        for expert_name in selected_experts:
            possible_keys = EXPERT_NAME_MAPPING.get(expert_name, [expert_name])
            if key in possible_keys or expert_name in key:
                filtered_data[key] = value
                expert_found = True
                break
        
        # 如果没有找到匹配，检查 agent 字段
        if not expert_found and isinstance(value, dict):
            agent_name = value.get('agent', '')
            for expert_name in selected_experts:
                if expert_name in agent_name or any(keyword in agent_name for keyword in EXPERT_NAME_MAPPING.get(expert_name, [])):
                    filtered_data[key] = value
                    break
    
    agent_list = list(filtered_data.items())

    # 响应式布局（保护空数据）
    num_agents = len(agent_list)
    if num_agents == 0:
        st.info("暂无可显示的专科间讨论内容。")
        st.markdown("---")
        return
    cols_per_row = min(3, num_agents)

    # 分批显示卡片
    for i in range(0, num_agents, cols_per_row):
        batch = agent_list[i:i + cols_per_row]
        cols = st.columns(len(batch))
        
        for j, (agent_name, response) in enumerate(batch):
            with cols[j]:
                display_expert_card(response, i + j, "sharing")
    
    st.markdown("---")

def display_conflict_detection(conflict_data: Dict[str, Any]):
    """显示意见冲突检测 (全宽专业卡片样式)"""
    st.markdown("""
    <div class="phase-wide-card">
        <h3 class="section-title">⚔️ 意见冲突检测</h3>
        <p class="sub-note">智能分析各专家意见中的分歧点，决定是否需要深入讨论</p>
    """, unsafe_allow_html=True)
    
    conflicts_detected = conflict_data.get("conflict_detected", False)
    
    # 创建大卡片
    conflict_color = "#ffebee" if conflicts_detected else "#e8f5e8"
    border_color = "#f44336" if conflicts_detected else "#4caf50"
    icon = "🔴" if conflicts_detected else "🟢"
    status_text = "检测到专家意见存在显著分歧" if conflicts_detected else "专家意见基本一致，无显著冲突"
    
    st.markdown(f"""
    <div style="
        background: {conflict_color};
        border: 2px solid {border_color};
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    ">
        <div style="text-align: center; margin-bottom: 15px;">
            <h3 style="margin: 0; color: {border_color};">{icon} 冲突检测结果</h3>
            <p style="margin: 5px 0; font-size: 16px; color: #333;">{status_text}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 分析详情
    if "conflict_analysis" in conflict_data:
        analysis = conflict_data["conflict_analysis"]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            with st.expander("查看详细分析", expanded=False):
                st.write("**冲突分析详情：**")
                if isinstance(analysis, str):
                    rendered_analysis = render_markdown_content(analysis)
                    st.markdown(rendered_analysis, unsafe_allow_html=True)
                elif isinstance(analysis, dict):
                    analysis_text = analysis.get('response', '无分析结果')
                    rendered_analysis = render_markdown_content(analysis_text)
                    st.markdown(rendered_analysis, unsafe_allow_html=True)
                else:
                    st.write('无分析结果')
        
        with col2:
            consensus_score = conflict_data.get('consensus_score', 0.0)
            st.metric(
                "初步共识度", 
                f"{consensus_score:.2f}",
                delta=f"{consensus_score - 0.5:.2f}" if consensus_score != 0.5 else None,
                help="基于专家意见一致性计算的共识度分数"
            )
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")

def display_multi_round_discussion(multi_round_data: Dict[str, Any], selected_experts: List[str]):
    """显示多轮深入讨论"""
    total_rounds = multi_round_data.get("total_rounds", 0)
    
    if total_rounds > 0:
        st.markdown(f"""
        <div class=\"phase-wide-card\">
            <h3 class=\"section-title\">💬 多轮深入讨论</h3>
            <p class=\"sub-note\">经过冲突检测，专家们进行了 <strong>{total_rounds}轮</strong> 深入讨论以寻求共识</p>
        """, unsafe_allow_html=True)
        
        rounds = multi_round_data.get("rounds", [])
        
        # 创建轮次选择器
        round_tabs = st.tabs([f"第{i+1}轮讨论" for i in range(total_rounds)])
        
        for i, round_data in enumerate(rounds):
            with round_tabs[i]:
                round_num = round_data.get("round", i+1)
                round_consensus = round_data.get("consensus_score", 0.0)
                
                # 轮次概要
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"#### 第 {round_num} 轮讨论结果")
                with col2:
                    consensus_color = "#4caf50" if round_consensus > 0.7 else "#ff9800" if round_consensus > 0.5 else "#f44336"
                    st.markdown(f"""
                    <div style="
                        background: {consensus_color};
                        color: white;
                        padding: 10px;
                        border-radius: 10px;
                        text-align: center;
                    ">
                        <strong>共识度: {round_consensus:.2f}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                
                # 专家卡片 - 过滤只显示选中的专家
                round_results = round_data.get("results", {})
                
                # 过滤数据
                filtered_round_results = {}
                for key, value in round_results.items():
                    expert_found = False
                    for expert_name in selected_experts:
                        possible_keys = EXPERT_NAME_MAPPING.get(expert_name, [expert_name])
                        if key in possible_keys or expert_name in key:
                            filtered_round_results[key] = value
                            expert_found = True
                            break
                    # 如果没有找到匹配，检查 agent 字段
                    if not expert_found and isinstance(value, dict):
                        agent_name = value.get('agent', '')
                        for expert_name in selected_experts:
                            if expert_name in agent_name or any(keyword in agent_name for keyword in EXPERT_NAME_MAPPING.get(expert_name, [])):
                                filtered_round_results[key] = value
                                break

                agent_list = list(filtered_round_results.items())

                # 响应式布局（保护空数据）
                num_agents = len(agent_list)
                if num_agents == 0:
                    st.info("该轮暂无匹配的专家发言。")
                    continue
                cols_per_row = min(3, num_agents)

                # 分批显示卡片
                for k in range(0, num_agents, cols_per_row):
                    batch = agent_list[k:k + cols_per_row]
                    cols = st.columns(len(batch))
                    
                    for l, (agent_name, response) in enumerate(batch):
                        with cols[l]:
                            display_expert_card(response, k + l, f"round_{round_num}", round_num)
    else:
        st.markdown("### ✅ 专家意见一致")
        st.info("🎉 专家们的初步意见已经非常一致，无需进行多轮深入讨论")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")

def display_consensus_evaluation(consensus_data: Dict[str, Any]):
    """显示共识评估 (全宽专业卡片样式)"""
    st.markdown("""
    <div class="phase-wide-card">
        <h3 class="section-title">📊 共识评估</h3>
        <p class="sub-note">对专家讨论的最终结果进行共识程度评估</p>
    """, unsafe_allow_html=True)
    
    consensus_reached = consensus_data.get("consensus_reached", False)
    consensus_score = consensus_data.get("consensus_score", 0.0)
    threshold = consensus_data.get("threshold", 0.75)
    
    # 创建共识评估卡片
    consensus_color = "#e8f5e8" if consensus_reached else "#fff8e1"
    border_color = "#4caf50" if consensus_reached else "#ffb300"
    icon = "✅" if consensus_reached else "⚠️"
    status_text = "专家已达成共识" if consensus_reached else "仍需进一步协调"

    st.markdown(f"""
    <div style="
        background: {consensus_color};
        border: 2px solid {border_color};
        border-radius: 16px;
        padding: 22px 26px 18px 26px;
        margin: 18px 0 10px 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
    ">
        <h3 style="margin: 0 0 8px 0; color: {border_color}; text-align:center;">{icon} 共识评估结果</h3>
        <p style="margin: 0 0 12px 0; font-size: 16px; color: #333; text-align:center;">{status_text}</p>
    </div>
    """, unsafe_allow_html=True)

    # 指标区
    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        st.metric("最终共识度", f"{consensus_score:.2f}")
    with mcol2:
        st.metric("共识阈值", f"{threshold:.2f}")
    with mcol3:
        gap = consensus_score - threshold
        st.metric("高于阈值" if gap >= 0 else "低于阈值", f"{gap:+.2f}")
    
    # 进度条表示程度
    pct = min(max(consensus_score / max(threshold, 1e-6), 0), 1.5)
    st.progress(min(pct, 1.0))
    
    # 评估详情
    detail_block = None
    if "evaluation" in consensus_data:
        detail_block = consensus_data["evaluation"]
    elif "evaluation_details" in consensus_data:
        detail_block = {"response": consensus_data["evaluation_details"]}

    if detail_block:
        with st.expander("查看详细评估", expanded=False):
            st.write("**共识评估详情：**")
            if isinstance(detail_block, dict):
                st.write(detail_block.get('response', '无评估结果'))
            else:
                st.write(str(detail_block))
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")

def display_final_coordination(coordination_result: Dict[str, Any]):
    """显示最终MDT协调建议 (全宽专业卡片样式)"""
    st.markdown("""
    <div class="phase-wide-card">
        <h3 class="section-title">🎯 最终MDT协调建议</h3>
        <p class="sub-note">基于整个讨论过程，MDT协调员生成的综合临床建议</p>
    """, unsafe_allow_html=True)
    
    # 获取关键指标
    final_consensus = coordination_result.get('consensus_score', 0.0)
    discussion_rounds = coordination_result.get('discussion_rounds', 0)
    consensus_reached = coordination_result.get('consensus_reached', False)
    
    # 状态指示条
    status_color = "#4caf50" if consensus_reached else "#ff9800"
    status_icon = "✅" if consensus_reached else "⚠️"
    status_text = "已达成专家共识" if consensus_reached else "存在一定分歧"
    
    # 关键指标展示
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        ">
            <h2 style="margin: 0;">{final_consensus:.2f}</h2>
            <p style="margin: 5px 0;">最终共识度</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        ">
            <h2 style="margin: 0;">{discussion_rounds}</h2>
            <p style="margin: 5px 0;">讨论轮数</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="
            background: {status_color};
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        ">
            <h2 style="margin: 0;">{status_icon}</h2>
            <p style="margin: 5px 0;">{status_text}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # 最终建议内容
    st.markdown("#### 📋 协调员综合建议")
    
    response_text = coordination_result.get('response', '无响应')
    agent_name = coordination_result.get('agent', 'MDT协调员')
    
    # 使用美观的容器展示建议内容
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 3px;
        border-radius: 15px;
        margin: 10px 0;
    ">
        <div style="
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        ">
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 10px 20px;
                border-radius: 10px;
                text-align: center;
                margin-bottom: 20px;
            ">
                <h4 style="margin: 0;">{agent_name}</h4>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 在HTML下方紧接着用Markdown渲染实际内容
    rendered_response = render_markdown_content(response_text)
    st.markdown(rendered_response, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")

def display_expert_card(response: Dict[str, Any], color_index: int, card_type: str, round_num: Optional[int] = None):
    """显示专家卡片"""
    agent_display_name = response.get('agent', 'Unknown Expert')
    specialty = response.get('specialty', '专科医生')
    
    # 生成不同的颜色
    if card_type == "individual":
        colors = ["#667eea", "#f093fb", "#4facfe", "#43e97b", "#fa709a", "#a8edea", "#ff9a9e"]
    elif card_type == "sharing":
        colors = ["#f093fb", "#4facfe", "#43e97b", "#fa709a", "#a8edea", "#ff9a9e", "#667eea"]
    else:  # multi-round
        colors = ["#9c27b0", "#3f51b5", "#009688", "#ff5722", "#795548", "#607d8b", "#e91e63"]
    
    color = colors[color_index % len(colors)]
    
    # 创建卡片 
    response_text = response.get('response', '无响应')
    timestamp = response.get('timestamp', '')
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime('%H:%M:%S')
        except:
            formatted_time = timestamp
    else:
        formatted_time = 'N/A'
    
    # 转义HTML特殊字符
    import html
    import re
    cleaned_response = re.sub(r"<\/?(script|iframe|style)[^>]*>", "", response_text, flags=re.IGNORECASE)
    safe_name = html.escape(agent_display_name)
    safe_specialty = html.escape(specialty)
    
    # 规范化多余空行
    cleaned_response = re.sub(r"\n{3,}", "\n\n", cleaned_response).strip()
    
    # 创建卡片头部
    st.markdown(f"""
    <div style="
        background: white;
        border-radius: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        overflow: hidden;
        border: 1px solid #e0e0e0;
    ">
        <div style="background: {color}; color: white; padding: 15px; text-align: center;">
            <h4 style="margin: 0; color: white; font-size: 16px;">{safe_name}</h4>
            <p style="margin: 5px 0 0 0; color: rgba(255,255,255,0.9); font-size: 12px;">{safe_specialty}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 在卡片下方紧接着添加白色背景的内容区域
    with st.container():
        # 使用简化的容器，避免样式冲突
        rendered_content = render_markdown_content(cleaned_response)
        
        # 创建完整的卡片内容区域
        st.markdown(f"""
        <div style="
            background: white;
            padding: 20px;
            margin-top: -20px;
            margin-bottom: 20px;
            border-radius: 0 0 15px 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: 1px solid #e0e0e0;
            border-top: none;
        ">
                <div class="card-scroll">{rendered_content}</div>
            <div style="border-top:1px solid #eee; padding-top:10px; margin-top:15px;">
                <small style="color:#666;">时间: {formatted_time}</small>
            </div>
        </div>
        """, unsafe_allow_html=True)

def display_download_section(result: Dict[str, Any], case_data: Dict[str, Any]):
    """显示下载结果部分"""
    st.subheader("💾 导出结果")
    
    # 准备下载数据
    download_data = json.dumps(result, ensure_ascii=False, indent=2)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 下载完整结果(JSON)",
            data=download_data,
            file_name=f"mdt_result_{result.get('session_id', 'unknown')}.json",
            mime="application/json"
        )
    
    with col2:
        # 生成简化报告
        phases = result.get("phases", {})
        if "final_coordination" in phases:
            final_recommendation = phases["final_coordination"].get('response', '')
            st.download_button(
                label="📋 下载MDT报告(TXT)",
                data=f"""MDT讨论报告
=================
版本: 1.0
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

一、基本信息
--------------------------------
患者ID        : {case_data.get('patient_id', 'N/A')}
讨论开始时间  : {result.get('start_time', 'N/A')}
参与专家（{len(result.get('participants', []))}人）: {', '.join(result.get('participants', []))}

二、最终综合建议
--------------------------------
{final_recommendation}

三、阶段性摘要（提取）
--------------------------------
1. 冲突检测结果: {result.get('phases', {}).get('conflict_detection', {}).get('conflict_analysis','N/A') if isinstance(result.get('phases', {}).get('conflict_detection', {}), dict) else 'N/A'}
2. 共识评估: 共识度 {result.get('phases', {}).get('consensus_evaluation', {}).get('consensus_score','N/A')} 阈值 {result.get('phases', {}).get('consensus_evaluation', {}).get('threshold','N/A')}
3. 讨论轮数: {result.get('phases', {}).get('multi_round_discussion', {}).get('total_rounds','0')}

四、技术元数据
--------------------------------
会话ID        : {result.get('session_id','N/A')}
总时长        : {result.get('duration','N/A')}
工具版本      : MDT Orchestrator v1

（本报告为自动生成，供临床参考，不替代临床医师最终判断。）
""",
                file_name=f"mdt_report_{result.get('session_id', 'unknown')}.txt",
                mime="text/plain"
            )

# run_stream_mdt 包装函数已移除，直接调用 run_real_stream_mdt

def run_real_stream_mdt(selected_experts: List[str]):
    """运行MDT讨论（使用AI模型） - 含动态流程与协作图"""
    st.info("🤖 正在进行MDT多学科讨论")

    try:
        orchestrator = MDTOrchestrator()
        st.session_state['active_orchestrator'] = orchestrator  # 保存引用供 RAG 片段展示
        case_data = st.session_state.get("case_data", {})
        full_case_data = case_data.get("full_case_data", {})
        if full_case_data:
            merged_case_data = {**full_case_data, **case_data}
            merged_case_data.pop("full_case_data", None)
            case_data = merged_case_data

        current_containers: Dict[str, Any] = {}
        phase_container = None
        created_in_phase = 0
        cols_current_row: List[Any] = []

        progress_bar = st.progress(0)
        metrics_container = st.empty()
        phase_progress_map = {
            "initialization": 0.02,
            "individual_analysis": 0.18,
            "sharing_discussion": 0.35,
            "conflict_detection": 0.50,
            "multi_round_discussion": 0.70,
            "consensus_evaluation": 0.85,
            "final_coordination": 0.95,
            "completed": 1.0
        }

        collected_result = {
            "session_id": f"MDT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "participants": selected_experts,
            "start_time": datetime.now().isoformat(),
            "phases": {}
        }

        flow_placeholder = st.empty()
        interaction_placeholder = st.empty()
        flow_steps_order = [
            ("individual_analysis", "独立分析", "专家独立初评"),
            ("sharing_discussion", "初步讨论", "观点共享"),
            ("conflict_detection", "冲突检测", "识别差异"),
            ("multi_round_discussion", "多轮讨论", "迭代求同"),
            ("consensus_evaluation", "共识评估", "量化一致性"),
            ("final_coordination", "最终协调", "综合建议")
        ]
        flow_state = {k: {"status": "pending", "agents": set(), "rounds": 0, "metrics": {}} for k,_,_ in flow_steps_order}

        interaction_nodes: List[str] = []
        interaction_edges: Dict[tuple, int] = {}
        last_speaker: Optional[str] = None
        coordinator_names = [n for n in EXPERT_NAME_MAPPING if '协调员' in n]

        def ensure_node(name: str):
            if name not in interaction_nodes:
                interaction_nodes.append(name)

        def add_edge(src: str, dst: str):
            if not src or not dst or src == dst:
                return
            key = (src, dst)
            interaction_edges[key] = interaction_edges.get(key, 0) + 1

        def build_interaction_svg() -> str:
            if not interaction_nodes:
                return ""
            import math
            n = len(interaction_nodes)
            cx, cy = 300, 300
            radius = 210 if n <= 8 else 260
            positions = {}
            for i, node in enumerate(interaction_nodes):
                angle = 2 * math.pi * i / n - math.pi/2
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                positions[node] = (x, y)
            max_w = max(interaction_edges.values()) if interaction_edges else 1
            svg_parts = ["<svg viewBox='0 0 600 600' width='100%' height='420' class='mdt-graph-svg' style='background:linear-gradient(145deg,#ffffff,#f5f7fb);border:1px solid #e1e5ec;border-radius:18px;'>"]
            svg_parts.append("<defs><marker id='arrow' markerWidth='10' markerHeight='10' refX='10' refY='5' orient='auto' markerUnits='strokeWidth'><path d='M0,0 L10,5 L0,10 z' fill='#556' /></marker></defs>")
            for (src, dst), cnt in interaction_edges.items():
                x1,y1 = positions.get(src, (0,0))
                x2,y2 = positions.get(dst, (0,0))
                width = 1.5 + 4.5 * (cnt / max_w)
                opacity = 0.35 + 0.55 * (cnt / max_w)
                svg_parts.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#667eea' stroke-width='{width:.2f}' stroke-linecap='round' opacity='{opacity:.2f}' marker-end='url(#arrow)' />")
            for node,(x,y) in positions.items():
                color = get_expert_color(node)
                abbrev = node.replace('专家','').replace('医生','').replace('MDT','')[:4]
                svg_parts.append(f"<g><circle cx='{x}' cy='{y}' r='34' fill='{color}' stroke='white' stroke-width='3' opacity='0.92' />")
                svg_parts.append(f"<text x='{x}' y='{y+4}' font-size='13' fill='white' text-anchor='middle' font-weight='600' style='font-family:-apple-system,BlinkMacSystemFont,Roboto,Arial;'>{abbrev}</text></g>")
            svg_parts.append("</svg>")
            legend = "<div style='margin-top:6px;font-size:12px;color:#566176;'>箭头表示信息/参考方向；线条越粗表示该方向互动次数越多。</div>"
            return "<div class='mdt-flow-wrapper' style='padding:14px 20px;'>" \
                   + "<h4 style='margin:4px 0 12px 4px;font-weight:700;font-size:16px;color:#2d3e50;'>🤝 智能体协作互动图 (实时)</h4>" \
                   + ''.join(svg_parts) + legend + "</div>"

        def render_interaction():
            interaction_placeholder.markdown(build_interaction_svg(), unsafe_allow_html=True)

        def render_flow():
            html_blocks = ["<div class='mdt-flow-wrapper'><div class='mdt-flow-steps'>"]
            for idx,(key,title,desc) in enumerate(flow_steps_order, start=1):
                st_info = flow_state[key]
                status = st_info["status"]
                norm_agents = []
                for a in st_info["agents"]:
                    na = a.replace('专家','').replace('MDT','').replace('医生','').strip() or a
                    norm_agents.append(na)
                agents_preview = ", ".join(list(norm_agents)[:3])
                rounds_txt = f"轮次: {st_info['rounds']}" if st_info['rounds'] else ""
                metrics_html = ""
                if st_info["metrics"]:
                    badges = []
                    for mk, mv in st_info["metrics"].items():
                        if mv is None: continue
                        if isinstance(mv, float):
                            mv_fmt = f"{mv:.2f}" if abs(mv) < 1000 else f"{mv:.1e}"
                        else:
                            mv_fmt = str(mv)
                        badges.append(f"<span class='mdt-flow-badge'>{mk}:{mv_fmt}</span>")
                    if badges:
                        metrics_html = f"<div class='mdt-flow-metrics'>{''.join(badges)}</div>"
                agents_html = f"<div class='mdt-flow-active-agents'>{agents_preview}{'…' if len(st_info['agents'])>3 else ''}</div>" if agents_preview else ""
                rounds_html = f"<div class='mdt-flow-rounds'>{rounds_txt}</div>" if rounds_txt else ""
                html_blocks.append(
                    f"<div class='mdt-flow-step {status}'>"
                    f"<div class='mdt-flow-circle {status}'>{idx}</div>"
                    f"<p class='mdt-flow-title'>{title}</p>"
                    f"<p class='mdt-flow-desc'>{desc}</p>"
                    f"{rounds_html}{agents_html}{metrics_html}"
                    f"</div>"
                )
            html_blocks.append("</div></div>")
            flow_placeholder.markdown("".join(html_blocks), unsafe_allow_html=True)

        # 初次显示
        render_flow(); render_interaction()

        for stream_result in orchestrator.conduct_mdt_session_stream(case_data, selected_experts):
            rtype = stream_result.get("type")
            phase = stream_result.get("phase")

            if rtype == "phase_start":
                st.markdown("---")
                phase_desc = {
                    "individual_analysis": "各专科独立分析",
                    "sharing_discussion": "专科间初步讨论",
                    "conflict_detection": "意见冲突检测",
                    "multi_round_discussion": "多轮深入讨论",
                    "consensus_evaluation": "共识评估",
                    "final_coordination": "最终协调建议"
                }
                phase_name = phase or "未知阶段"
                render_phase_header(phase_desc.get(phase_name, phase_name), stream_result.get("message", ""))
                current_containers = {}
                phase_container = st.container()
                created_in_phase = 0
                cols_current_row = []
                progress_bar.progress(phase_progress_map.get(phase_name, 0.0))
                for k in flow_state:
                    if flow_state[k]["status"] == "current":
                        flow_state[k]["status"] = "done"
                if phase_name in flow_state:
                    flow_state[phase_name]["status"] = "current"
                render_flow()
                last_speaker = None

            elif rtype == "agent_start":
                expert_name = stream_result.get("agent", "专家")
                if not is_expert_selected(expert_name, selected_experts):
                    continue
                if expert_name not in current_containers:
                    if created_in_phase % 3 == 0:
                        if phase_container is None:
                            phase_container = st.container()
                        cols_current_row = phase_container.columns(3)
                    target_col = cols_current_row[created_in_phase % 3]
                    current_containers[expert_name] = target_col.empty()
                    created_in_phase += 1
                display_expert_response(current_containers[expert_name], expert_name, "", "thinking")
            elif rtype == "agent_chunk":
                expert_name = stream_result.get("agent", "专家")
                if not is_expert_selected(expert_name, selected_experts):
                    continue
                full_response = stream_result.get("full_response") or ""
                if expert_name not in current_containers:
                    if created_in_phase % 3 == 0:
                        if phase_container is None:
                            phase_container = st.container()
                        cols_current_row = phase_container.columns(3)
                    target_col = cols_current_row[created_in_phase % 3]
                    current_containers[expert_name] = target_col.empty()
                    created_in_phase += 1
                display_expert_response(current_containers[expert_name], expert_name, full_response, "typing")
                display_expert_response(current_containers[expert_name], expert_name, full_response, "typing")

            elif rtype == "phase_complete":
                phase_name = stream_result.get("phase")
                phase_result = stream_result.get("result", {})
                if phase_name:
                    collected_result["phases"][phase_name] = phase_result
                if phase_name in flow_state:
                    flow_state[phase_name]["status"] = "done"
                    metrics_capture = {}
                    if phase_name == "conflict_detection":
                        metrics_capture = {"共识": phase_result.get("consensus_score"), "冲突": "是" if phase_result.get("conflict_detected") else "否"}
                    elif phase_name == "consensus_evaluation":
                        metrics_capture = {"最终共识": phase_result.get("consensus_score"), "阈值": phase_result.get("threshold")}
                    elif phase_name == "multi_round_discussion":
                        metrics_capture = {"轮数": phase_result.get("total_rounds")}
                    flow_state[phase_name]["metrics"] = metrics_capture
                    if phase_name == "multi_round_discussion":
                        flow_state[phase_name]["rounds"] = phase_result.get("total_rounds", 0)
                render_flow()
                if phase_name == "conflict_detection":
                    consensus_score = phase_result.get("consensus_score", 0.0)
                    conflicts = phase_result.get("conflict_detected", False)
                    with metrics_container.container():
                        c1, c2 = st.columns(2)
                        with c1: st.metric("初步共识度", f"{consensus_score:.2f}")
                        with c2: st.metric("是否存在冲突", "是" if conflicts else "否")
                elif phase_name == "consensus_evaluation":
                    consensus_score = phase_result.get("consensus_score", 0.0)
                    threshold = phase_result.get("threshold", 0.75)
                    gap = consensus_score - threshold
                    with metrics_container.container():
                        c1, c2, c3 = st.columns(3)
                        with c1: st.metric("最终共识度", f"{consensus_score:.2f}")
                        with c2: st.metric("共识阈值", f"{threshold:.2f}")
                        with c3: st.metric("高于阈值" if gap >= 0 else "低于阈值", f"{gap:+.2f}")
                if phase_name in ("conflict_detection", "consensus_evaluation", "final_coordination"):
                    coord_nodes = [n for n in interaction_nodes if any(cn in n for cn in coordinator_names)]
                    if coord_nodes:
                        coord = coord_nodes[0]
                        for n in interaction_nodes:
                            if n != coord:
                                add_edge(n, coord)
                        render_interaction()

            elif rtype == "agent_complete":
                expert_name = stream_result.get("agent", "专家")
                if not is_expert_selected(expert_name, selected_experts):
                    continue
                full_response = stream_result.get("result", {}).get("response", "")
                if expert_name not in current_containers:
                    if created_in_phase % 3 == 0:
                        if phase_container is None:
                            phase_container = st.container()
                        cols_current_row = phase_container.columns(3)
                    target_col = cols_current_row[created_in_phase % 3]
                    current_containers[expert_name] = target_col.empty()
                    created_in_phase += 1
                display_expert_response(current_containers[expert_name], expert_name, full_response, "complete")
                ensure_node(expert_name)
                last_speaker = expert_name
                render_interaction()

            elif rtype == "session_complete":
                st.success("🎉 MDT讨论完成！")
                progress_bar.progress(1.0)
                for k in flow_state:
                    if flow_state[k]["status"] == "current":
                        flow_state[k]["status"] = "done"
                render_flow(); render_interaction()
                final_result = stream_result.get("result", {})
                if final_result:
                    collected_result.update(final_result)
                # 统一展示所有专家的 RAG 片段预览（汇总至底部）
                orch = st.session_state.get('active_orchestrator')
                if orch and hasattr(orch, 'agents'):
                    name_map = {
                        'pulmonary':'呼吸科专家','imaging':'影像科专家','pathology':'病理科专家',
                        'rheumatology':'风湿免疫科专家','data_analysis':'数据分析专家','coordinator':'协调员'
                    }
                    rag_any = False
                    rag_container = st.container()
                    with rag_container:
                        with st.expander('🔎 RAG片段(预览) - 全部专家汇总', expanded=False):
                            for key, agent in orch.agents.items():
                                chunks = getattr(agent, 'last_retrieved_chunks', []) or []
                                if chunks:
                                    rag_any = True
                                    st.markdown(f"### {name_map.get(key, key)}")
                                    for idx, chunk in enumerate(chunks[:5], 1):
                                        # 兼容字符串旧格式与新结构化字典
                                        if isinstance(chunk, dict):
                                            src = chunk.get('source','未知')
                                            score = chunk.get('score')
                                            content = chunk.get('raw') or chunk.get('content','')
                                            meta = f"来源: {src}"
                                            if score is not None:
                                                meta += f" | 相关度: {score:.4f}" if isinstance(score,(int,float)) else ""
                                            st.markdown(f"**#{idx}** {meta}")
                                            st.code(content[:800], language='markdown')
                                        else:
                                            st.markdown(f"**#{idx}**")
                                            st.code(str(chunk)[:600], language='markdown')
                            if not rag_any:
                                st.info('当前会话未检索到任何RAG片段。')
                end_time = datetime.now()
                collected_result["end_time"] = end_time.isoformat()
                start_time = datetime.fromisoformat(collected_result["start_time"])
                duration = end_time - start_time
                collected_result["duration"] = f"{int(duration.total_seconds()//60)}分{int(duration.total_seconds()%60)}秒"
                st.session_state.mdt_result = collected_result
                st.session_state.stream_complete = True
                break

            elif rtype == "session_error":
                st.error(f"❌ 讨论过程出现错误：{stream_result.get('message', '未知错误')}")
                st.session_state.stream_complete = True
                break

    except Exception as e:
        st.error(f"❌ MDT讨论执行失败：{e}")
        logger.error(f"Stream MDT error: {e}")
        st.session_state.stream_complete = True

if __name__ == "__main__":
    main()
