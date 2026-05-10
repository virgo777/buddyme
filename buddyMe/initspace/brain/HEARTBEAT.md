# 心跳任务执行规范；定时任务执行规范；

## 项目路径
- 对话记录: initspace/memorys/conversation_log.json
- 用户描述: initspace/brain/USER.md
- 心跳配置: initspace/memorys/heartbeat.json
- 记忆摘要: initspace/memorys/memory_summary.md

## 基本规则
- 收到心跳触发信号后，依次检查每个任务是否满足执行条件
- 无需执行任何任务时，直接返回 HEARTBEAT_OK，不发通知
- 任务执行结果简短记录，不打扰用户
- 直接用上面给出的路径读取文件，不要用 bash 查找路径

## 记忆更新任务
1. 读取 initspace/memorys/conversation_log.json 最近对话
2. 提取用户画像、偏好、需求变化
3. 用 write_file 更新 initspace/memorys/memory_summary.md
4. 返回更新摘要
