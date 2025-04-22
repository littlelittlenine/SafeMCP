from typing import Any, Dict, List
import httpx
import os
import time
import json
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
load_dotenv()  # 加载当前目录下的 .env 文件
# 初始化 MCP 服务器
mcp = FastMCP("search")

# 博查 API 配置
# BOCHA_API_KEY = os.getenv("BOCHA_API_KEY", "")
BOCHA_API_KEY = os.getenv("BOCHA_API_KEY", "")
if not BOCHA_API_KEY:
    raise ValueError("请设置 BOCHA_API_KEY 环境变量")

API_ENDPOINT = "https://api.bochaai.com/v1/web-search"

# 搜索时间范围配置
FRESHNESS_RANGES = {
    "noLimit": "不限",
    "oneDay": "一天内",
    "oneWeek": "一周内", 
    "oneMonth": "一月内",
    "oneYear": "一年内"
}

# 速率限制配置
RATE_LIMIT = {
    "per_second": 2,
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

async def make_bocha_request(query: str, count: int = 10, page: int = 1, 
                           freshness: str = "noLimit", summary: bool = False) -> Dict[str, Any]:
    """向博查API发送搜索请求"""
    headers = {
        "Authorization": f"Bearer {BOCHA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "query": query,
        "count": count,
        "page": page,
        "freshness": freshness,
        "summary": summary
    }
    
    try:
        check_rate_limit()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                API_ENDPOINT,
                json=params,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def web_search(query: str, count: int = 10, page: int = 1,
                    freshness: str = "noLimit", summary: bool = False) -> str:
    """
    执行网页搜索并返回格式化结果
    
    参数:
        query: 搜索关键词
        count: 返回结果数量(1-10)
        page: 页码(从1开始)
        freshness: 时间范围(noLimit/oneDay/oneWeek/oneMonth/oneYear)
        summary: 是否显示详细摘要
    """
    # 验证参数
    if not query:
        return "搜索关键词不能为空"
    if not 1 <= count <= 10:
        return "结果数量必须在1-10之间"
    if page < 1:
        return "页码必须大于0"
    if freshness not in FRESHNESS_RANGES:
        return f"时间范围必须是: {list(FRESHNESS_RANGES.keys())}"
    
    # 调用API
    result = await make_bocha_request(query, count, page, freshness, summary)
    
    # 处理错误
    if "error" in result:
        return f"API请求失败: {result['error']}"
    if result.get("code") != 200:
        return f"搜索失败: {result.get('msg', '未知错误')}"
    
    # 格式化结果
    data = result.get("data", {})
    web_pages = data.get("webPages", {}).get("value", [])
    
    if not web_pages:
        return "未找到相关结果"
    
    # 构建响应内容
    formatted = []
    
    # 添加统计信息
    total = data.get("webPages", {}).get("totalEstimatedMatches", 0)
    formatted.append(
        f"找到约 {total} 条结果 (当前显示 {len(web_pages)} 条)\n"
        f"时间范围: {FRESHNESS_RANGES[freshness]}\n"
    )
    
    # 添加每个结果
    for idx, item in enumerate(web_pages, 1):
        item_info = [
            f"{idx}. {item.get('name', '无标题')}",
            f"网址: {item.get('url', '未知')}",
            f"来源: {item.get('siteName', '未知')}",
        ]
        
        if summary and item.get("summary"):
            item_info.append(f"摘要: {item['summary']}")
        else:
            item_info.append(f"描述: {item.get('snippet', '无描述')}")
            
        if "dateLastCrawled" in item:
            item_info.append(f"抓取时间: {item['dateLastCrawled']}")
            
        formatted.append("\n".join(item_info))
    
    return "\n\n".join(formatted)

@mcp.tool()
async def image_search(query: str, count: int = 10) -> str:
    """
    执行图片搜索
    
    参数:
        query: 搜索关键词
        count: 返回结果数量(1-10)
    """
    # 参数验证
    if not query:
        return "搜索关键词不能为空"
    if not 1 <= count <= 10:
        return "结果数量必须在1-10之间"
    
    # 调用API
    result = await make_bocha_request(query, count=count)
    
    # 处理错误
    if "error" in result:
        return f"API请求失败: {result['error']}"
    if result.get("code") != 200:
        return f"搜索失败: {result.get('msg', '未知错误')}"
    
    # 格式化结果
    data = result.get("data", {})
    images = data.get("images", {}).get("value", [])
    
    if not images:
        return "未找到相关图片"
    
    # 构建响应内容
    formatted = [f"找到 {len(images)} 张相关图片:\n"]
    
    for idx, img in enumerate(images, 1):
        img_info = [
            f"{idx}. {img.get('name', '无标题')}",
            f"尺寸: {img.get('width', '未知')}x{img.get('height', '未知')}",
            f"来源: {img.get('hostPageDisplayUrl', img.get('hostPageUrl', '未知'))}",
            f"图片URL: {img.get('contentUrl', '未知')}",
        ]
        formatted.append("\n".join(img_info))
    
    return "\n\n".join(formatted)

if __name__ == "__main__":
    # 启动标准输入输出模式的MCP服务器
    mcp.run(transport='stdio')