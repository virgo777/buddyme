---
name: api-design
description: 生产级 API 的 REST API 设计模式，包括资源命名、状态码、分页、过滤、错误响应、版本控制和速率限制。
origin: ECC
---

# API 设计模式 (API Design Patterns)

设计一致且开发者友好的 REST API 的规范与最佳实践。

## 何时启用

- 设计新的 API 端点 (Endpoints)
- 审查现有的 API 合约 (Contracts)
- 添加分页、过滤或排序功能
- 为 API 实现错误处理
- 规划 API 版本控制策略
- 构建公开或面向合作伙伴的 API

## 资源设计 (Resource Design)

### URL 结构

```
# 资源是名词、复数、小写、短横线命名 (kebab-case)
GET    /api/v1/users
GET    /api/v1/users/:id
POST   /api/v1/users
PUT    /api/v1/users/:id
PATCH  /api/v1/users/:id
DELETE /api/v1/users/:id

# 关系子资源
GET    /api/v1/users/:id/orders
POST   /api/v1/users/:id/orders

# 不属于 CRUD 的操作（谨慎使用动词）
POST   /api/v1/orders/:id/cancel
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
```

### 命名规则

```
# 正确示例 (GOOD)
/api/v1/team-members          # 多单词资源使用 kebab-case
/api/v1/orders?status=active  # 使用查询参数进行过滤
/api/v1/users/123/orders      # 嵌套资源表示所属关系

# 错误示例 (BAD)
/api/v1/getUsers              # URL 中包含动词
/api/v1/user                  # 使用单数（应使用复数）
/api/v1/team_members          # URL 中使用 snake_case
/api/v1/users/123/getOrders   # 嵌套资源中包含动词
```

## HTTP 方法与状态码

### 方法语义 (Method Semantics)

| 方法 (Method) | 幂等 (Idempotent) | 安全 (Safe) | 用途 |
|--------|-----------|------|---------|
| GET | 是 | 是 | 获取资源 |
| POST | 否 | 否 | 创建资源，触发操作 |
| PUT | 是 | 否 | 完整替换资源 |
| PATCH | 否* | 否 | 部分更新资源 |
| DELETE | 是 | 否 | 删除资源 |

*如果实现得当，PATCH 也可以实现为幂等的。

### 状态码参考

```
# 成功 (Success)
200 OK                    — GET, PUT, PATCH（包含响应正文）
201 Created               — POST（需包含 Location 标头）
204 No Content            — DELETE, PUT（无响应正文）

# 客户端错误 (Client Errors)
400 Bad Request           — 验证失败、JSON 格式错误
401 Unauthorized          — 缺失或无效的身份验证
403 Forbidden             — 已身份验证但无权访问
404 Not Found             — 资源不存在
409 Conflict              — 重复条目、状态冲突
422 Unprocessable Entity  — 语义无效（JSON 合法，但数据有误）
429 Too Many Requests     — 超出速率限制

# 服务器错误 (Server Errors)
500 Internal Server Error — 意外故障（绝不要暴露详细信息）
502 Bad Gateway           — 上游服务故障
503 Service Unavailable   — 临时过载，包含 Retry-After 标头
```

### 常见错误

```
# 错误：所有响应都返回 200
{ "status": 200, "success": false, "error": "Not found" }

# 正确：语义化使用 HTTP 状态码
HTTP/1.1 404 Not Found
{ "error": { "code": "not_found", "message": "User not found" } }

# 错误：验证错误返回 500
# 正确：返回 400 或 422，并附带字段级详细信息

# 错误：创建资源返回 200
# 正确：返回 201 并在 Location 标头中包含路径
HTTP/1.1 201 Created
Location: /api/v1/users/abc-123
```

## 响应格式 (Response Format)

### 成功响应

```json
{
  "data": {
    "id": "abc-123",
    "email": "alice@example.com",
    "name": "Alice",
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

### 集合响应（带分页）

```json
{
  "data": [
    { "id": "abc-123", "name": "Alice" },
    { "id": "def-456", "name": "Bob" }
  ],
  "meta": {
    "total": 142,
    "page": 1,
    "per_page": 20,
    "total_pages": 8
  },
  "links": {
    "self": "/api/v1/users?page=1&per_page=20",
    "next": "/api/v1/users?page=2&per_page=20",
    "last": "/api/v1/users?page=8&per_page=20"
  }
}
```

### 错误响应

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Must be a valid email address",
        "code": "invalid_format"
      },
      {
        "field": "age",
        "message": "Must be between 0 and 150",
        "code": "out_of_range"
      }
    ]
  }
}
```

### 响应封装变体

```typescript
// 选项 A：带数据包装器的封装（推荐用于公开 API）
interface ApiResponse<T> {
  data: T;
  meta?: PaginationMeta;
  links?: PaginationLinks;
}

interface ApiError {
  error: {
    code: string;
    message: string;
    details?: FieldError[];
  };
}

// 选项 B：扁平化响应（较简单，常用于内部 API）
// 成功：直接返回资源
// 错误：返回错误对象
// 通过 HTTP 状态码进行区分
```

## 分页 (Pagination)

### 基于偏移量 (Offset-Based) - 简单

```
GET /api/v1/users?page=2&per_page=20

# 实现
SELECT * FROM users
ORDER BY created_at DESC
LIMIT 20 OFFSET 20;
```

**优点：** 易于实现，支持“跳转到第 N 页”。
**缺点：** 偏移量较大时性能较差 (OFFSET 100000)，且在并发插入时可能出现不一致。

### 基于游标 (Cursor-Based) - 可扩展

```
GET /api/v1/users?cursor=eyJpZCI6MTIzfQ&limit=20

# 实现
SELECT * FROM users
WHERE id > :cursor_id
ORDER BY id ASC
LIMIT 21;  -- 多获取一个以确定是否有下一页 (has_next)
```

```json
{
  "data": [...],
  "meta": {
    "has_next": true,
    "next_cursor": "eyJpZCI6MTQzfQ"
  }
}
```

**优点：** 无论位置如何，性能保持一致；并发插入时稳定。
**缺点：** 无法跳转到任意页码，游标是不透明的。

### 何时使用哪种方式

| 使用场景 | 分页类型 |
|----------|----------------|
| 管理后台、小型数据集 (<10K) | 偏移量 (Offset) |
| 无限滚动、Feed 流、大型数据集 | 游标 (Cursor) |
| 公开 API | 默认使用游标 (Cursor)，可选偏移量 (Offset) |
| 搜索结果 | 偏移量 (Offset)（用户通常期望看到页码） |

## 过滤、排序与搜索 (Filtering, Sorting, and Search)

### 过滤 (Filtering)

```
# 简单等值匹配
GET /api/v1/orders?status=active&customer_id=abc-123

# 比较运算符（使用方括号标记）
GET /api/v1/products?price[gte]=10&price[lte]=100
GET /api/v1/orders?created_at[after]=2025-01-01

# 多个值（逗号分隔）
GET /api/v1/products?category=electronics,clothing

# 嵌套字段（点标记法）
GET /api/v1/orders?customer.country=US
```

### 排序 (Sorting)

```
# 单个字段（前缀 - 表示降序）
GET /api/v1/products?sort=-created_at

# 多个字段（逗号分隔）
GET /api/v1/products?sort=-featured,price,-created_at
```

### 全文搜索 (Full-Text Search)

```
# 搜索查询参数
GET /api/v1/products?q=wireless+headphones

# 特定字段搜索
GET /api/v1/users?email=alice
```

### 稀疏字段集 (Sparse Fieldsets)

```
# 仅返回指定的字段（减少数据传输量）
GET /api/v1/users?fields=id,name,email
GET /api/v1/orders?fields=id,total,status&include=customer.name
```

## 身份验证与授权 (Authentication and Authorization)

### 基于令牌的身份验证 (Token-Based Auth)

```
# Authorization 标头中的 Bearer 令牌
GET /api/v1/users
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# API 密钥（用于服务器对服务器通信）
GET /api/v1/data
X-API-Key: sk_live_abc123
```

### 授权模式 (Authorization Patterns)

```typescript
// 资源级别：检查所有权
app.get("/api/v1/orders/:id", async (req, res) => {
  const order = await Order.findById(req.params.id);
  if (!order) return res.status(404).json({ error: { code: "not_found" } });
  if (order.userId !== req.user.id) return res.status(403).json({ error: { code: "forbidden" } });
  return res.json({ data: order });
});

// 基于角色：检查权限
app.delete("/api/v1/users/:id", requireRole("admin"), async (req, res) => {
  await User.delete(req.params.id);
  return res.status(204).send();
});
```

## 速率限制 (Rate Limiting)

### 响应标头 (Headers)

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000

# 当超出限制时
HTTP/1.1 429 Too Many Requests
Retry-After: 60
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Try again in 60 seconds."
  }
}
```

### 速率限制分级 (Rate Limit Tiers)

| 级别 (Tier) | 限制 | 窗口 | 使用场景 |
|------|-------|--------|----------|
| 匿名 (Anonymous) | 30/min | 每 IP | 公开端点 |
| 已认证 (Authenticated) | 100/min | 每用户 | 标准 API 访问 |
| 高级 (Premium) | 1000/min | 每 API 密钥 | 付费 API 方案 |
| 内部 (Internal) | 10000/min | 每服务 | 服务间调用 |

## 版本控制 (Versioning)

### URL 路径版本控制（推荐）

```
/api/v1/users
/api/v2/users
```

**优点：** 显式、易于路由、可缓存。
**缺点：** 版本间 URL 会发生变化。

### 标头版本控制 (Header Versioning)

```
GET /api/users
Accept: application/vnd.myapp.v2+json
```

**优点：** URL 整洁。
**缺点：** 较难测试，容易遗忘。

### 版本控制策略

```
1. 从 /api/v1/ 开始 —— 在确实需要之前不要进行版本控制
2. 最多维护 2 个活跃版本（当前版本 + 上一个版本）
3. 弃用时间线：
   - 宣布弃用（公开 API 通常提前 6 个月通知）
   - 添加 Sunset 标头：Sunset: Sat, 01 Jan 2026 00:00:00 GMT
   - 在 Sunset 日期后返回 410 Gone
4. 非破坏性更改不需要新版本：
   - 在响应中添加新字段
   - 添加新的可选查询参数
   - 添加新的端点
5. 破坏性更改需要新版本：
   - 删除或重命名字段
   - 更改字段类型
   - 更改 URL 结构
   - 更改身份验证方法
```

## 实现模式 (Implementation Patterns)

### TypeScript (Next.js API Route)

```typescript
import { z } from "zod";
import { NextRequest, NextResponse } from "next/server";

const createUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
});

export async function POST(req: NextRequest) {
  const body = await req.json();
  const parsed = createUserSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json({
      error: {
        code: "validation_error",
        message: "Request validation failed",
        details: parsed.error.issues.map(i => ({
          field: i.path.join("."),
          message: i.message,
          code: i.code,
        })),
      },
    }, { status: 422 });
  }

  const user = await createUser(parsed.data);

  return NextResponse.json(
    { data: user },
    {
      status: 201,
      headers: { Location: `/api/v1/users/${user.id}` },
    },
  );
}
```

### Python (Django REST Framework)

```python
from rest_framework import serializers, viewsets, status
from rest_framework.response import Response

class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=100)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "created_at"]

class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateUserSerializer
        return UserSerializer

    def create(self, request):
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.create(**serializer.validated_data)
        return Response(
            {"data": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
            headers={"Location": f"/api/v1/users/{user.id}"},
        )
```

### Go (net/http)

```go
func (h *UserHandler) CreateUser(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        writeError(w, http.StatusBadRequest, "invalid_json", "Invalid request body")
        return
    }

    if err := req.Validate(); err != nil {
        writeError(w, http.StatusUnprocessableEntity, "validation_error", err.Error())
        return
    }

    user, err := h.service.Create(r.Context(), req)
    if err != nil {
        switch {
        case errors.Is(err, domain.ErrEmailTaken):
            writeError(w, http.StatusConflict, "email_taken", "Email already registered")
        default:
            writeError(w, http.StatusInternalServerError, "internal_error", "Internal error")
        }
        return
    }

    w.Header().Set("Location", fmt.Sprintf("/api/v1/users/%s", user.ID))
    writeJSON(w, http.StatusCreated, map[string]any{"data": user})
}
```

## API 设计自检清单 (API Design Checklist)

在发布新端点之前：

- [ ] 资源 URL 遵循命名规范（复数、kebab-case、无动词）
- [ ] 使用了正确的 HTTP 方法（GET 用于读取，POST 用于创建等）
- [ ] 返回了适当的状态码（不要对所有内容都返回 200）
- [ ] 使用 Schema（Zod, Pydantic, Bean Validation）验证输入
- [ ] 错误响应遵循带代码和消息的标准格式
- [ ] 为列表端点实现分页（游标或偏移量）
- [ ] 要求身份验证（或明确标记为公开）
- [ ] 检查授权（用户只能访问自己的资源）
- [ ] 配置了速率限制
- [ ] 响应不泄露内部细节（堆栈跟踪、SQL 错误）
- [ ] 命名与现有端点保持一致（camelCase 与 snake_case）
- [ ] 已归档（更新了 OpenAPI/Swagger 规范）
