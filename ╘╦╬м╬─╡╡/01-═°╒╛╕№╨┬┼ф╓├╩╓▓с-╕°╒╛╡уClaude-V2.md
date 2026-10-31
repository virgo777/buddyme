# BuddyMe 站点更新与配置手册（V2 · 给打包 Claude）

> 站点侧：buddyme.cn 主站运维 Claude · 2026-09-24 上线
> 用途：打包侧每发新版本时，把本手册当对接契约——**站点已全部配置好，你只需要交两个东西**。

---

## 一、站点现状（已上线，勿重复配置）

| 项 | 状态 |
|---|---|
| 下载清单 | `https://www.buddyme.cn/downloads/latest.json` ✓ 可访问 |
| 安装包直链 | `https://www.buddyme.cn/downloads/BuddyMe-Setup-1.0.0.exe` ✓ HTTP 200，Content-Type: application/octet-stream |
| 断点续传 | ✓ Range 请求返回 206 |
| 下载网页 | `https://www.buddyme.cn/download/` ✓ 自动读取 latest.json 显示最新版本号、更新说明、下载按钮和文件大小 |
| nginx | `/downloads/` 静态 alias（sendfile+tcp_nopush+no-cache），exe/json MIME 正确，无鉴权无跳转 |
| 文件落点 | 站点服务器 `/home/ubuntu/BuddyMeBlog/downloads/public/` |

## 二、发新版本时你要交什么（只有两样）

1. **新安装包**：`BuddyMe-Setup-<新版本号>.exe`（命名必须一字不差）
2. **一段更新说明**：一句话（可不给，客户端/网页就不显示说明）

**交给站点的方式**：放到约定目录（站点侧约定 `/home/ubuntu/BuddyMeBlog/downloads/installer/`，站点运维 Claude 会取走部署），或按现有投递通道转给站点运维并附版本号+说明。

## 三、站点侧接手后的动作（打包侧无需关心）

上传 exe 到 `downloads/public/` → 更新 latest.json 的 version/url/notes → 自检两条 curl。**先传 exe、后改 json**（防「提示更新但下载 404」窗口期）。旧版 exe 不删（回滚靠它）。

24 小时内所有桌面客户端自动发现新版本（红 new 角标）；网页 `/download/` 下次访问即显示新版。

## 四、版本号规范（客户端严格校验，违约=客户端当无更新）

| 规则 | 说明 |
|---|---|
| 格式 | 纯点分数字 `^\d+(\.\d+)*$`：`1.0.1`、`1.2.10` ✓ |
| 禁止 | `1.0.1a`、`v1.0.1`、`1.0.1-beta` ✗ |
| 比较 | 逐段数字比较：`1.10.0 > 1.9.9`，与日期无关 |
| 递增 | 修 bug 末位 +1；新功能中间位 +1；大改版首位 +1 |

## 五、latest.json 字段（客户端+网页双重校验）

```json
{
  "version": "1.0.1",
  "url": "https://www.buddyme.cn/downloads/BuddyMe-Setup-1.0.1.exe",
  "notes": "一句话更新说明（可选，>500 字截断）"
}
```
- `url` 必须 `https://` 开头的完整直链
- url 的文件名必须与实际安装包文件名**完全一致**（客户端按 `BuddyMe-Setup-{version}.exe` 落盘）

## 六、网页下载页行为（/download/）

- 自动 fetch latest.json：显示版本号 + notes + 下载按钮（含文件大小）
- 校验与客户端同规则，不合规自动回退「即将上线」占位
- 桌面客户端更新与网页下载共用同一份 latest.json

## 七、自检命令

```bash
curl -s https://www.buddyme.cn/downloads/latest.json
# 期望：json 原文，version 纯点分数字、url https 直链
curl -sI https://www.buddyme.cn/downloads/BuddyMe-Setup-<版本>.exe
# 期望：HTTP 200 + Content-Length 真实大小 + application/octet-stream
```

## 八、常见问题

| 现象 | 原因 | 修法 |
|---|---|---|
| 客户端「无更新信息」 | json 404 / 格式错 / version 带字母 / url 非 https | 第五节逐项检查 |
| 网页显示「即将上线」但 json 正常 | 前端缓存旧 chunk | 强刷；站点构建后 5 分钟内生效 |
| 有角标但下载秒失败 | url 不可达/是网页 | 自检②；客户端防呆 <1MB 报「URL 指向网页」 |
| 下载 99% 断 | 服务器断连 | 站点已开 Range 206；客户端可续传 |
| 部分用户不提示 | 24h 节流未到 | 用户点「检查更新」立即触发 |

## 九、回滚与下架

- **回滚**：latest.json 改回旧版本号+旧 url（旧 exe 站点保留）
- **下架更新**：改名/删除 latest.json → 客户端全部静默回「无更新」

---

*站点侧联系人：buddyme.cn 主站运维 Claude。本手册对应站点部署 2026-09-24。*
