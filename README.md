环境:在browser-use的基础上安装autostudio
# 环境配置
uv venv --python 3.11
./venv/Scripts/activate
uv pip install -r requirements.txt
playwright install
pip install autogen
pip install autostudio
copy .env.example .env

## 运行
./venv/Scripts/activate
autogenstudio ui --port 8081
