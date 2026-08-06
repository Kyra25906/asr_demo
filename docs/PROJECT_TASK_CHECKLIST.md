# asr_demo 项目任务清单

最后更新：2026-08-06

真实项目：`C:\Users\dahli\Desktop\asr_demo`

## 1. 使用规则

本文件是项目推进的唯一任务总表。每轮开发和真实验收结束后都要更新。

状态定义：

| 状态 | 含义 |
|---|---|
| `TODO` | 尚未开始 |
| `DESIGN` | 正在定义数据结构或接口 |
| `CODED` | 代码已完成，但自动测试尚未全部通过 |
| `AUTO_OK` | 单元/集成/回归测试通过，但尚未真实环境验收 |
| `REAL_OK` | 已使用真实麦克风、ASR、LLM 或完整流程验收 |
| `BLOCKED` | 存在明确阻塞条件 |

状态升级必须有证据：

```text
TODO → DESIGN → CODED → AUTO_OK → REAL_OK
```

不能因为“代码看起来正确”直接标记为 `REAL_OK`。

## 2. 当前测试基线

- 全量自动测试：`79 tests OK`
- 最近真实连续口述会话：`20260806_102742`
- 真实会话已验证：7 段连续口述、后台 DeepSeek、事件分类、指标保存、结束指令。

恢复工作时先运行：

```powershell
cd C:\Users\dahli\Desktop\asr_demo

.\.venv\Scripts\python.exe -B -m unittest discover `
    -s tests `
    -v
```

## 3. 当前唯一下一项

> `PRESENT-01`：定义统一的用户消息数据结构，先把“内容、渠道、优先级、来源”固定下来。

在该项达到 `AUTO_OK` 前，不同时推进 main 接入、即时回复或 TTS。

## 4. 任务总表

### A. 音频、唤醒与 ASR 基础

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `AUDIO-01` | 麦克风录音和 WAV 保存 | `REAL_OK` | 多次真实口述已生成 `audio/recordings/*.wav` |
| `VAD-01` | 检测开始说话和自然停顿 | `REAL_OK` | 真实日志包含“检测到人声/检测到说话结束” |
| `KWS-01` | 离线唤醒“小科小科” | `REAL_OK` | 真实日志多次唤醒成功 |
| `ASR-01` | FunASR/SenseVoice 中文识别 | `REAL_OK` | 真实实验口述已识别并保存 |
| `ASR-02` | 专业词错误保留原文 | `REAL_OK` | “一液枪/微生”等原文未被覆盖 |
| `ASR-03` | 建立实验专业词固定评测集 | `TODO` | 真实验收发现专业词错词较多；需固定音频、期望文本和错词统计 |
| `ASR-04` | 专业词热词/文本后处理对照实验 | `TODO` | 当前识别调用未传热词；必须在 ASR-03 后比较，且保留模型原文 |
| `ASR-05` | 固定中文语言参数对照测试 | `TODO` | 当前 `language="auto"`；先核对安装版本支持值，再比较准确率 |
| `MODEL-LOAD-01` | ASR 和唤醒模型在进程内只加载一次 | `REAL_OK` | 当前 `main()` 启动时创建一次并跨会话复用 |

### B. LLM 结构化与降级

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `LLM-01` | 统一 LLMClient 接口 | `REAL_OK` | DeepSeek 真实请求通过 |
| `LLM-02` | 严格 JSON 协议和额外字段拒绝 | `REAL_OK` | 自动测试通过；真实结构化成功 |
| `LLM-03` | 保留 raw_text，不直接覆盖 ASR | `REAL_OK` | 真实事件同时保留 raw/normalized |
| `LLM-04` | 空响应、超时、429、5xx 有限重试 | `AUTO_OK` | 重试单测通过；尚缺真实故障注入验收 |
| `LLM-05` | DeepSeek 关闭 thinking 模式 | `REAL_OK` | 真实日志 `thinking.type=disabled` |
| `LLM-06` | 尝试次数和处理耗时 | `REAL_OK` | 真实 JSONL 含 attempts/seconds |
| `LLM-07` | 操作、观察、测量、异常分类 | `REAL_OK` | 会话 `20260806_102742` 四类结果正确 |
| `LLM-08` | 缺少关键参数时产生追问 | `REAL_OK` | “将溶液加热”产生温度/时间追问 |
| `LLM-09` | 阶段总结接口 | `AUTO_OK` | processor/validation 单测通过，未接主流程 |
| `LLM-10` | 会话结束总结接入 | `TODO` | 依赖确认收尾流程 |

### C. 后台队列与会话上下文

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `QUEUE-01` | LLM 后台处理，录音可继续 | `REAL_OK` | 真实日志显示 LLM 请求期间仍在录音 |
| `QUEUE-02` | 单线程顺序保证 | `AUTO_OK` | 队列顺序测试通过 |
| `QUEUE-03` | 最大积压和背压 | `AUTO_OK` | backpressure 测试通过 |
| `QUEUE-04` | 会话结束优雅等待 | `REAL_OK` | 真实结束时等待剩余任务完成 |
| `CTX-01` | 最近事件上下文 | `REAL_OK` | 上下文进入真实提示词，单测通过 |
| `CTX-02` | NOTE 使用 raw_text | `AUTO_OK` | SessionContext 单测通过 |

### D. 存储、会话与导出

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `STORE-01` | ASR JSONL 保存 | `REAL_OK` | 真实会话记录存在 |
| `STORE-02` | 实验事件 JSONL 保存 | `REAL_OK` | `experiment_events.jsonl` 已核验 |
| `STORE-03` | 事件可追溯到 session/segment | `REAL_OK` | 真实事件 source id 正确 |
| `STORE-04` | LLM 降级元数据保存 | `REAL_OK` | 真实历史日志出现降级 NOTE |
| `SESSION-01` | 每次实验使用独立 session_id | `REAL_OK` | 会话编号已进入 ASR/事件记录 |
| `SESSION-02` | 按 session_id 查询完整实验 | `TODO` | 尚无统一查询命令 |
| `EXPORT-01` | 导出单次实验 Markdown/JSON | `TODO` | TTS 前建议完成第一版 |
| `EXPORT-02` | 导出报告文档 | `TODO` | 后期白名单工具功能 |

### E. 待确认与回复协调

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `CLARIFY-01` | PendingClarification 数据结构 | `AUTO_OK` | 单元测试通过 |
| `CLARIFY-02` | ReplyCoordinator 登记和部分解决 | `AUTO_OK` | 单元测试通过 |
| `CLARIFY-03` | 每个安全间隙最多一条回复 | `AUTO_OK` | main 集成测试通过，尚缺真实验收 |
| `CLARIFY-04` | 回复带来源段号和原文 | `AUTO_OK` | main 集成测试通过，尚缺真实验收 |
| `CLARIFY-05` | 会话结束显示遗留项 | `AUTO_OK` | 已接 main，尚缺真实验收 |
| `CLARIFY-06` | 明确肯定答复关闭最早 ASR 确认项 | `REAL_OK` | 会话 `20260806_203255` 已用真实语音关闭第 1 段确认项 |
| `CLARIFY-07` | 否定并提供修正内容 | `TODO` | 当前“不是”不会自动关闭 |
| `CLARIFY-08` | 问题优先级、合并、过期 | `TODO` | 当前主要按最早段号 |
| `CLARIFY-09` | 待确认项支持暂缓、回看和稳定编号 | `DESIGN` | 跳过不删除；协调 ACTIVE、DEFERRED、RESOLVED、EXPIRED 与新问题 |
| `CLARIFY-TARGET-01` | 用户按问题编号指定回答目标 | `TODO` | 支持“问题2”“第二个问题”；只用确定性规则，不让 LLM 猜测 |
| `CLARIFY-TARGET-02` | 用户按实验步骤或唯一主题指定回答目标 | `TODO` | 支持“第2步”“离心时间”；匹配不唯一时必须追问，不自动选择 |
| `COMMAND-01` | 定义统一 InteractionCommand 与命令解析器 | `DESIGN` | 从 main/ReplyCoordinator 抽离结束、暂缓、查看、肯定、否定和指定问题的文本识别；原始ASR必须先保存 |

### F. 确认答复持久化与主流程

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `CONF-STORE-01` | ConfirmationRecord 数据结构 | `REAL_OK` | 会话 `20260806_203255` 生成真实确认记录 |
| `CONF-STORE-02` | ConfirmationStore JSONL 保存 | `REAL_OK` | confirmations JSONL 已保存真实肯定答复 |
| `CONF-MAIN-01` | ASR 确认答复接入 main | `REAL_OK` | 真实语音答复已完成 prepare/save/commit |
| `CONF-MAIN-02` | 确认成功终端反馈 | `REAL_OK` | 真实流程显示“已保存对第 1 段的确认答复” |
| `CONF-MAIN-03` | 确认答复不作为普通实验事件 | `REAL_OK` | ASR 共 4 条、实验事件仅 3 条，确认答复只进入确认记录 |

### G. 回复时机与会话收尾

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `TIMING-01` | LLM 完成后不必等下一段才显示 | `TODO` | 当前被阻塞式录音等待延迟 |
| `TIMING-02` | 用户正在说话时不输出/播放回复 | `TODO` | TTS 前硬性依赖 |
| `TIMING-03` | 明确安全回复判断接口 | `TODO` | 供终端和未来 TTS 共用 |
| `CLOSING-01` | 增加 CONFIRMING 收尾阶段 | `TODO` | 结束记录后仍可回答遗留项 |
| `CLOSING-02` | “跳过确认/直接结束”指令 | `TODO` | 避免无法退出收尾阶段 |
| `CLOSING-03` | 全部确认完成后进入 IDLE | `TODO` | 状态机集成测试和真实验收 |

### H. TTS 前稳定性验收

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `STABILITY-01` | 连续至少 10 段实验口述 | `TODO` | 检查顺序、丢失、积压和延迟 |
| `STABILITY-02` | 空响应/网络失败真实降级演练 | `TODO` | 原始数据不得丢失 |
| `STABILITY-03` | 确认答复完整真实闭环 | `TODO` | 包含肯定、否定和遗留项 |
| `STABILITY-04` | 会话结束总结和记录核验 | `TODO` | 结束后结果可使用 |

### H2. 用户输出与呈现策略

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `PRESENT-01` | 定义 PresentationMessage 数据结构 | `CODED` | 10项协议单测通过；移除RECORD消息渠道，增加ScreenTarget；待项目venv全量回归 |
| `PRESENT-02` | 当前回答回执优先于旧后台追问 | `TODO` | 会话 20260806_203255 暴露顺序混乱 |
| `PRESENT-03` | 按认知负担预算组成语音消息组 | `DESIGN` | 默认最多2条、50字、1个问题；支持“回执+相关问题” |
| `PRESENT-04` | 内部口述编号与用户实验步骤编号分离 | `TODO` | 确认答复占号导致实验步骤从2跳到4 |
| `PRESENT-05` | 用户输出与 debug 日志分离 | `TODO` | 状态、路径、token、耗时默认不展示/不朗读 |
| `PRESENT-06` | 输出顺序真实验收 | `TODO` | 先确认回执，再在后续安全间隙提出新问题 |

### H3. 系统故障与实验安全

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `SAFETY-01` | 定义系统故障分类和严重程度 | `TODO` | 区分问题类型、严重程度、消息优先级；先覆盖可由程序确定的故障 |
| `SAFETY-02` | 将确定的存储/音频故障转换为用户消息 | `TODO` | 存储不可写等关键故障必须明确提醒；可降级故障不得冒充严重危险 |
| `SAFETY-03` | 确定 Demo 实验后建立风险规则白名单 | `TODO` | Demo、SOP 和术语尚未确定，当前不提前绑定具体实验风险规则 |
| `SAFETY-04` | 实验风险提示的证据等级与确认流程 | `TODO` | 区分 confirmed、suspected、unknown；疑似 ASR 错词不得直接判定危险 |

### I. TTS 与后续阶段

| ID | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|
| `TTS-01` | 定义 TTSClient 接口 | `TODO` | 先假客户端单测 |
| `TTS-02` | 系统 TTS 第一版 | `TODO` | 不先接 GPT-SoVITS |
| `TTS-03` | 增加 SPEAKING 状态 | `TODO` | 播放期间暂停 KWS/VAD |
| `TTS-04` | 分句播放、失败降级 | `TODO` | TTS 失败回退终端文本 |
| `TTS-05` | 用户打断策略 | `TODO` | 需要状态机和音频资源管理 |
| `TTS-06` | 唤醒提示替换为“我在，请说” | `TODO` | 系统 TTS 稳定后 |
| `SOVITS-01` | GPT-SoVITS HTTP 服务 | `TODO` | TTS 第一版之后 |
| `SOVITS-02` | 超时、缓存、系统 TTS 回退 | `TODO` | 外部服务失败不影响主流程 |
| `LIVE2D-01` | Live2D 表现层接入 | `TODO` | TTS 稳定后 |
| `AGENT-01` | 白名单计时器/提醒/查询/导出 | `TODO` | TTS 与记录闭环后 |

## 5. TTS 开始条件

以下任务至少达到指定状态后，才开始 `TTS-01`：

| 前置任务 | 最低状态 |
|---|---|
| `CONF-STORE-01/02` | `AUTO_OK` |
| `CONF-MAIN-01/02/03` | `REAL_OK` |
| `TIMING-01/02/03` | `REAL_OK` |
| `CLOSING-01/02/03` | `REAL_OK` |
| `CLARIFY-07` | 至少 `AUTO_OK` |
| `LLM-10` | 至少 `AUTO_OK` |
| `STABILITY-01` | `REAL_OK` |
| `STABILITY-03` | `REAL_OK` |
| `PRESENT-01/02/03/04/05/06` | `REAL_OK` |
| `SESSION-02` | 至少 `AUTO_OK` |
| `EXPORT-01` | 至少 `AUTO_OK`，并完成一次真实会话导出验收 |
| `SAFETY-01/02` | 至少 `AUTO_OK` |

### TTS 前的功能推进顺序

第一版系统 TTS 不应早于实验记录闭环。当前固定顺序为：

```text
PRESENT-01～06 输出协调
    ↓
CLARIFY-09 暂缓、回看和稳定编号
    ↓
CLARIFY-TARGET-01/02 指定回答目标
    ↓
否定修正与确认收尾
    ↓
会话结束总结
    ↓
SESSION-02 按 session_id 聚合
    ↓
EXPORT-01 Markdown/JSON 第一版导出
    ↓
TTS-01 统一接口与系统 TTS
    ↓
EXPORT-02 Word/PDF 报告美化
```

TTS 前至少完成 `SessionRecord` 聚合和 Markdown/JSON 第一版导出，用来证明：

```text
口述 → 识别 → 结构化 → 确认 → 总结 → 可用记录
```

Word/PDF 属于表现层增强，可以在系统 TTS 之后完成。

## 6. 维护日志

| 日期 | 变更 | 自动测试 | 真实验收 | 下一项 |
|---|---|---:|---|---|
| 2026-08-06 | 建立任务总表；整理当前完成度 | 65 tests OK | 使用既有会话证据 | `CONF-STORE-01` |
| 2026-08-06 | 建立 ConfirmationRecord 与 ConfirmationStore | 73 tests OK | 未进行真实写入验收 | `CONF-MAIN-01` |
| 2026-08-06 | 明确肯定答复以两阶段方式接入 main | 79 tests OK | 等待真实口述与三份JSONL核验 | `CONF-MAIN-01/02/03` |
| 2026-08-06 | 真实验收发现实验专业词错词较多 | 未改代码 | 当前 SenseVoiceSmall 未配置专业词增强 | 先完成确认闭环验收，再做 `ASR-03` |
| 2026-08-06 | 会话203255发现用户对话、状态和调试输出混杂 | 未改业务代码 | 确认回执被新追问插队，实验步骤编号跳号 | 先定义 `PRESENT-01` |
| 2026-08-06 | 核验会话203255的三类 JSONL 并确定输出分层策略 | 79 tests OK | 4 条 ASR、3 条实验事件、1 条确认记录；确认项已解决 | `PRESENT-01` |
| 2026-08-06 | 新增统一展示消息协议和语音认知负担预算 | 新增8项单测通过；当前代理环境无法启动项目venv完成全量回归 | 未接入main，不需要真实口述 | 验收 `PRESENT-01` 后做问题暂缓生命周期 |
| 2026-08-06 | 固定 TTS 前的数据闭环顺序，并登记安全任务和新问题维护规则 | 未改业务代码 | 不需要真实验收 | 先完成 `PRESENT-01` 自动回归验收 |
| 2026-08-06 | 补登记用户指定待确认问题能力 | 未改业务代码 | 不需要真实验收 | `CLARIFY-09` 后依次完成 `CLARIFY-TARGET-01/02` |
| 2026-08-06 | 固定命令、问题状态、消息调度、屏幕和TTS职责边界 | 未改业务代码 | 不需要真实验收 | PRESENT验收后新增统一命令解析器 |
| 2026-08-06 | 澄清领域记录、展示消息和输出适配器边界 | 10项协议单测通过；全量回归仍待项目venv | 未接main，不需要真实口述 | 完成PRESENT-01全量回归后进入COMMAND-01 |

## 7. 每轮结束时必须更新

1. 更新对应任务的状态。
2. 填写自动测试数量和结果。
3. 如果进行了真实验收，记录 session_id 或日志证据。
4. 更新“当前唯一下一项”。
5. 在维护日志追加一行。
6. 如果文件结构变化，同步更新任务备注和交接文档。
7. 开发、测试或真实验收中发现的新问题，必须在本清单登记任务 ID 或写入维护日志，不能只保留在对话中。
8. 新问题需要注明发现来源、影响、依赖关系和建议处理时机；未确定方案时标记为 `TODO` 或 `DESIGN`，不得假装已经解决。
