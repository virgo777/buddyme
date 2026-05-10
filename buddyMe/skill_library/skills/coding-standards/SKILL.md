---
name: coding-standards
description: 适用于 TypeScript、JavaScript、React 和 Node.js 开发的通用编码标准、最佳实践和模式。
origin: ECC
---

# 编码标准与最佳实践 (Coding Standards & Best Practices)

适用于所有项目的通用编码标准。

## 何时启用 (When to Activate)

- 启动新项目或模块时
- 为了质量和可维护性进行代码审查（Code Review）时
- 重构现有代码以遵循规范时
- 强制执行命名、格式或结构的一致性时
- 设置 linting、格式化或类型检查规则时
- 引导新贡献者了解编码规范时

## 代码质量原则 (Code Quality Principles)

### 1. 可读性优先 (Readability First)
- 代码被阅读的次数远多于编写的次数
- 变量和函数命名应清晰明确
- 优先选择自描述代码，而非依赖注释
- 保持一致的格式化风格

### 2. KISS 原则 (Keep It Simple, Stupid)
- 采用最简单的可行方案
- 避免过度设计（Over-engineering）
- 不进行过早优化
- 易于理解胜过奇技淫巧

### 3. DRY 原则 (Don't Repeat Yourself)
- 将公共逻辑提取为函数
- 创建可复用的组件
- 在模块间共享工具函数
- 避免“复制粘贴式”编程

### 4. YAGNI 原则 (You Aren't Gonna Need It)
- 不要在功能被需要之前就构建它
- 避免投机性的通用设计
- 仅在必要时增加复杂性
- 从简单开始，在需要时重构

## TypeScript/JavaScript 规范

### 变量命名 (Variable Naming)

```typescript
// ✅ 优：描述性命名
const marketSearchQuery = 'election'
const isUserAuthenticated = true
const totalRevenue = 1000

// ❌ 劣：含义不明
const q = 'election'
const flag = true
const x = 1000
```

### 函数命名 (Function Naming)

```typescript
// ✅ 优：动词-名词模式
async function fetchMarketData(marketId: string) { }
function calculateSimilarity(a: number[], b: number[]) { }
function isValidEmail(email: string): boolean { }

// ❌ 劣：不清晰或仅有名词
async function market(id: string) { }
function similarity(a, b) { }
function email(e) { }
```

### 不可变性模式（关键） (Immutability Pattern)

```typescript
// ✅ 始终使用展开运算符（Spread Operator）
const updatedUser = {
  ...user,
  name: 'New Name'
}

const updatedArray = [...items, newItem]

// ❌ 严禁直接修改（Mutate）
user.name = 'New Name'  // 劣
items.push(newItem)     // 劣
```

### 错误处理 (Error Handling)

```typescript
// ✅ 优：完善的错误处理
async function fetchData(url: string) {
  try {
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Fetch failed:', error)
    throw new Error('Failed to fetch data')
  }
}

// ❌ 劣：没有错误处理
async function fetchData(url) {
  const response = await fetch(url)
  return response.json()
}
```

### Async/Await 最佳实践

```typescript
// ✅ 优：尽可能并行执行
const [users, markets, stats] = await Promise.all([
  fetchUsers(),
  fetchMarkets(),
  fetchStats()
])

// ❌ 劣：非必要的串行执行
const users = await fetchUsers()
const markets = await fetchMarkets()
const stats = await fetchStats()
```

### 类型安全 (Type Safety)

```typescript
// ✅ 优：定义正确的类型
interface Market {
  id: string
  name: string
  status: 'active' | 'resolved' | 'closed'
  created_at: Date
}

function getMarket(id: string): Promise<Market> {
  // 实现代码
}

// ❌ 劣：滥用 'any'
function getMarket(id: any): Promise<any> {
  // 实现代码
}
```

## React 最佳实践

### 组件结构 (Component Structure)

```typescript
// ✅ 优：带类型的函数式组件
interface ButtonProps {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary'
}

export function Button({
  children,
  onClick,
  disabled = false,
  variant = 'primary'
}: ButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`btn btn-${variant}`}
    >
      {children}
    </button>
  )
}

// ❌ 劣：无类型，结构不清晰
export function Button(props) {
  return <button onClick={props.onClick}>{props.children}</button>
}
```

### 自定义 Hook (Custom Hooks)

```typescript
// ✅ 优：可复用的自定义 Hook
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}

// 使用示例
const debouncedQuery = useDebounce(searchQuery, 500)
```

### 状态管理 (State Management)

```typescript
// ✅ 优：正确更新状态
const [count, setCount] = useState(0)

// 基于先前状态的函数式更新
setCount(prev => prev + 1)

// ❌ 劣：直接引用状态
setCount(count + 1)  // 在异步场景下可能会由于闭包导致状态过期
```

### 条件渲染 (Conditional Rendering)

```typescript
// ✅ 优：清晰的条件渲染
{isLoading && <Spinner />}
{error && <ErrorMessage error={error} />}
{data && <DataDisplay data={data} />}

// ❌ 劣：三元运算符嵌套地狱
{isLoading ? <Spinner /> : error ? <ErrorMessage error={error} /> : data ? <DataDisplay data={data} /> : null}
```

## API 设计规范 (API Design Standards)

### REST API 约定 (REST API Conventions)

```
GET    /api/markets              # 列出所有市场
GET    /api/markets/:id          # 获取特定市场
POST   /api/markets              # 创建新市场
PUT    /api/markets/:id          # 更新市场（完整更新）
PATCH  /api/markets/:id          # 更新市场（局部更新）
DELETE /api/markets/:id          # 删除市场

# 用于过滤的查询参数
GET /api/markets?status=active&limit=10&offset=0
```

### 响应格式 (Response Format)

```typescript
// ✅ 优：一致的响应结构
interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  meta?: {
    total: number
    page: number
    limit: number
  }
}

// 成功响应
return NextResponse.json({
  success: true,
  data: markets,
  meta: { total: 100, page: 1, limit: 10 }
})

// 错误响应
return NextResponse.json({
  success: false,
  error: 'Invalid request'
}, { status: 400 })
```

### 输入验证 (Input Validation)

```typescript
import { z } from 'zod'

// ✅ 优：模式（Schema）验证
const CreateMarketSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().min(1).max(2000),
  endDate: z.string().datetime(),
  categories: z.array(z.string()).min(1)
})

export async function POST(request: Request) {
  const body = await request.json()

  try {
    const validated = CreateMarketSchema.parse(body)
    // 使用验证后的数据继续执行
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({
        success: false,
        error: 'Validation failed',
        details: error.errors
      }, { status: 400 })
    }
  }
}
```

## 文件组织 (File Organization)

### 项目结构 (Project Structure)

```
src/
├── app/                    # Next.js App Router (路由)
│   ├── api/               # API 路由
│   ├── markets/           # 市场页面
│   └── (auth)/           # 认证页面 (路由分组)
├── components/            # React 组件
│   ├── ui/               # 通用 UI 组件
│   ├── forms/            # 表单组件
│   └── layouts/          # 布局组件
├── hooks/                # 自定义 React hooks
├── lib/                  # 工具函数和配置
│   ├── api/             # API 客户端
│   ├── utils/           # 辅助函数
│   └── constants/       # 常量
├── types/                # TypeScript 类型定义
└── styles/              # 全局样式
```

### 文件命名 (File Naming)

```
components/Button.tsx          # 组件使用 PascalCase (大驼峰)
hooks/useAuth.ts              # 使用 camelCase (小驼峰) 并以 'use' 开头
lib/formatDate.ts             # 工具函数使用 camelCase
types/market.types.ts         # 使用 camelCase 并带上 .types 后缀
```

## 注释与文档 (Comments & Documentation)

### 何时编写注释 (When to Comment)

```typescript
// ✅ 优：解释“为什么”，而不是“是什么”
// 在发生停机时，使用指数退避算法以避免给 API 造成过大压力
const delay = Math.min(1000 * Math.pow(2, retryCount), 30000)

// 为了优化大数组的性能，这里特意使用了直接修改（Mutation）
items.push(newItem)

// ❌ 劣：陈述显而易见的事实
// 将计数器加 1
count++

// 将名称设置为用户的名称
name = user.name
```

### 针对公共 API 的 JSDoc (JSDoc for Public APIs)

```typescript
/**
 * 使用语义相似度搜索市场。
 *
 * @param query - 自然语言搜索查询
 * @param limit - 最大结果数 (默认值: 10)
 * @returns 按相似度评分排序的市场数组
 * @throws {Error} 如果 OpenAI API 失败或 Redis 不可用
 *
 * @example
 * ```typescript
 * const results = await searchMarkets('election', 5)
 * console.log(results[0].name) // "Trump vs Biden"
 * ```
 */
export async function searchMarkets(
  query: string,
  limit: number = 10
): Promise<Market[]> {
  // 实现代码
}
```

## 性能最佳实践 (Performance Best Practices)

### 记忆化 (Memoization)

```typescript
import { useMemo, useCallback } from 'react'

// ✅ 优：记忆化昂贵的计算
const sortedMarkets = useMemo(() => {
  return markets.sort((a, b) => b.volume - a.volume)
}, [markets])

// ✅ 优：记忆化回调函数
const handleSearch = useCallback((query: string) => {
  setSearchQuery(query)
}, [])
```

### 延迟加载 (Lazy Loading)

```typescript
import { lazy, Suspense } from 'react'

// ✅ 优：延迟加载大型组件
const HeavyChart = lazy(() => import('./HeavyChart'))

export function Dashboard() {
  return (
    <Suspense fallback={<Spinner />}>
      <HeavyChart />
    </Suspense>
  )
}
```

### 数据库查询 (Database Queries)

```typescript
// ✅ 优：仅选择需要的列
const { data } = await supabase
  .from('markets')
  .select('id, name, status')
  .limit(10)

// ❌ 劣：全量查询
const { data } = await supabase
  .from('markets')
  .select('*')
```

## 测试规范 (Testing Standards)

### 测试结构 (AAA 模式) (Test Structure (AAA Pattern))

```typescript
test('calculates similarity correctly', () => {
  // 安排 (Arrange)
  const vector1 = [1, 0, 0]
  const vector2 = [0, 1, 0]

  // 执行 (Act)
  const similarity = calculateCosineSimilarity(vector1, vector2)

  // 断言 (Assert)
  expect(similarity).toBe(0)
})
```

### 测试命名 (Test Naming)

```typescript
// ✅ 优：描述性的测试名称
test('returns empty array when no markets match query', () => { })
test('throws error when OpenAI API key is missing', () => { })
test('falls back to substring search when Redis unavailable', () => { })

// ❌ 劣：模糊的测试名称
test('works', () => { })
test('test search', () => { })
```

## 代码异味（Code Smell）检测

注意以下反模式（Anti-patterns）：

### 1. 过长函数 (Long Functions)
```typescript
// ❌ 劣：函数长度 > 50 行
function processMarketData() {
  // 100 行代码
}

// ✅ 优：拆分为更小的函数
function processMarketData() {
  const validated = validateData()
  const transformed = transformData(validated)
  return saveData(transformed)
}
```

### 2. 过深嵌套 (Deep Nesting)
```typescript
// ❌ 劣：5 层以上嵌套
if (user) {
  if (user.isAdmin) {
    if (market) {
      if (market.isActive) {
        if (hasPermission) {
          // 执行操作
        }
      }
    }
  }
}

// ✅ 优：及早返回 (Early Returns)
if (!user) return
if (!user.isAdmin) return
if (!market) return
if (!market.isActive) return
if (!hasPermission) return

// 执行操作
```

### 3. 魔数 (Magic Numbers)
```typescript
// ❌ 劣：未解释的数字
if (retryCount > 3) { }
setTimeout(callback, 500)

// ✅ 优：命名常量
const MAX_RETRIES = 3
const DEBOUNCE_DELAY_MS = 500

if (retryCount > MAX_RETRIES) { }
setTimeout(callback, DEBOUNCE_DELAY_MS)
```

**记住**：代码质量不容妥协。清晰、可维护的代码是实现快速开发和自信重构的基石。
