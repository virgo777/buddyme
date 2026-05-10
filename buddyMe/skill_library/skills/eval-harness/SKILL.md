---
name: eval-harness
description: 为 Claude Code 会话提供的正式评测框架，实现了评测驱动开发（EDD）原则
origin: ECC
tools: Read, Write, Edit, Bash, Grep, Glob
---

# 评测工具链（Eval Harness）技能（Skill）

一个用于 Claude Code 会话的正式评测框架，实现了评测驱动开发（Eval-Driven Development, EDD）原则。

## 何时激活

- 为 AI 辅助工作流设置评测驱动开发（EDD）
- 为 Claude Code 任务完成定义通过/失败的标准
- 使用 pass@k 指标衡量智能体（Agent）的可靠性
- 为提示词（Prompt）或智能体（Agent）的变更创建回归测试套件
- 跨模型版本对智能体（Agent）性能进行基准测试

## 核心理念

评测驱动开发（Eval-Driven Development）将评测视为“AI 开发的单元测试”：
- 在实现之**前**定义预期行为
- 在开发过程中持续运行评测
- 追踪每次变更带来的回归（Regression）
- 使用 pass@k 指标进行可靠性衡量

## 评测类型

### 能力评测（Capability Evals）
测试 Claude 是否能够完成之前无法完成的任务：
```markdown
[CAPABILITY EVAL: feature-name]
任务：描述 Claude 应该完成的目标
成功标准：
  - [ ] 标准 1
  - [ ] 标准 2
  - [ ] 标准 3
预期输出：对预期结果的描述
```

### 回归评测（Regression Evals）
确保变更不会破坏现有功能：
```markdown
[REGRESSION EVAL: feature-name]
基线（Baseline）：SHA 或检查点（checkpoint）名称
测试项：
  - existing-test-1: 通过/失败（PASS/FAIL）
  - existing-test-2: 通过/失败（PASS/FAIL）
  - existing-test-3: 通过/失败（PASS/FAIL）
结果：X/Y 通过（之前为 Y/Y）
```

## 评分器（Grader）类型

### 1. 基于代码的评分器（Code-Based Grader）
使用代码进行确定性检查：
```bash
# 检查文件是否包含预期模式
grep -q "export function handleAuth" src/auth.ts && echo "PASS" || echo "FAIL"

# 检查测试是否通过
npm test -- --testPathPattern="auth" && echo "PASS" || echo "FAIL"

# 检查构建是否成功
npm run build && echo "PASS" || echo "FAIL"
```

### 2. 基于模型的评分器（Model-Based Grader）
使用 Claude 评测开放式输出：
```markdown
[MODEL GRADER PROMPT]
评测以下代码变更：
1. 它是否解决了所述问题？
2. 结构是否良好？
3. 是否处理了边缘情况？
4. 错误处理是否得当？

得分：1-5（1=差，5=优秀）
推理：[解释说明]
```

### 3. 人工评分器（Human Grader）
标记以进行人工审查：
```markdown
[HUMAN REVIEW REQUIRED]
变更内容：描述发生了什么变化
原因：为什么需要人工审查
风险等级：低/中/高（LOW/MEDIUM/HIGH）
```

## 指标

### pass@k
“k 次尝试中至少有一次成功”
- pass@1：首次尝试成功率
- pass@3：3 次尝试内的成功率
- 典型目标：pass@3 > 90%

### pass^k
“所有 k 次试验均成功”
- 对可靠性有更高要求
- pass^3：连续 3 次成功
- 用于关键路径

## 评测工作流

### 1. 定义（编码前）
```markdown
## 评测定义：feature-xyz

### 能力评测
1. 可以创建新用户账户
2. 可以验证电子邮件格式
3. 可以安全地对密码进行哈希处理

### 回归评测
1. 现有登录功能仍然正常
2. 会话管理保持不变
3. 注销流程完好无损

### 成功指标
- 对于能力评测：pass@3 > 90%
- 对于回归评测：pass^3 = 100%
```

### 2. 实现
编写代码以通过定义的评测。

### 3. 执行评测
```bash
# 运行能力评测
[运行每项能力评测，记录通过/失败]

# 运行回归评测
npm test -- --testPathPattern="existing"

# 生成报告
```

### 4. 报告
```markdown
评测报告：feature-xyz
========================

能力评测：
  create-user:     通过 (pass@1)
  validate-email:  通过 (pass@2)
  hash-password:   通过 (pass@1)
  总体：           3/3 通过

回归评测：
  login-flow:      通过
  session-mgmt:    通过
  logout-flow:     通过
  总体：           3/3 通过

指标：
  pass@1: 67% (2/3)
  pass@3: 100% (3/3)

状态：准备好进行评审 (READY FOR REVIEW)
```

## 集成模式

### 实现前（Pre-Implementation）
```
/eval define feature-name
```
在 `.claude/evals/feature-name.md` 创建评测定义文件

### 实现过程中（During Implementation）
```
/eval check feature-name
```
运行当前评测并报告状态

### 实现后（Post-Implementation）
```
/eval report feature-name
```
生成完整的评测报告

## 评测存储

在项目中存储评测：
```
.claude/
  evals/
    feature-xyz.md      # 评测定义
    feature-xyz.log     # 评测运行历史
    baseline.json       # 回归基线
```

## 最佳实践

1. **在编码前（BEFORE）定义评测** - 强制对成功标准进行清晰思考
2. **频繁运行评测** - 尽早发现回归
3. **随时间跟踪 pass@k** - 监控可靠性趋势
4. **尽可能使用代码评分器** - 确定性优于概率性
5. **安全相关需人工评审** - 绝不完全自动化安全检查
6. **保持评测快速** - 慢速评测往往不会被运行
7. **将评测与代码一同进行版本控制** - 评测是一等公民资产

## 示例：添加身份验证（Authentication）

```markdown
## EVAL: add-authentication

### 第 1 阶段：定义 (10 分钟)
能力评测：
- [ ] 用户可以使用电子邮件/密码注册
- [ ] 用户可以使用有效凭据登录
- [ ] 无效凭据被拒绝并显示正确错误
- [ ] 页面重新加载后会话依然持久化
- [ ] 注销后清除会话

回归评测：
- [ ] 公共路由仍可访问
- [ ] API 响应保持不变
- [ ] 数据库架构兼容

### 第 2 阶段：实现 (耗时视情况而定)
[编写代码]

### 第 3 阶段：执行评测
运行：/eval check add-authentication

### 第 4 阶段：报告
评测报告：add-authentication
==============================
能力：5/5 通过 (pass@3: 100%)
回归：3/3 通过 (pass^3: 100%)
状态：准予发布 (SHIP IT)
```
