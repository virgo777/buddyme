# 国内城市名称拼音对照表

本文件用于将用户输入的中文城市名转换为标准拼音格式，供 `scripts/weather.py` 调用时使用。

## 直辖市

| 中文名 | 拼音 | 备注 |
|--------|------|------|
| 北京 | beijing | 首都 |
| 上海 | shanghai | |
| 天津 | tianjin | |
| 重庆 | chongqing | |

## 省会城市

| 中文名 | 拼音 | 省份 |
|--------|------|------|
| 石家庄 | shijiazhuang | 河北 |
| 太原 | taiyuan | 山西 |
| 呼和浩特 | hohhot | 内蒙古 |
| 沈阳 | shenyang | 辽宁 |
| 长春 | changchun | 吉林 |
| 哈尔滨 | harbin | 黑龙江 |
| 南京 | nanjing | 江苏 |
| 杭州 | hangzhou | 浙江 |
| 合肥 | hefei | 安徽 |
| 福州 | fuzhou | 福建 |
| 南昌 | nanchang | 江西 |
| 济南 | jinan | 山东 |
| 郑州 | zhengzhou | 河南 |
| 武汉 | wuhan | 湖北 |
| 长沙 | changsha | 湖南 |
| 广州 | guangzhou | 广东 |
| 南宁 | nanning | 广西 |
| 海口 | haikou | 海南 |
| 成都 | chengdu | 四川 |
| 贵阳 | guiyang | 贵州 |
| 昆明 | kunming | 云南 |
| 拉萨 | lhasa | 西藏 |
| 西安 | xian | 陕西 |
| 兰州 | lanzhou | 甘肃 |
| 西宁 | xining | 青海 |
| 银川 | yinchuan | 宁夏 |
| 乌鲁木齐 | urumqi | 新疆 |

## 其他主要城市

| 中文名 | 拼音 | 省份 |
|--------|------|------|
| 深圳 | shenzhen | 广东 |
| 苏州 | suzhou | 江苏 |
| 东莞 | dongguan | 广东 |
| 青岛 | qingdao | 山东 |
| 大连 | dalian | 辽宁 |
| 厦门 | xiamen | 福建 |
| 宁波 | ningbo | 浙江 |
| 无锡 | wuxi | 江苏 |
| 珠海 | zhuhai | 广东 |
| 洛阳 | luoyang | 河南 |
| 温州 | wenzhou | 浙江 |
| 徐州 | xuzhou | 江苏 |

## 使用说明

- 当用户输入 "北京" 或 "北京市" 时，均转换为 `beijing`
- 当用户输入 "西安" 时，转换为 `xian`（注意不是 `xian` 的其他拼写）
- 城市名带 "市" 字后缀时，应自动去除后再匹配
- 如遇到表中未列出的城市，可尝试直接使用城市名拼音作为查询参数
