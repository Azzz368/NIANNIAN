# backend/services/__init__.py
# 通过 sys.path 复用根目录下的现有模块（llm_client、skill_loader 等）
# 这样 Streamlit (app.py) 和 FastAPI (backend/main.py) 共享同一份业务代码
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # 项目根
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 暴露常用对象，供 service_manager 引用
ROOT_DIR = _ROOT
