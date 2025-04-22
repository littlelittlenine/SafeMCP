# 注意代码
from typing import Any, Dict, List, Tuple
import logging
import time
from dotenv import load_dotenv
from environment import webshop_env_server
from model import *
from utils import debug_flg
from mcp.server.fastmcp import FastMCP
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent  # 根据实际结构调整
sys.path.append(str(project_root))
# 加载环境变量
load_dotenv()

# 初始化 MCP 服务器
mcp = FastMCP("webshop")

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# 速率限制配置
RATE_LIMIT = {
    "per_second": 5,
    "per_minute": 60
}

request_count = {
    "second": 0,
    "minute": 0,
    "last_reset": time.time(),
    "last_minute_reset": time.time()
}

def check_rate_limit():
    """检查并更新速率限制"""
    now = time.time()
    
    # 重置秒级计数器
    if now - request_count["last_reset"] > 1:
        request_count["second"] = 0
        request_count["last_reset"] = now
        
    # 重置分钟级计数器
    if now - request_count["last_minute_reset"] > 60:
        request_count["minute"] = 0
        request_count["last_minute_reset"] = now
    
    if (request_count["second"] >= RATE_LIMIT["per_second"] or 
        request_count["minute"] >= RATE_LIMIT["per_minute"]):
        raise Exception("超出速率限制")
    
    request_count["second"] += 1
    request_count["minute"] += 1

@mcp.tool()
async def create_env() -> int:
    """创建一个新的WebShop环境"""
    try:
        check_rate_limit()
        env = webshop_env_server.create()
        return env
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def step_action(env_idx: int, action: str) -> Dict[str, Any]:
    """在指定环境中执行一个动作"""
    try:
        check_rate_limit()
        state, reward, done, info = webshop_env_server.step(env_idx, action)
        return {
            "state": state,
            "reward": reward,
            "done": done,
            "info": info
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def get_available_actions(env_idx: int) -> Dict[str, Any]:
    """获取指定环境中可用的动作"""
    try:
        check_rate_limit()
        res = webshop_env_server.get_available_actions(env_idx)
        return {
            "has_search_bar": res["has_search_bar"],
            "clickables": res["clickables"]
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def get_instruction(env_idx: int) -> str:
    """获取指定环境的指令文本"""
    try:
        check_rate_limit()
        return webshop_env_server.get_instruction_text(env_idx)
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def get_observation(env_idx: int) -> str:
    """获取指定环境的观察结果"""
    try:
        check_rate_limit()
        return webshop_env_server.observation(env_idx)
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def get_state(env_idx: int) -> Dict[str, Any]:
    """获取指定环境的完整状态"""
    try:
        check_rate_limit()
        url, html, instruction_text = webshop_env_server.state(env_idx)
        return {
            "url": url,
            "html": html,
            "instruction_text": instruction_text
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def reset_env(env_idx: int, session_id: str = None) -> Dict[str, Any]:
    """重置指定环境"""
    try:
        check_rate_limit()
        result = webshop_env_server.reset(env_idx, session_id)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def list_envs() -> List[int]:
    """列出所有活跃的环境"""
    try:
        check_rate_limit()
        return list(webshop_env_server.env.keys())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # 启动标准输入输出模式的MCP服务器
    mcp.run(transport='stdio')