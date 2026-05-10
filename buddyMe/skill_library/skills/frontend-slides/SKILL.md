---
name: frontend-slides
description: 从头开始创建令人惊叹、动画丰富的 HTML 演示文稿，或通过转换 PowerPoint 文件生成。当用户想要构建演示文稿、将 PPT/PPTX 转换为网页版，或为演讲/路演创建幻灯片时使用。帮助非设计师通过视觉探索而非抽象选择来发现他们的审美。
origin: ECC
---

# 前端幻灯片（Frontend Slides）

创建完全在浏览器中运行、零依赖、动画丰富的 HTML 演示文稿。

受 zarazhangrui 作品中展示的视觉探索方法的启发（致谢：@zarazhangrui）。

## 激活时机（When to Activate）

- 创建演讲幻灯片组（Talk deck）、路演幻灯片组（Pitch deck）、工作坊幻灯片组或内部演示文稿
- 将 `.ppt` 或 `.pptx` 幻灯片转换为 HTML 演示文稿
- 改进现有 HTML 演示文稿的布局、动态（Motion）或排版（Typography）
- 与尚不清楚其设计偏好的用户一起探索演示风格

## 硬性规定（Non-Negotiables）

1. **零依赖（Zero dependencies）**：默认生成一个包含内联 CSS 和 JS 的自包含 HTML 文件。
2. **必须适配视口（Viewport fit）**：每张幻灯片必须适配在一个视口内，且无内部滚动。
3. **展示而非叙述（Show, don't tell）**：使用视觉预览，而不是抽象的风格问卷。
4. **独特的设计**：避免通用的紫色渐变、白底 Inter 字体、看起来像模板的幻灯片组（Decks）。
5. **生产质量**：保持代码有注释、可访问、响应式且高性能。

在生成之前，请阅读 `STYLE_PRESETS.md` 以了解视口安全（Viewport-safe）的 CSS 基础、密度限制、预设目录和 CSS 注意事项。

## 工作流（Workflow）

### 1. 检测模式（Detect Mode）

选择一条路径：
- **新演示文稿**：用户有主题、笔记或完整草稿
- **PPT 转换**：用户有 `.ppt` 或 `.pptx`
- **增强**：用户已有 HTML 幻灯片并希望进行改进

### 2. 内容发现（Discover Content）

仅询问最少需要的信息：
- 目的：路演、教学、会议演讲、内部更新
- 长度：短（5-10 页）、中（10-20 页）、长（20+ 页）
- 内容状态：已完成的文案、粗略笔记、仅有主题

如果用户有内容，请他们在开始设计风格前粘贴内容。

### 3. 风格发现（Discover Style）

默认采用视觉探索方式。

如果用户已经知道所需的预设，跳过预览并直接使用。

否则：
1. 询问幻灯片组应营造什么样的感觉：震撼、充满活力、专注、受到启发。
2. 在 `.ecc-design/slide-previews/` 中生成 **3 个单页幻灯片预览文件**。
3. 每个预览必须是自包含的，清晰展示排版/颜色/动态，且幻灯片内容保持在大约 100 行以内。
4. 询问用户保留哪个预览或混合哪些元素。

在将氛围映射到风格时，请参考 `STYLE_PRESETS.md` 中的预设指南。

### 4. 构建演示文稿（Build the Presentation）

输出：
- `presentation.html`
- `[presentation-name].html`

仅当幻灯片组包含提取的或用户提供的图像时，才使用 `assets/` 文件夹。

必要结构：
- 语义化的幻灯片部分（sections）
- 来自 `STYLE_PRESETS.md` 的视口安全 CSS 基础
- 用于主题值的 CSS 自定义属性
- 用于键盘、滚轮和触摸导航的演示控制器类
- 用于显示动画的 Intersection Observer
- 减弱动态（Reduced-motion）支持

### 5. 强制视口适配（Enforce Viewport Fit）

将其视为硬性门槛。

规则：
- 每个 `.slide` 必须使用 `height: 100vh; height: 100dvh; overflow: hidden;`
- 所有字体和间距必须使用 `clamp()` 缩放
- 当内容放不下时，拆分为多张幻灯片
- 严禁通过将文本缩小到可读尺寸以下来解决溢出问题
- 严禁在幻灯片内部出现滚动条

使用 `STYLE_PRESETS.md` 中的密度限制和强制性 CSS 块。

### 6. 验证（Validate）

在以下尺寸检查完成的幻灯片组：
- 1920x1080
- 1280x720
- 768x1024
- 375x667
- 667x375

如果可以使用浏览器自动化工具，请用它来验证没有幻灯片溢出且键盘导航正常工作。

### 7. 交付（Deliver）

在交付时：
- 除非用户想保留，否则删除临时预览文件
- 在有用时，使用平台适用的命令打开幻灯片组
- 总结文件路径、使用的预设、幻灯片页数以及易于自定义的主题点

为当前操作系统使用正确的打开方式：
- macOS: `open file.html`
- Linux: `xdg-open file.html`
- Windows: `start "" file.html`

## PPT / PPTX 转换

对于 PowerPoint 转换：
1. 优先使用带有 `python-pptx` 的 `python3` 来提取文本、图像和备注。
2. 如果 `python-pptx` 不可用，询问是否安装它，或者退回到手动/基于导出的工作流。
3. 保留幻灯片顺序、演讲者备注和提取的资产。
4. 提取后，运行与新演示文稿相同的风格选择工作流。

保持转换跨平台。当 Python 可以胜任时，不要依赖仅限 macOS 的工具。

## 实现要求（Implementation Requirements）

### HTML / CSS

- 除非用户明确要求多文件项目，否则使用内联 CSS 和 JS。
- 字体可以来自 Google Fonts 或 Fontshare。
- 优先选择有氛围的背景、强大的排版层次结构和清晰的视觉方向。
- 使用抽象形状、渐变、网格、噪声和几何图形，而不是插图。

### JavaScript

包含：
- 键盘导航
- 触摸 / 滑动导航
- 鼠标滚轮导航
- 进度指示器或幻灯片索引
- 进入时显示（Reveal-on-enter）动画触发器

### 可访问性（Accessibility）

- 使用语义化结构（`main`, `section`, `nav`）
- 保持对比度可读
- 支持纯键盘导航
- 尊重 `prefers-reduced-motion`

## 内容密度限制（Content Density Limits）

除非用户明确要求更密集的幻灯片且仍保持可读性，否则使用以下最大限制：

| 幻灯片类型 | 限制 |
|------------|-------|
| 标题（Title） | 1 个主标题 + 1 个副标题 + 可选口号 |
| 内容（Content） | 1 个标题 + 4-6 个项目符号或 2 个短段落 |
| 功能网格（Feature grid） | 最多 6 个卡片 |
| 代码（Code） | 最多 8-10 行 |
| 引言（Quote） | 1 段引言 + 署名 |
| 图像（Image） | 1 张受视口约束的图像 |

## 反面模式（Anti-Patterns）

- 没有视觉辨识度的通用初创公司风格渐变
- 使用系统字体（除非是有意为之的编辑风格）
- 长篇的项目符号墙
- 需要滚动的代码块
- 在短屏幕上会断开的固定高度内容框
- 无效的负值 CSS 函数，如 `-clamp(...)`

## 相关的 ECC 技能（Related ECC Skills）

- `frontend-patterns`：用于幻灯片组周围的组件和交互模式
- `liquid-glass-design`：当演示文稿有意借用 Apple 玻璃拟态审美时使用
- `e2e-testing`：如果需要对最终幻灯片组进行自动化浏览器验证

## 交付物检查清单（Deliverable Checklist）

- 演示文稿可以在浏览器中通过本地文件运行
- 每张幻灯片都能适配视口而无需滚动
- 风格独特且具有设计意图
- 动画有意义，而非嘈杂
- 尊重减弱动态设置
- 在交付时解释了文件路径和自定义点
