"""initspace — Agent 运行时初始化与状态子系统包。

承载 Agent 启动后所需的运行时能力：
- contextbuild：分层 system prompt 动态构建（SOUL / IDENTITY / AGENT + 工具 Schema）
- skill_loader：Skill 三层渐进式发现与加载
- memorybuild / memory_extractor / use_memory：记忆的构建、抽取与检索
- heartbeat / loop_*：心跳与循环（定时）任务
- todo_manager：待办事项管理
"""
