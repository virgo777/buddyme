#!/usr/bin/env python3
"""
天气查询脚本 - 调用 wttr.in 免费 API 查询国内城市实时天气

用法:
    python weather.py              # 默认查询北京
    python weather.py <城市拼音>
    python weather.py beijing
    python weather.py shanghai

示例输出:
    北京: 25°C, 晴, 湿度 45%, 风速 10km/h
"""

import json
import sys
import urllib.request
import urllib.error

# 常用城市拼音 -> 中文名映射
CITY_MAP = {
    "beijing": "北京", "shanghai": "上海", "guangzhou": "广州",
    "shenzhen": "深圳", "chengdu": "成都", "hangzhou": "杭州",
    "wuhan": "武汉", "nanjing": "南京", "tianjin": "天津",
    "chongqing": "重庆", "xian": "西安", "suzhou": "苏州",
    "changsha": "长沙", "zhengzhou": "郑州", "dongguan": "东莞",
    "qingdao": "青岛", "shenyang": "沈阳", "dalian": "大连",
    "kunming": "昆明", "xiamen": "厦门", "harbin": "哈尔滨",
    "fuzhou": "福州", "hefei": "合肥", "nanning": "南宁",
    "guiyang": "贵阳", "lanzhou": "兰州", "taiyuan": "太原",
    "shijiazhuang": "石家庄", "haikou": "海口", "nanchang": "南昌",
    "changchun": "长春", "yinchuan": "银川", "xining": "西宁",
    "hohhot": "呼和浩特", "lhasa": "拉萨", "urumqi": "乌鲁木齐",
    "jinan": "济南", "ningbo": "宁波", "wuxi": "无锡",
    "zhuhai": "珠海", "luoyang": "洛阳", "wenzhou": "温州",
    "xuzhou": "徐州",
}

# 天气描述中英文映射
WEATHER_DESC_MAP = {
    "Sunny": "晴", "Clear": "晴", "Partly cloudy": "多云",
    "Cloudy": "阴", "Overcast": "阴", "Mist": "雾",
    "Fog": "雾", "Light rain": "小雨", "Moderate rain": "中雨",
    "Heavy rain": "大雨", "Light snow": "小雪", "Moderate snow": "中雪",
    "Heavy snow": "大雪", "Thunderstorm": "雷阵雨",
    "Patchy rain possible": "可能有零星小雨",
    "Patchy snow possible": "可能有零星小雪",
    "Light drizzle": "毛毛雨", "Freezing fog": "冻雾",
}


def translate_weather(desc: str) -> str:
    """将英文天气描述翻译为中文，未匹配时原样返回"""
    return WEATHER_DESC_MAP.get(desc, desc)


def query_weather(city_pinyin: str) -> dict:
    """
    调用 wttr.in JSON API 查询天气信息

    Args:
        city_pinyin: 城市拼音，如 "beijing"

    Returns:
        包含天气信息的字典，失败时返回包含 error 键的字典
    """
    url = f"https://wttr.in/{city_pinyin}?format=j1&lang=zh"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "curl/7.68.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"API 返回错误: HTTP {e.code}"}
    except urllib.error.URLError:
        return {"error": "网络连接失败，请检查网络设置"}
    except Exception as e:
        return {"error": f"查询异常: {str(e)}"}

    try:
        current = data["current_condition"][0]
        city_cn = CITY_MAP.get(city_pinyin.lower(), city_pinyin)
        weather_desc_en = current.get("weatherDesc", [{}])[0].get("value", "未知")
        weather_desc_cn = translate_weather(weather_desc_en)

        return {
            "city": city_cn,
            "temperature": current.get("temp_C", "未知") + "°C",
            "feels_like": current.get("FeelsLikeC", "未知") + "°C",
            "weather": weather_desc_cn,
            "humidity": current.get("humidity", "未知") + "%",
            "wind_speed": current.get("windspeedKmph", "未知") + "km/h",
            "wind_dir": current.get("winddir16Point", ""),
            "visibility": current.get("visibility", "未知") + "km",
            "pressure": current.get("pressure", "未知") + "hPa",
            "uv_index": current.get("uvIndex", "未知"),
        }
    except (KeyError, IndexError):
        return {"error": "解析天气数据失败，接口返回格式异常"}


def format_output(result: dict) -> str:
    """将查询结果格式化为可读的中文输出"""
    if "error" in result:
        return f"查询失败: {result['error']}"

    lines = [
        f"城市: {result['city']}",
        f"天气: {result['weather']}",
        f"温度: {result['temperature']} (体感 {result['feels_like']})",
        f"湿度: {result['humidity']}",
        f"风况: {result['wind_dir']} {result['wind_speed']}",
        f"能见度: {result['visibility']}",
        f"气压: {result['pressure']}",
        f"紫外线指数: {result['uv_index']}",
    ]
    return "\n".join(lines)


def main():
    # 修复：无参数时默认查询北京，兼容双击运行
    if len(sys.argv) == 1:
        city_pinyin = "beijing"
    elif len(sys.argv) == 2:
        city_pinyin = sys.argv[1].strip().lower()
    else:
        print("用法: python weather.py <城市拼音>")
        print("示例: python weather.py beijing")
        sys.exit(1)

    if city_pinyin not in CITY_MAP:
        print(f"警告: '{city_pinyin}' 不在已知城市列表中，尝试直接查询...")

    result = query_weather(city_pinyin)
    print(format_output(result))


if __name__ == "__main__":
    main()