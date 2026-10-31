# BuddyMe 桌面版 · 打包全流程与踩坑手册（V4）

> 读者：负责打包/发版的 Claude（或工程师）· 2026-09-24 修订（rev12 · 1.0.31 发布实录）
> 本文取代 V3：新增 **动态端口自愈（VPN 共存）/ 滚轮屏 300s+实时进度 / 端口冲突排障法 / 版本纪律实例（1.0.29→1.0.31）/ 最终用户安装说明（随包分发）**。
> 站点对接：《01-网站更新配置手册-给站点Claude-V2.md》；更新链验收：《03-更新检测测试手册》。

---

## 一、产物形态（rev12）

安装到 `C:\Users\<用户>\AppData\Local\Programs\BuddyMe`（per-user，免 UAC）：

```
BuddyMe\
├─ buddyme.exe            主程序（内嵌 logo；滚轮屏启动；标题栏无图标；★动态端口）
├─ uninst.exe             卸载器（数据保全）
├─ VERSION                ★运行时磁盘读取（改版本号不用重构建）
├─ README.txt / _bootstrap.py（默认工作空间=桌面\buddyme-workspace）
├─ log\                   运行日志（排障第一现场）
├─ agent_core\ context_build\   ★隐藏属性 + .pyc 字节码（源码不落盘）
├─ cli_moudle\（含 buddyme.ico）config_library\ skill_library\ …
└─ _runtime\              581MB 运行时（目标机零依赖，无需 Python/VC++）
```

## 二、发新版完整流程

```bash
cd C:/Users/xiaohua/Desktop/buddyme-engineer/buddyme-engineer
# ① 版本号：纯点分数字。★仅改版本 = 更新 仓库\VERSION + C:\bm_dist\buddyme\VERSION 两处即可（运行时读盘）
#    ★版本纪律实例：1.0.29 已在本机装过 → 修 bug 重发跳 1.0.31（同号绝不复用）
# ② 改过 .py / templates / static → 必须全量构建（约 12-16 分钟）：
python skill_library/skills/packaging/exe_skill/scripts/build_exe.py --windowed
# ③ 打安装器（nsi 自动隐藏 agent_core/context_build）：
taskkill //IM makensis.exe //F 2>/dev/null
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
"/c/Program Files (x86)/NSIS/makensis.exe" /V2 "/DVERSION=1.0.31" \
  "/DOUTDIR=C:/Users/xiaohua/Desktop/buddyme-engineer/buddyme-engineer/output" \
  "/DSRCDIR=C:/bm_dist/buddyme" \
  "skill_library/skills/packaging/exe_skill/scripts/installer.nsi"
# ④ 改名 BuddyMe-Setup-<版本>.exe → 更新 latest.json → /S 静默装自测 → 交付运维
```

## 三、启动链路（rev12 定稿）

| 环节 | 行为 |
|---|---|
| 滚轮屏 | 内联 HTML 先显示（vmin 适配屏幕/DPI），服务就绪 `load_url` 无缝切换 |
| 等待上限 | **300 秒**；每 10s 刷新「已等待 N 秒（杀毒扫描/智能体预热）」；超时才报「启动失败:本地服务未就绪」 |
| **动态端口** | `_pick_free_port`：5050 被占（TCP）→ 依次试 5051-5059；日志打「端口 X 被占用（VPN/代理？）→ 改试 X+1」；前端全同源相对路径 + 窗口 URL 动态拼端口 → 换端口零影响 |
| 标题栏 | WM_SETICON 透明图标（无左上角图标）；任务栏保留 exe logo |

## 四、图标链（换图标必读）

源图 `cli_moudle/buddymeLogo.png` → `make_icon.py` → `scripts/buddyme.ico`（--icon 嵌 exe）+ `cli_moudle/buddyme.ico`（随包分发）。换图标必须重构建。

**坑20 复述**：exe 图标验证用 pywin32（`.NET Icon` API 不认 PNG 压缩条目会误报「无效」）；用户机器显示旧图标 = 图标缓存（删 iconcache_*.db + 重启 explorer），不是嵌入失败。

## 五、构建脚本链

| 文件 | 职责 |
|---|---|
| `make_icon.py` | PNG → 多尺寸 ico |
| `build_exe.py` | PyInstaller + 构建后处理：提升/瘦身/**.pyc 源码保护**（agent_core+context_build 119 个） |
| `installer.nsi` | per-user 安装器：数据保全三策略 / 装后隐藏两个源码目录 / DisplayVersion |
| `entrypoint.py` | 滚轮屏(300s+进度) / `_pick_free_port` / 透明图标 / 更新取消下载 |

## 六、验证清单（每次发版必跑）

```bash
C:/bm_dist/buddyme/buddyme.exe & sleep 30        # 坑1：绝对路径
curl -s http://127.0.0.1:5050/api/app/version    # 版本号；端口被占时看日志换到 505x
curl -s http://127.0.0.1:5050/api/skills | head -c 60
curl -s http://127.0.0.1:5050/api/vision_config/models | head -c 80
# 日志：4-agent 全 ready（.pyc 试金石）；jserr.log 空
# 专项：.py=0/.pyc=119；搜索 4 档默认 searxng；LLM 3 档；生图仅 buddyme-gpt-image-2.5
# /S 静默装：uninst.exe 在、Hidden 属性、DisplayVersion=新号、装完自启
taskkill //IM buddyme.exe //F
```

## 七、源码保护（.pyc + 隐藏，定案）

- `.py` → `py_compile` → 同目录 `.pyc`，源文件删除：明文 0 落盘，SourcelessFileLoader 导入无感
- 安装器 SetFileAttributes HIDDEN（agent_core/context_build）
- **不能只删 .py**（坑18：add-data 包运行靠磁盘导入，不在 PYZ）；要抗反编译需 Cython（未立项）

## 八、发版内容基线（1.0.31）

- LLM：buddyme_glm_flash5.3 / 5.3X / version5.3；生图：仅 buddyme-gpt-image-2.5；搜索：searxng_search(默认)+免费池+聚合+arXiv
- 工作空间默认：桌面\buddyme-workspace（首启自建）
- 前端：模型页修复 / 站点Key精简 / 更新气泡+角标可点+取消下载 / 发送防重入 / `?v=20260924c`
- **1.0.31 增量**：端口冲突自愈（VPN 共存）+ 滚轮屏 300s 实时进度（根治「本地服务未就绪」误报）
- 个人数据不随包：cli-state（内核经验/会话）每用户从零（新装内核经验为空属正常）

## 九、坑总表（1-23 见 V3，24 为 V4 新增）

1-23. 继承（含：add-data≠PYZ / frozen `__file__` 悬空 / 图标缓存 / VERSION 免重建 / 构建完成误判 `[exited with code]` / PowerShell 内联转义写 ps1）。

24. **【新】「启动失败:本地服务未就绪」两病因一表象**：
    - **病因A 慢启动**：Defender 全量扫描 + 预热期 LLM 429 熔断重试 → 超 90s 误报（已修：300s+进度显示）。日志特征：预热消息**全部出现**且以「agent 线程已全部终止」收尾（用户关窗）。
    - **病因B TCP 端口被占**：v2ray/Clash/老版工具占 TCP 5050 → 绑定失败服务死（已修：动态避让 5051+）。
    - **诊断法**：①看日志——「后端启动」+预热全有=A；无后端启动/绑定异常=B。②`netstat -ano | findstr :5050`——**只有 UDP 行（svchost）=无害巧合**（Flask 走 TCP），有 TCP LISTEN 行才是真占用。③别让用户关 VPN 重启——1.0.31 起自动避让。

## 十、给最终用户的安装说明（随包分发文案）

> **安装**：双击 `BuddyMe-Setup-<版本>.exe`，一路下一步（装到用户目录，无需管理员权限）。
> **首次双击若弹蓝色「Windows 已保护你的电脑」**：点「更多信息」→「仍要运行」（软件未购买微软签名证书，本身安全）。
> **首次启动 10-60 秒属正常**：窗口先显示启动滚轮（实时显示已等待秒数），杀毒扫描+智能体预热完成后自动进入。超过 5 分钟仍提示失败再查日志。
> **无需安装任何运行环境**：不需要 Python；Win11/较新 Win10 自带 WebView2 即可（老 Win10 未打过更新可能缺，装 Edge 浏览器即可补齐）。
> **VPN/代理可以开着**：应用自动避开被占端口。
> **装好后**：桌面出现 `buddyme-workspace` 文件夹（默认工作空间，成果交付在这里）；更新采用覆盖安装，设置/技能/会话数据全部保留。

## 十一、历史包袱备忘

`exe_skill/01-07`（rev1-8）· V2 手册（rev9-10）· V3（rev11）· 本文 rev12；`buddyme.spec` 勿手改；hermes-office-cli 缺失 → Office 套件 fail-open。

*V4 修订于 2026-09-24（1.0.31 发布）：动态端口自愈 / 滚轮屏 300s / 坑24 两病因诊断法 / 用户安装文案。配套：01-V2（站点）、03（更新测试）。*
