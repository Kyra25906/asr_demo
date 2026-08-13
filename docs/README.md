# asr_demo 文档入口

最后维护：2026-08-12

## 现行文档及唯一职责

| 文档 | 唯一职责 | 更新时机 |
|---|---|---|
| `PROJECT_TASK_CHECKLIST.md` | 当前状态、优先级、任务依赖和验收门槛的唯一来源 | 每轮任务状态变化 |
| `NEXT_SESSION_HANDOFF_2026-08-09.md` | 下一会话快速恢复，只保留当前停点、风险和命令 | 每轮结束 |
| `PROJECT_ARCHITECTURE.md` | 稳定模块边界、数据流、设计原因和目标架构 | 架构边界变化 |
| `ENVIRONMENT_SETUP.md` | Python、依赖、配置和环境验证命令 | 运行环境变化 |
| `OUTPUT_PRESENTATION_POLICY.md` | 屏幕、语音、调试和记录的输出政策 | 展示合同变化 |

## 历史快照

以下文件保留当时决策和验收证据，不再描述当前状态：

- `PROJECT_STATUS_2026-08-05.md`
- `DEVELOPMENT_HANDOFF_2026-08-06.md`

遇到冲突时，采用以下优先顺序：

```text
PROJECT_TASK_CHECKLIST（当前事实）
→ NEXT_SESSION_HANDOFF（当前摘要）
→ PROJECT_ARCHITECTURE / OUTPUT_PRESENTATION_POLICY / ENVIRONMENT_SETUP（稳定规范）
→ 日期历史快照（只作追溯）
```

## 当前方向

```text
MAIN-FLAG-INVARIANT-01
→ MAIN-EVIDENCE-COMMIT-01
→ MAIN-SESSION-CONTEXT-01
→ INTENT-02 五步清理
→ Query / Safety / Knowledge 类型合同
→ QUERY 第四分支与只读分派
→ PRESENT 稳定后接真实安全规则、设备查询和 RAG
```

原因：先保证当前主流程只有合法配置、证据先于状态、会话上下文不断链；再删除新旧双轨；最后扩展未来能力。否则查询、安全和 RAG 会复制当前过渡层问题。
