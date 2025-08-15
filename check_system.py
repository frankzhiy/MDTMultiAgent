#!/usr/bin/env python3
"""多智能体MDT系统配置检查"""

import os
from utils.config import config

def check_system_configuration():
    """检查系统配置"""
    print("🔍 多智能体MDT系统配置检查")
    print("=" * 50)
    
    # 检查环境变量
    print("\n📋 环境变量配置:")
    print(f"  • OPENAI_API_KEY: {'✅ 已设置' if config.OPENAI_API_KEY and config.OPENAI_API_KEY != 'your_openai_api_key_here' else '❌ 需要设置真实的API密钥'}")
    print(f"  • OPENAI_BASE_URL: {config.OPENAI_BASE_URL}")
    print(f"  • OPENAI_MODEL: {config.OPENAI_MODEL}")
    print(f"  • OPENAI_TEMPERATURE: {config.OPENAI_TEMPERATURE}")
    
    # 检查目录结构
    print("\n📁 目录结构:")
    required_dirs = [
        "agents",
        "knowledge",
        "mdt_system", 
        "prompts",
        "utils",
        "app",
        "data",
        "tests"
    ]
    
    for dir_name in required_dirs:
        exists = os.path.exists(dir_name)
        print(f"  • {dir_name}/: {'✅' if exists else '❌'}")
    
    # 检查关键文件
    print("\n📄 关键文件:")
    required_files = [
        "agents/base_agent.py",
        "agents/coordinator_agent.py",
        "agents/pulmonary_agent.py",
        "agents/imaging_agent.py",
        "agents/pathology_agent.py",
        "agents/rheumatology_agent.py",
        "agents/data_analysis_agent.py",
        "knowledge/vector_store.py",
        "mdt_system/orchestrator.py",
        "app/streamlit_app_stream.py",
        "utils/config.py",
        "requirements.txt",
        ".env"
    ]
    
    for file_name in required_files:
        exists = os.path.exists(file_name)
        print(f"  • {file_name}: {'✅' if exists else '❌'}")
    
    # 系统状态总结
    print("\n🚀 系统状态:")
    if config.OPENAI_API_KEY and config.OPENAI_API_KEY != 'your_openai_api_key_here':
        print("  ✅ 系统已准备就绪，可以启动MDT智能体系统")
        print("\n启动命令:")
        print("  streamlit run app/streamlit_app_stream.py")
    else:
        print("  ⚠️  需要在.env文件中设置真实的OPENAI_API_KEY")
        print("  📝 编辑.env文件，将OPENAI_API_KEY设置为您的真实API密钥")

if __name__ == "__main__":
    check_system_configuration()
