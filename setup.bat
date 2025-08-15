@echo off
REM 多智能体MDT系统 - Windows快速启动脚本

echo 🏥 多智能体MDT系统 - 安装向导
echo ========================================

REM 检查Python版本
echo 🔍 检查Python版本...
python --version
if %errorlevel% neq 0 (
    echo ❌ 请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

REM 检查是否存在虚拟环境
if not exist "venv" (
    echo 📦 创建Python虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo 🔄 激活虚拟环境...
call venv\Scripts\activate.bat

REM 升级pip
echo ⬆️ 升级pip...
pip install --upgrade pip

REM 安装依赖
echo 📥 安装项目依赖...
pip install -r requirements.txt

REM 检查.env文件
if not exist ".env" (
    echo ⚙️ 创建环境配置文件...
    copy .env.example .env
    echo.
    echo 📝 请编辑 .env 文件，添加您的OpenAI API密钥：
    echo    OPENAI_API_KEY=your_api_key_here
    echo.
    pause
)

REM 创建必要的目录
echo 📁 创建数据目录...
mkdir data\chroma_db 2>nul
mkdir data\sessions 2>nul

echo.
echo ✅ 安装完成！
echo.
echo 🚀 运行方式：
echo    1. 命令行版本: python main.py
echo    2. Web界面版本: streamlit run app/streamlit_app_stream.py
echo.
echo 📚 使用前请确保：
echo    1. 已在.env文件中配置OpenAI API密钥
echo    2. 网络连接正常，可访问OpenAI API
echo.
pause
