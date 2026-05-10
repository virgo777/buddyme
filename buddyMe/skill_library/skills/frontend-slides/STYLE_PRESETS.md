# 样式预设参考 (Style Presets Reference)

为 `frontend-slides` 精选的视觉样式。

使用此文件进行：
- 必须的视口适配（viewport-fitting）CSS 基础设置
- 预设选择与氛围映射
- CSS 注意事项与验证规则

仅限抽象形状。除非用户明确要求，否则避免使用插图。

## 视口适配是不可逾越的底线

每一页幻灯片必须完全填满一个视口。

### 金科玉律

```text
每一页幻灯片 = 正好一个视口高度。
内容过多 = 拆分为更多幻灯片。
严禁在幻灯片内部滚动。
```

### 密度限制

| 幻灯片类型 | 最大内容量 |
|------------|-----------------|
| 标题页 | 1 个标题 + 1 个副标题 + 可选的标语 |
| 内容页 | 1 个标题 + 4-6 个项目符号或 2 个段落 |
| 功能网格 | 最多 6 个卡片 |
| 代码页 | 最多 8-10 行 |
| 引用页 | 1 条引用 + 署名 |
| 图片页 | 1 张图片，建议高度低于 60vh |

## 强制性基础 CSS

将此代码块复制到每个生成的演示文稿中，然后在此基础上进行主题定制。

```css
/* ===========================================
   视口适配：强制性基础样式 (VIEWPORT FITTING: MANDATORY BASE STYLES)
   =========================================== */

html, body {
    height: 100%;
    overflow-x: hidden;
}

html {
    scroll-snap-type: y mandatory;
    scroll-behavior: smooth;
}

.slide {
    width: 100vw;
    height: 100vh;
    height: 100dvh;
    overflow: hidden;
    scroll-snap-align: start;
    display: flex;
    flex-direction: column;
    position: relative;
}

.slide-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    max-height: 100%;
    overflow: hidden;
    padding: var(--slide-padding);
}

:root {
    --title-size: clamp(1.5rem, 5vw, 4rem);
    --h2-size: clamp(1.25rem, 3.5vw, 2.5rem);
    --h3-size: clamp(1rem, 2.5vw, 1.75rem);
    --body-size: clamp(0.75rem, 1.5vw, 1.125rem);
    --small-size: clamp(0.65rem, 1vw, 0.875rem);

    --slide-padding: clamp(1rem, 4vw, 4rem);
    --content-gap: clamp(0.5rem, 2vw, 2rem);
    --element-gap: clamp(0.25rem, 1vw, 1rem);
}

.card, .container, .content-box {
    max-width: min(90vw, 1000px);
    max-height: min(80vh, 700px);
}

.feature-list, .bullet-list {
    gap: clamp(0.4rem, 1vh, 1rem);
}

.feature-list li, .bullet-list li {
    font-size: var(--body-size);
    line-height: 1.4;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 250px), 1fr));
    gap: clamp(0.5rem, 1.5vw, 1rem);
}

img, .image-container {
    max-width: 100%;
    max-height: min(50vh, 400px);
    object-fit: contain;
}

@media (max-height: 700px) {
    :root {
        --slide-padding: clamp(0.75rem, 3vw, 2rem);
        --content-gap: clamp(0.4rem, 1.5vw, 1rem);
        --title-size: clamp(1.25rem, 4.5vw, 2.5rem);
        --h2-size: clamp(1rem, 3vw, 1.75rem);
    }
}

@media (max-height: 600px) {
    :root {
        --slide-padding: clamp(0.5rem, 2.5vw, 1.5rem);
        --content-gap: clamp(0.3rem, 1vw, 0.75rem);
        --title-size: clamp(1.1rem, 4vw, 2rem);
        --body-size: clamp(0.7rem, 1.2vw, 0.95rem);
    }

    .nav-dots, .keyboard-hint, .decorative {
        display: none;
    }
}

@media (max-height: 500px) {
    :root {
        --slide-padding: clamp(0.4rem, 2vw, 1rem);
        --title-size: clamp(1rem, 3.5vw, 1.5rem);
        --h2-size: clamp(0.9rem, 2.5vw, 1.25rem);
        --body-size: clamp(0.65rem, 1vw, 0.85rem);
    }
}

@media (max-width: 600px) {
    :root {
        --title-size: clamp(1.25rem, 7vw, 2.5rem);
    }

    .grid {
        grid-template-columns: 1fr;
    }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.2s !important;
    }

    html {
        scroll-behavior: auto;
    }
}
```

## 视口检查清单 (Viewport Checklist)

- 每个 `.slide` 都有 `height: 100vh`、`height: 100dvh` 和 `overflow: hidden`
- 所有排版使用 `clamp()`
- 所有间距使用 `clamp()` 或视口单位
- 图片具有 `max-height` 约束
- 网格通过 `auto-fit` + `minmax()` 进行自适应
- 在 `700px`、`600px` 和 `500px` 处存在针对矮屏幕的断点
- 如果感觉拥挤，请拆分幻灯片

## 氛围到预设映射 (Mood to Preset Mapping)

| 氛围 | 推荐预设 |
|------|--------------|
| 震撼 / 自信 (Impressed / Confident) | Bold Signal, Electric Studio, Dark Botanical |
| 兴奋 / 活力 (Excited / Energized) | Creative Voltage, Neon Cyber, Split Pastel |
| 冷静 / 专注 (Calm / Focused) | Notebook Tabs, Paper & Ink, Swiss Modern |
| 启发 / 动人 (Inspired / Moved) | Dark Botanical, Vintage Editorial, Pastel Geometry |

## 预设目录 (Preset Catalog)

### 1. Bold Signal (醒目信号)

- 风格：自信、高冲击力、适用于主题演讲
- 适用场景：融资路演、产品发布、重要声明
- 字体：Archivo Black + Space Grotesk
- 色板：木炭色底，热橙色焦点卡片，纯白文字
- 标志性元素：超大章节编号，暗场上的高对比度卡片

### 2. Electric Studio (电力工作室)

- 风格：简洁、大胆、机构级打磨感
- 适用场景：客户演示、战略回顾
- 字体：仅 Manrope
- 色板：黑、白、高饱和度钴蓝色点缀
- 标志性元素：双面板布局和锐利的编辑对齐

### 3. Creative Voltage (创意电压)

- 风格：充满活力、复古现代、俏皮的自信
- 适用场景：创意工作室、品牌工作、产品叙事
- 字体：Syne + Space Mono
- 色板：电光蓝、霓虹黄、深海军蓝
- 标志性元素：半色调纹理、徽章、强力对比

### 4. Dark Botanical (暗色植物)

- 风格：优雅、高端、有氛围感
- 适用场景：奢侈品牌、深度叙事、高端产品演示
- 字体：Cormorant + IBM Plex Sans
- 色板：近黑色、暖象牙白、腮红粉、金色、陶土色
- 标志性元素：模糊的抽象圆圈、精细线条、克制的动效

### 5. Notebook Tabs (笔记本标签)

- 风格：编辑风格、有条理、触感感
- 适用场景：报告、回顾、结构化叙事
- 字体：Bodoni Moda + DM Sans
- 色板：木炭色背景上的奶油纸张色，配以淡彩色标签
- 标志性元素：纸页感、彩色侧边标签、活页细节

### 6. Pastel Geometry (淡彩几何)

- 风格：亲切、现代、友好
- 适用场景：产品概览、入职培训、轻松的品牌演示
- 字体：仅 Plus Jakarta Sans
- 色板：淡蓝色底，奶油色卡片，柔和粉/薄荷/薰衣草色点缀
- 标志性元素：垂直胶囊形状、圆角卡片、柔和阴影

### 7. Split Pastel (分割淡彩)

- 风格：俏皮、现代、创意
- 适用场景：机构介绍、研讨会、作品集
- 字体：仅 Outfit
- 色板：桃红色 + 薰衣草色分割，配以薄荷色徽章
- 标志性元素：分割背景、圆角标签、轻量级网格叠加层

### 8. Vintage Editorial (复古社论)

- 风格：机智、个性驱动、杂志启发
- 适用场景：个人品牌、观点演讲、叙事
- 字体：Fraunces + Work Sans
- 色板：奶油色、木炭色、灰调暖色点缀
- 标志性元素：几何点缀、带边框的标注块、强力衬线标题

### 9. Neon Cyber (霓虹赛博)

- 风格：未来感、科技感、动力感
- 适用场景：AI、基础设施、开发者工具、关于未来的演讲
- 字体：Clash Display + Satoshi
- 色板：午夜蓝、青色、洋红色
- 标志性元素：发光、粒子、网格、数据雷达动效

### 10. Terminal Green (终端绿)

- 风格：开发者导向、黑客风简洁
- 适用场景：API、CLI 工具、工程演示
- 字体：仅 JetBrains Mono
- 色板：GitHub 暗色主题 + 终端绿
- 标志性元素：扫描线、命令行框架、精确的等宽字体节奏

### 11. Swiss Modern (瑞士现代)

- 风格：极简、精确、数据驱动
- 适用场景：企业汇报、产品战略、分析报告
- 字体：Archivo + Nunito
- 色板：白、黑、信号红
- 标志性元素：可见网格、不对称设计、几何纪律感

### 12. Paper & Ink (纸墨风格)

- 风格：文学感、有深度、故事驱动
- 适用场景：文章随笔、主题演讲叙事、宣言演示
- 字体：Cormorant Garamond + Source Serif 4
- 色板：暖奶油色、木炭色、深红色点缀
- 标志性元素：拉取引用 (pull quotes)、首字下沉、优雅线条

## 直接选择提示词 (Direct Selection Prompts)

如果用户已经知道他们想要的样式，让他们直接从上面的预设名称中选择，而不是强制生成预览。

## 动画感觉映射 (Animation Feel Mapping)

| 感觉 | 运动方向 |
|---------|------------------|
| 戏剧化 / 电影感 (Dramatic / Cinematic) | 慢速淡入淡出、视差、大幅缩放进入 |
| 科技感 / 未来感 (Techy / Futuristic) | 发光、粒子、网格运动、乱码文字 (scramble text) |
| 俏皮 / 友好 (Playful / Friendly) | 弹性缓动、圆角形状、漂浮运动 |
| 专业 / 企业级 (Professional / Corporate) | 微妙的 200-300ms 切换、简洁划过 |
| 冷静 / 极简 (Calm / Minimal) | 非常克制的动作、空白优先 |
| 编辑 / 杂志风格 (Editorial / Magazine) | 强层级感、文字与图片的交错步进 |

## CSS 注意事项：负号函数 (Negating Functions)

严禁这样写：

```css
right: -clamp(28px, 3.5vw, 44px);
margin-left: -min(10vw, 100px);
```

浏览器会静默忽略它们。

请务必改为这样写：

```css
right: calc(-1 * clamp(28px, 3.5vw, 44px));
margin-left: calc(-1 * min(10vw, 100px));
```

## 验证尺寸 (Validation Sizes)

至少在以下尺寸进行测试：
- 桌面端：`1920x1080`、`1440x900`、`1280x720`
- 平板端：`1024x768`、`768x1024`
- 手机端：`375x667`、`414x896`
- 横屏手机：`667x375`、`896x414`

## 反模式 (Anti-Patterns)

不要使用：
- 白底紫色的初创公司模板
- 将 Inter / Roboto / Arial 作为视觉核心（除非用户明确要求极致的中立实用主义）
- 堆满项目符号、极小的字体或需要滚动的代码块
- 当抽象几何图形能更好地完成任务时，使用装饰性插图
