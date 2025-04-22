from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
# 建立服务器，支持双向管道写入写出
mcp = FastMCP("weather")

# Constants
WIS_API_BASE = "https://wis.qq.com"
# 发送API调用请求但是这其实在后面的每个mcp.tool都需要调用
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """向腾讯天气API发送请求并返回响应数据."""
    headers = {
        "Accept": "application/json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None



@mcp.tool()
async def get_forecast_48h(province: str, city: str) -> str:
    """获取中国某个省，某个城市的未来48个小时天气预报。

    参数:
        province: 省份名称
        city: 城市名称
    """
    # 首先获取指定地点的天气预报
    forecast_url = f"{WIS_API_BASE}/weather/common?source=pc&weather_type=forecast_1h&province={province}&city={city}"
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "无法获取此位置的未来48小时的天气预报。"

    # 将JSON数据格式化为可读的预报
    periods = forecast_data["data"]["forecast_1h"]

    forecasts = []
    for period in periods:
        # periods['update_time']数据为20250411140000,需要格式化为2025-04-11 14:00:00
        _time = periods[period]["update_time"][:4] + "-" + periods[period]["update_time"][4:6] + "-" + periods[period]["update_time"][6:8] + " " + periods[period]["update_time"][8:10] + ":" + periods[period]["update_time"][10:12] + ":" + periods[period]["update_time"][12:14]
        forecast = f"""
时间：{_time}
温度: {periods[period]['degree']}°
天气: {periods[period]['weather']}
风向: {periods[period]['wind_direction']}
风速: {periods[period]['wind_power']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.tool()
async def get_alarms(province: str, city: str) -> str:
    """获取中国某个省，某个城市的天气预警。

    参数:
        province: 省份名称
        city: 城市名称
    """
    # 首先获取指定地点的天气预警
    alarm_url = f"{WIS_API_BASE}/weather/common?source=pc&weather_type=alarm&province={province}&city={city}"
    alarm_data = await make_nws_request(alarm_url)

    if not alarm_data or "data" not in alarm_data or "alarm" not in alarm_data["data"]:
        return "无法获取此位置的天气预警。"

    # 确保 alarm 是一个列表
    alarms = alarm_data["data"]["alarm"]
    
    # 如果 alerms 是列表，但是为空，则返回提示
    if isinstance(alarms, list) and len(alarms) == 0:
        return "该城市暂时没有天气预警。"

    # 将JSON数据格式化为可读的预警
    alarm_list = []
    for alarm in alarms:
        alarm_list.append(f"""
预警区域: {alarm["province"]}
预警类型: {alarm["type_name"]}
预警级别: {alarm["level_name"]}
预警时间: {alarm["update_time"]}
预警内容: {alarm["detail"]}
""")
        
    return "\n---\n".join(alarm_list)

@mcp.tool()
async def get_forecast_week(province: str, city: str) -> str:
    """获取中国某个省，某个城市的未来一周天气预报。

    参数:
        province: 省份名称
        city: 城市名称
    """

    # 首先获取指定地点的天气预报
    forecast_url = f"{WIS_API_BASE}/weather/common?source=pc&weather_type=forecast_24h&province={province}&city={city}"
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "无法获取此位置的未来一周的天气预报。"

    # 将JSON数据格式化为可读的预报
    periods = forecast_data["data"]["forecast_24h"]

    forecasts = []
    for period in periods:
        forecast = f"""
日期: {periods[period]["time"]}
温度: {periods[period]["min_degree"]}° ~ {periods[period]["max_degree"]}°
白天天气: {periods[period]["day_weather"]}
白天风向: {periods[period]["day_wind_direction"]}
白天风速: {periods[period]["day_wind_power"]}
夜间天气: {periods[period]["night_weather"]}
夜间风向: {periods[period]["night_wind_direction"]}
夜间风速: {periods[period]["night_wind_power"]}
"""
        forecasts.append(forecast)
    return "\n---\n".join(forecasts)

@mcp.tool()
async def get_observe(province: str, city: str) -> str:
    """获取中国某个省，某个城市的实时天气。

    参数:
        province: 省份名称
        city: 城市名称
    """
    # 首先获取指定地点的天气预报
    observe_url = f"{WIS_API_BASE}/weather/common?source=pc&weather_type=observe&province={province}&city={city}"
    observe_data = await make_nws_request(observe_url)

    if not observe_data:
        return "无法获取此位置的实时天气。"

    # 将JSON数据格式化为可读的预报
    observe = observe_data["data"]["observe"]
    _update_time = observe["update_time"][:4] + "-" + observe["update_time"][4:6] + "-" + observe["update_time"][6:8] + " " + observe["update_time"][8:10] + ":" + observe["update_time"][10:12] + ":" + observe["update_time"][12:14]
    return f"""
时间: {_update_time}
温度: {observe["degree"]}°
湿度: {observe["humidity"]}%
降水量: {observe["precipitation"]}mm
气压: {observe["pressure"]}hPa
天气: {observe["weather"]}
风向: {observe["wind_direction_name"]}
风速: {observe["wind_power"]}
"""

mcp.tool()
async def get_rise_14day(province: str, city: str) -> str:
    """获取中国某个省，某个城市的未来14天的日出日落时间。

    参数:
        province: 省份名称
        city: 城市名称
    """
    # 首先获取指定地点的未来14天的日出日落时间
    rise_url = f"{WIS_API_BASE}/weather/common?source=pc&weather_type=rise&province={province}&city={city}"
    rise_data = await make_nws_request(rise_url)

    if not rise_data:
        return "无法获取此位置的日出日落时间。"

    # 将JSON数据格式化为可读的预报
    rises = rise_data["data"]["rise"]
    rise_list = []
    for rise in rises:
        rise_list.append(f"""
日期: {rises[rise]["time"]}
日出时间: {rises[rise]["sunrise"]}
日落时间: {rises[rise]["sunset"]}
"""
        )
    return "\n---\n".join(rise_list)

if __name__ == "__main__":
    # Initialize and run the server
    # mcp.run(transport='stdio')
    # import asyncio
    # # 本地直接调用工具（绕过MCP协议）
    # print(asyncio.run(get_forecast_48h("河北", "秦皇岛")))
    # 正式启动服务
    mcp.run(transport='stdio')