# asr_demo 项目任务清单

最后更新：2026-08-11

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

优先级定义：

| 标志 | 含义 |
|---|---|
| `P0` | 当前主线或阻塞项；不完成就不应继续后续能力 |
| `P1` | TTS前核心闭环；P0完成后按依赖顺序推进 |
| `P2` | 重要增强、稳定性或跨模块集成；不阻塞当前小步 |
| `P3` | 明确后置、依赖外部条件或表现层增强 |

优先级表示执行紧迫度，状态表示完成证据，两者不能互相替代。已完成任务仍保留其架构优先级；
若发现数据丢失、安全或主流程阻断问题，可在维护日志说明证据后提升优先级。

## 2. 当前测试基线

- 全量自动测试：`422 tests OK`（Python 3.11.9，2026-08-11）
- 最近真实连续口述会话：`20260811_103134`
- 最近真实会话已验证：影子观察”将溶液加热”输出missing_fields=('temperature','duration')、待确认动作=create、未执行；旧流程正常创建追问；结束命令正常退出

恢复工作时先运行：

```powershell
cd C:\Users\dahli\Desktop\asr_demo

.\.venv\Scripts\python.exe -B -m unittest discover `
    -s tests `
    -v
```

## 3. 当前唯一下一项

> 真实验收：`UNIFIED_SHADOW_EXECUTE_ENABLED=true` 开启执行，说多段话验证新老两套链路结果一致。验收通过后关闭旧 `ingest_analysis`，新链路成为唯一来源。

COMMAND-03 ✅、REPLY-GATE-02 ✅、REPLY-GATE-03 ✅。三个前置任务全部完成，进入验收阶段。

## 3.1 当前执行看板

这一部分只放“近期真正要做的事”。下面第4节仍保存完整任务库和历史证据。

| 顺序 | 优先级 | 任务 | 当前状态 | 本轮要得到的结果 | 进入下一项的条件 |
|---:|---|---|---|---|---|
| 1 | `P0` | `INTENT-02-UNIFIED-DISPATCH-01` 统一路由结果分派合同 | `AUTO_OK` | 六类无副作用目标与最小权限合同完成 | 10项专项、4项Router→Planner集成及全量332项通过；未接main、存储、协调器或状态机 |
| 2 | `P0` | `INTENT-02-UNIFIED-DISPATCH-INTEGRATION-01` 固定文本旁路分派集成 | `AUTO_OK` | 模拟ASR证据→真实Router→真实Planner→只读报告形成旁路 | 6项专项、五类脚本烟雾及全量338项通过；无执行依赖、无文件写入 |
| 3 | `P0` | `INTENT-02-UNIFIED-DISPATCH-WAV-01` 固定WAV真实旁路验收 | `REAL_OK` | 固定WAV→真实ASR→统一路由→安全分派，只输出观察报告 | 18.072秒固定WAV真实识别1.593秒；DeepSeek首次请求成功1.961秒；普通实验只得到experiment_pipeline＋forward_experiment_analysis；全量340项通过，未写业务文件或连接执行模块 |
| 4 | `P0` | `INTENT-02-DISPATCH-EXECUTION-CONTRACT-01` 分派执行请求/结果合同 | `AUTO_OK` | 将最小权限计划转换为可审计、可拒绝、可防重复的执行请求；仍不实现真实副作用 | 新增10项合同/Fake测试；相关24项、全量350项通过；未接main、存储、状态机或TTS |
| 5 | `P0` | `INTENT-02-EXPERIMENT-ACCEPTANCE-CONTRACT-01` 实验结果采用合同 | `AUTO_OK` | 验证统一理解的实验候选后形成不可变规范快照，禁止旧SegmentProcessor再次调用LLM | 新增10项采用测试；相关37项、全量360项通过；未写存储或上下文 |
| 6 | `P0` | `INTENT-02-CLARIFICATION-ACCEPTANCE-01` 待确认动作采用合同 | `AUTO_OK` | 把创建、回答、确认、暂缓、回看和弃权变成目标明确的无副作用动作计划 | 新增13项测试；相关43项、全量373项通过；没有commit方法，未修改ReplyCoordinator |
| 7 | `P0` | `INTENT-02-ACCEPTANCE-INTEGRATION-01` 固定文本采用链集成 | `AUTO_OK` | Router→Planner→ExecutionRequest→实验/待确认采用器组成一条无副作用链 | 新增9项接线测试；相关59项、全量382项通过；固定文本覆盖实验、创建追问、查看、暂缓、指定回答、LLM中风险弃权和降级；不接main或存储 |
| 8 | `P0` | `INTENT-02-MAIN-SHADOW-INTEGRATION-01` main影子观察接入 | `REAL_OK` | 新采用链读取main产生的同一份最终ASR证据并输出可比较观察结果 | 自动全量385项；真实会话`20260810_120209`观察4段，3段成功、结束候选1段安全失败且旧流程继续；未写影子业务数据、未改状态、未发TTS。首次怀疑追问合同缺失，后续测试证明合同原有双检验，真实差异最终定位为统一Prompt能力规则遗漏；main命令标准化漂移已修复并REAL_OK |
| 9 | `P0` | `INTENT-02-FOLLOWUP-INVARIANT-01` 追问跨字段一致性合同 | `AUTO_OK` | `missing_fields`非空或`needs_confirmation=true`时，不能接受`should_ask_follow_up=false`并产生NO_ACTION | 复核发现parse_analysis原本已强制该不变量，采用快照物化时也会再次严格解析；新增5项明确上下游反例测试并补影子missing_fields/follow_up_required摘要；相关25项、全量390项通过。真实会话no_action不能证明矛盾，因为当时未记录新链字段 |
| 10 | `P0` | `INTENT-02-END-NORMALIZATION-UNIFY-01` 结束命令标准化单一来源 | `REAL_OK` | main与InteractionCommandParser必须复用同一份SenseVoice情绪符号清理和命令集合 | 删除main独立字典/正则，新增情绪尾反例和一致性2项，全量392项；修改后短真实会话直接结束，ASR业务记录保持186、事件保持133，主程序停止且最后记录未变化，证明结束口述未进入分段、影子/旧LLM或存储 |
| 11 | `P0` | `INTENT-02-SHADOW-FOLLOWUP-OBSERVE-01` 追问字段真实影子复验 | `REAL_OK` | 使用新增脱敏摘要观察新统一链自己的missing_fields与follow_up_required | 会话`20260810_180242`确定差异来自统一Prompt缺少能力规则，不是合同矛盾 |
| 12 | `P0` | `INTENT-02-UNIFIED-PROMPT-MISSING-FIELDS-01` 统一Prompt缺失字段能力对齐 | `REAL_OK` | ~ | Prompt新增1行业务规则；真实DeepSeek复验missing_fields=['temperature','duration']；影子会话`20260811_103134`确认create+缺失字段输出正确 |
| 13 | `P1` | `INTENT-02-REPLY-GATE-01` ClarificationAction→ReplyCoordinator执行器 | `AUTO_OK` | ~ | 新增ClarificationExecutor+23项测试；ReplyCoordinator新增4个原子方法；影子会话`20260811_103134`验证新链输出create施工单但未执行；415项通过 |
| 14 | `P0` | `COMMAND-03` 自然控制表达兼容 | `AUTO_OK` | 将”我先跳过/可先跳过”等自然表达匹配到精确命令 | DEFER新增安全前缀+跳过后缀规则；REVIEW新增自然表达式模式；Prompt新增uncertain兜底规则；3项parser+1项prompt测试；418项全量通过；未做真实影子复验 |
| 15 | `P0` | `INTENT-02-REPLY-GATE-02` ANSWER施工单实体填充 | `AUTO_OK` | ~ | 新增AnswerEntityExtractor轻量LLM提取+answer_clarification方法；统一理解control分支可携带supplied_entities；Executor优先用施工单实体再fallback到extractor；422项通过 |
| 16 | `P0` | `INTENT-02-REPLY-GATE-03` 影子位接入ClarificationExecutor | `AUTO_OK` | 影子观察时CREATE真的创建问题到ReplyCoordinator，旧流程并行跑 | ShadowObservation新增executed/execution_reason；observe()内接executor.execute()；新增UNIFIED_SHADOW_EXECUTE_ENABLED独立开关；422项通过；未真实验收 |

### 当前路线为什么这样排

```text
先把“听见了什么”测清楚
    ↓
再定义“用户想做什么”以及风险边界
    ↓
再决定“何时、通过什么渠道告诉用户”
    ↓
最后完成确认收尾、总结、聚合、导出和TTS
```

ASR、意图和展示属于三个不同问题。若同时修改，真实测试失败时无法判断究竟是模型没听清、
路由器理解错，还是消息没有在正确时机展示。

## 3.2 TTS 前阶段路线

### 阶段一：输入可靠性

```text
ASR-CMD-REC-01 语料采集器
→ ASR-CMD-01 固定语料与真实基线
→ ASR-CMD-02 比较ASR增强方案
→ ASR-03/04 专业实验词评测与热词对照
```

完成标志：控制语句和核心专业词都有固定WAV、参考文本和可重复报告，不再凭一次口述感觉调参。

### 阶段二：自然语言控制与安全边界

```text
INTENT-01 自然表达和风险等级
→ INTENT-02 IntentRouter
→ COMMAND-03 自然表达兼容
→ CLARIFY-TARGET-02 按步骤或主题指定回答
→ CLARIFY-07 否定并修正
```

完成标志：低风险查看可以语义容错；暂缓和回答具有明确目标；结束、删除等较高风险动作不能由
LLM猜测后直接执行。

### 阶段三：输出顺序与会话收尾

```text
PRESENT-INTEGRATE-01 最小消息链路
→ PRESENT-03/04/05/06 输出预算、编号和日志分流
→ TIMING-01/02/03 安全输出时机
→ CLOSING-01/02/03 确认收尾阶段
→ LLM-10 会话结束总结
```

完成标志：用户不会在操作后面时突然听到很早以前的无来源问题；可以跳过、回看和结束确认阶段；
屏幕内容、未来朗读内容和开发日志职责清楚。

### 阶段四：数据闭环与导出

```text
CLARIFY-TARGET-PERSIST-01 答复目标持久化
→ SESSION-02 按session_id聚合
→ EXPORT-01 Markdown/JSON导出
→ STABILITY-01/03/04 真实长会话验收
→ SAFETY-01/02 系统故障分级和用户消息
```

完成标志：一次实验从原始口述、结构化事件、确认答复到总结都能追溯，并可导出为真正可用的记录。

### 阶段五：TTS及表现层

```text
TTS-01 接口和假客户端
→ TTS-02 系统TTS
→ TTS-03/04/05 SPEAKING状态、降级和打断
→ GPT-SoVITS
→ Live2D
→ Word/PDF美化导出
```

完成标志：TTS失败不会影响录音和记录；用户开始说话时系统能停止朗读；Live2D崩溃也不会破坏核心数据。

## 3.3 暂不提前开展的任务

| 优先级 | 任务 | 暂缓原因 | 重新启动条件 |
|---|---|---|---|
| `P3` | TTS、GPT-SoVITS、Live2D | 会把当前输出时序问题放大，且难以判断故障来源 | 阶段三和阶段四达到验收条件 |
| `P3` | Word/PDF报告美化 | 当前还没有完整SessionRecord可供可靠导出 | Markdown/JSON第一版真实导出通过 |
| `P3` | Demo实验风险知识库 | Demo实验尚未最终确定，过早写规则容易返工 | 确定演示实验、SOP和术语范围 |
| `P3` | RAG和用户画像 | 属于质量增强，不是当前闭环缺失的核心能力 | 基础记录、确认、总结和导出稳定 |
| `P3` | 多工具Agent | 外部写入和高风险动作尚未建立统一确认边界 | 安全等级、白名单和确认流程完成 |

## 3.4 个人开发范围与团队分工（待团队确认）

本节把“整个产品需要什么”和“当前开发者本人必须完成什么”分开。它来自现阶段讨论，属于建议稿，
在三人共同确认前不代表正式派工。

### A：当前开发者本人主责

这些模块决定语音实验记录主链是否可靠，应由本人持续维护和最终验收：

| 领域 | 主责内容 | 为什么适合本人负责 |
|---|---|---|
| 音频入口 | 唤醒、VAD、录音、WAV、播放期间资源协调 | 已有真实链路和故障经验，继续维护最容易保证原始证据 |
| ASR质量 | 固定语料、人工标签、基线、热词/模型对照 | 能直接从真实录音定位“截音、识别、意图”分别哪里错 |
| 自然意图 | InteractionCommand、IntentRouter、风险分层 | 它位于ASR与实验LLM之间，是语音助手安全边界 |
| 会话控制 | 状态机、后台队列、顺序、背压、优雅退出 | 已有完整上下文，交给多人同时修改容易产生时序故障 |
| 实验理解 | LLMClient、结构化事件、原文保护、降级 | 当前项目的核心差异化能力 |
| 追问确认 | PendingClarification、指定回答、修正与收尾 | 与语音上下文和实验事件高度相关 |
| 消息协调 | PresentationMessage、Presenter、未来TTS播放策略 | 决定何时说、显示什么、失败怎样降级，不等于负责前端样式 |
| 会话记录 | SessionRecord、总结、Markdown/JSON第一版导出 | 负责把现场事实形成完整、可追溯记录 |

### A：建议新增的“跨模块学习型主责”

这些工作能学习接口、后端通信、系统集成和测试，又不需要接管队友内部实现：

| ID | 优先级 | 任务 | 状态 | 学习价值与边界 |
|---|---|---|---|---|
| `ARCH-01` | `P2` | 维护端到端数据流和模块边界图 | `TODO` | 学习系统架构；只描述职责和数据，不替各模块决定内部算法 |
| `CONTRACT-01` | `P2` | 定义设备查询第一版请求/响应/错误契约 | `TODO` | 学习API和Schema；需B共同确认，不能单方面定稿 |
| `PLANNING-CLIENT-01` | `P2` | 定义PlanningClient接口与Fake实现 | `TODO` | 学习依赖倒置和HTTP客户端；不直接访问B的数据库 |
| `PLANNING-CLIENT-02` | `P2` | 实现只读HTTP设备查询适配器 | `TODO` | 学习超时、错误映射和外部服务降级；B负责服务端 |
| `CONTRACT-TEST-01` | `P2` | 固定JSON契约测试 | `TODO` | 学习跨仓库协作；验证双方遵守接口，不测试B的内部函数 |
| `E2E-QUERY-01` | `P2` | 语音查询设备的端到端验收 | `TODO` | 学习系统集成和分层排错；只读查询，不修改日程 |
| `E2E-DEMO-01` | `P2` | 维护2～3分钟稳定Demo脚本和验收表 | `TODO` | 学习产品化和质量保证；三人共同提供模块能力 |
| `OBS-01` | `P2` | 统一跨模块request_id与关键耗时记录 | `TODO` | 学习可观测性；不把debug日志混入用户消息 |

这些任务不立即插队。建议在 `INTENT-02` 稳定后依次开展：

```text
CONTRACT-01
→ PLANNING-CLIENT-01 Fake客户端
→ CONTRACT-TEST-01
→ PLANNING-CLIENT-02 真实HTTP
→ E2E-QUERY-01
```

### A：共同参与，但不应独自包揽

| 事项 | 本人适合做什么 | 不应包揽什么 |
|---|---|---|
| 计划与设备后端 | 参与Schema、调用接口、写契约和集成测试 | 数据库表、冲突算法、后端权限和所有API实现 |
| 前端页面 | 定义消息语义、提供Mock事件、验收展示顺序 | 整套页面布局、组件、动画和Live2D渲染 |
| GPT-SoVITS服务 | 定义TTSClient、超时、缓存和降级要求 | 同时承担服务部署、训练、音色调优和播放状态全部工作 |
| 报告导出 | 定义SessionRecord并实现Markdown/JSON内容 | 同时包揽前端预览、Word/PDF美化和队友计划数据生成 |
| 安全规则 | 定义语音意图风险、确认和降级接口 | 单独制定实验室SOP、设备权限和全部业务规则 |
| 比赛集成 | 维护主链验收、故障注入和演示脚本 | 一个人修复所有队友模块内部缺陷 |

### 建议由B主责

```text
实验计划与设备数据库
→ 设备稳定ID和资源状态
→ 时间冲突与预约规则
→ 待确认计划提案及其持久化
→ 确认后写入、幂等、权限和审计
→ FastAPI服务端及OpenAPI文档
```

A可以通过Fake客户端、契约测试和代码评审学习这些知识，但生产实现和数据责任应有明确负责人。

### 建议由C主责

```text
Web展示页面
→ 用户/助手消息布局和状态可视化
→ 实验时间线、设备状态、待确认问题和报告预览
→ WebSocket或事件订阅适配
→ Live2D表现、口型、演示模式和展示打包
```

A负责提供稳定消息协议和Mock数据，不应让前端直接读取 `main.py` 的终端输出。

### “多学习但不包揽”的执行规则

1. 每个生产模块只有一个明确主责人，其他人通过评审、测试和接口参与。
2. 想学习队友领域时，优先写Fake、契约测试、客户端或小型实验，不复制一套生产服务。
3. 联调故障先定位所属层，再由主责人修复内部实现；集成人负责提供可重复证据。
4. 共同任务必须写清最终拍板人，避免“三个人都负责”等于没人负责。
5. 当前个人任务一次仍只推进一个可独立验证能力，跨模块学习任务不得打断当前ASR主线。

### 第一次团队确认只需要决定的事项

| 需要确认 | 建议默认值 |
|---|---|
| A/B/C长期边界 | A语音会话；B计划设备；C前端展示 |
| 第一条联合链路 | 只读查询一号离心机是否空闲 |
| 公共字段 | equipment_id、start_at、end_at，时间带时区 |
| 写入安全 | 第一轮完全只读；后续修改必须提案+明确确认 |
| 接口变更方式 | 先改契约和示例，再改双方实现 |
| 联合验收责任 | A维护端到端步骤，B/C各自修复所属模块 |

## 4. 任务总表

### 0. 本地开发环境

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `ENV-01` | `P1` | 修复或重建主 `.venv` | `REAL_OK` | Python 3.11.9与`.venv`均正常；先前失败是Codex沙箱拒绝执行AppData解释器造成的误判；沙箱外复验218项全量测试和真实SenseVoice对照均通过 |
| `ENV-02` | `P3` | 保留 Python 3.14 备用环境 | `REAL_OK` | 已恢复为 `.venv-py314`，不作为正式开发与验收环境 |
| `ENV-03` | `P2` | 建立可复现的依赖锁定文件 | `TODO` | 当前requirements只列直接依赖且未固定版本；应在功能稳定后生成3.11锁定版本 |

### A. 音频、唤醒与 ASR 基础

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `AUDIO-01` | `P0` | 麦克风录音和 WAV 保存 | `REAL_OK` | 多次真实口述已生成 `audio/recordings/*.wav` |
| `VAD-01` | `P0` | 检测开始说话和自然停顿 | `REAL_OK` | 真实日志包含“检测到人声/检测到说话结束” |
| `KWS-01` | `P1` | 离线唤醒“小科小科” | `REAL_OK` | 真实日志多次唤醒成功 |
| `ASR-01` | `P0` | FunASR/SenseVoice 中文识别 | `REAL_OK` | 真实实验口述已识别并保存 |
| `ASR-02` | `P0` | 专业词错误保留原文 | `REAL_OK` | “一液枪/微生”等原文未被覆盖 |
| `ASR-03` | `P2` | 建立实验专业词固定评测集 | `TODO` | 真实验收发现专业词错词较多；需固定音频、期望文本和错词统计 |
| `ASR-04` | `P2` | 专业词热词/文本后处理对照实验 | `TODO` | 当前识别调用未传热词；必须在 ASR-03 后比较，且保留模型原文 |
| `ASR-05` | `P0` | 固定中文语言参数对照测试 | `REAL_OK` | 14条真实WAV对照：auto文本8/14、意图9/14；zh文本8/14、意图10/14；zh有一项意图改善但也产生两项文本回退，暂不修改main默认auto |
| `ASR-CMD-01` | `P0` | 建立通用控制命令文本/音频语料和基线 | `REAL_OK` | 新增accepted尝试→真实ASR清单/基线生成器；24条人工接受WAV使用SenseVoice language=auto、use_itn=True、batch_size_s=60两次真实运行汇总一致：文本精确13/24、精确规则意图11/24、控制漏触发13、普通内容误触发0；进一步用人工参考文本诊断出规则覆盖不足13、ASR额外造成意图漏触发0；全量297项通过；本地识别清单和报告不上传 |
| `ASR-CMD-REC-01` | `P2` | 独立采集控制命令固定语料 | `REAL_OK` | 正式入口真实完成24/24；共31次尝试，24次accepted、7次retry_requested；三条待补样本通过断点恢复再次采集；24个样本ID各有且只有一条接受记录，31个WAV路径全部存在；本地音频与尝试清单不上传GitHub |
| `ASR-CMD-REC-DATA-01` | `P0` | 定义语料提示项和录音尝试数据对象 | `AUTO_OK` | 新增不可变CommandCorpusPrompt、RecordingAttempt及状态枚举；11项专项测试通过；严格校验确认、失败、跳过和基线资格；JSON路径跨平台统一为正斜杠 |
| `ASR-CMD-REC-STORE-01` | `P0` | 追加式保存录音尝试清单 | `AUTO_OK` | 原子临时文件替换；attempt_id防重复；允许同一句不同attempt；损坏旧文件和替换失败不覆盖；新增6项存储测试，专项17项及全量152项通过 |
| `ASR-CMD-REC-COORD-01` | `P0` | 通用录音、回放、人工决策和证据保存协调器 | `AUTO_OK` | 接受/截断/重复/重录/跳过/录音失败/播放失败统一转换为RecordingAttempt；WAV优先保留；7项专项、全量203项通过 |
| `ASR-CMD-REC-PROMPTS-01` | `P0` | 固定提示稿计划和断点恢复 | `AUTO_OK` | schema_version=1严格加载；拒绝额外字段/重复ID/未知意图；正式24条覆盖7类意图；只有accepted算完成；7项专项、全量210项通过 |
| `ASR-CMD-REC-CLI-01` | `P0` | 正式独立命令行采集入口 | `AUTO_OK` | 可恢复会话运行器5项测试；正式--status烟雾测试显示0/24及尝试号；入口复用计划/协调器/存储；全量215项通过 |
| `ASR-CMD-02` | `P0` | 使用固定命令集比较 ASR 增强方案 | `DESIGN` | 固定中文参数真实对照已完成，未显示无代价全面改善；下一步比较热词；同一批音频一次只改一个变量 |
| `ASR-CMD-02-LANGUAGE-01` | `P0` | language=auto与固定中文参数对照 | `REAL_OK` | Python3.11运行28次真实识别并生成language_comparison.json；auto文本8/14、意图9/14、漏触发5；zh文本8/14、意图10/14、漏触发4；普通内容误触发均为0；暂不改main |
| `ASR-CMD-02-HOTWORD-01` | `P2` | 无热词与固定热词参数对照 | `BLOCKED` | FunASR 1.4.1通用AutoModel声明hotword参数，但当前SenseVoiceSmall.inference不读取模型级hotword；直接传参会被kwargs吞掉，无法形成可信单变量对照；待未来换用明确支持热词的ASR模型后复验 |
| `ASR-CMD-02-POSTPROCESS-01` | `P2` | 固定专业词模糊后处理对照 | `REAL_OK` | 使用24条已保存原始ASR文本、固定目标词移液枪/水浴/滴定管、阈值0.85；只生成候选不覆盖原文；修改4条，目标术语0/4→4/4，严格文本13/24→16/24，意图11/24不变，文本/意图回退均0；新增4项测试、全量301项通过；样本内选词存在过拟合风险，未接main |
| `ASR-BACKEND-CONTRACT-01` | `P1` | 模型无关ASR后端合同与工厂 | `REAL_OK` | 新增ASRBackend Protocol、SenseVoiceBackend和create_asr_backend；main及三个独立真实脚本不再直接构造具体模型；ASR_BACKEND集中配置且默认sensevoice，未知后端在加载模型前明确拒绝；保留ASRResult、原始模型文本和旧ASR_MODEL兼容名；新增7项Fake/临时WAV测试、ASR下游38项及全量308项通过；通过新工厂真实识别18.072秒固定WAV，模型iic/SenseVoiceSmall、识别1.922秒；尚未实现第二模型 |
| `ASR-EVIDENCE-CONTRACT-01` | `P0` | ASR、LLM与用户消息原始证据命名合同 | `REAL_OK` | `ASRResult`升级为不可变schema v2：`asr_model_raw_text`保存ASR引擎直接文本字段，`asr_transcript`保存确定性去标签后的忠实可读转写；新写入不再生成含糊的`text/raw_text`键，旧构造与只读属性仅作过渡。新增独立不可变`TranscriptCorrectionCandidate`，源转写与候选必须不同，纠错不能回写证据。`ASRResultStore.load_all()`严格读取v1/v2并保留会话来源，损坏行明确报行号；182条现有v1历史记录全部读取成功且文件SHA-256前后不变。SenseVoice适配器、main、命令/确认处理、评测和真实脚本已迁移到明确字段；测试Fake也改为正式ASRResult而非半对象。新增10项合同/存储测试，专项17项、下游47项、Python3.11全量318项通过；真实18.072秒固定WAV输出schema v2，模型原始文本与忠实转写均非空且不同，识别1.482秒。LLM原始响应仍由现有严格Processor边界管理，本轮未重命名ExperimentEvent或PresentationMessage字段，未批量迁移历史文件 |
| `ASR-CMD-02-MODEL-CANDIDATE-01` | `P2` | 热词模型候选验证 | `TODO` | 候选优先SeACo/contextual Paraformer；先用源码/能力探针证明推理路径真正读取模型级hotword，再以同一批24条accepted WAV完成SenseVoice原始、SenseVoice＋文本后处理、候选模型无热词、候选模型有热词四组对照；固定热词为移液枪/水浴/滴定管；保留各模型原文并记录模型标识、配置、耗时、峰值内存、目标术语命中、严格文本、意图、普通内容误触发及改善/回退；候选验证不得替换当前模型、不得接main、不得上传WAV/模型权重/逐条本地报告。通过门槛：有热词相对候选无热词目标术语改善，意图和普通句无新增回退，并在独立新增语音上复验；否则保留SenseVoice与后处理方案 |
| `INTENT-01` | `P0` | 定义自然控制表达与风险等级 | `AUTO_OK` | 新增IntentRisk、IntentEvidence、IntentDisposition、IntentPolicy和IntentDecision；7项专项及全量225项通过；精确结束可执行，语义/LLM结束必须确认，LLM不得直接写确认状态；尚未接main |
| `INTENT-02` | `P0` | 实现 ASR 与实验LLM之间的轻量 IntentRouter | `DESIGN` | 精确路由子步骤已AUTO_OK：IntentRouter组合InteractionCommandParser与IntentPolicyEvaluator，返回不可变IntentRouteResult；7项路由测试、相关30项及全量232项通过；尚未接自然语义、协调器或main |
| `INTENT-02-EXACT-01` | `P0` | 精确命令统一路由 | `AUTO_OK` | 普通口述进入实验链路；查看/答复进入上下文；精确结束进入执行；保留raw_text和答复编号；自然表达不猜测；7项专项通过 |
| `INTENT-02-CLASSIFIER-01` | `P0` | 定义LLM意图分类接口和候选结构 | `AUTO_OK` | 新增IntentClassificationInput、IntentCandidate、IntentClassifier协议、FakeIntentClassifier及IntentClassifierError；严格拒绝缺失/额外/越权字段；10项专项、全量242项通过；未调用真实LLM |
| `INTENT-02-CLASSIFIER-ROUTE-01` | `P0` | Fake分类器接入IntentRouter | `AUTO_OK` | 精确命令绕过分类器；未命中才分类；候选统一经过风险策略；结束候选只REQUEST_CONFIRMATION；超时保留raw_text并降级为普通链路且记录错误；新增6项集成测试，全量248项通过；未接main |
| `INTENT-02-PROMPT-01` | `P0` | 意图弃权状态与严格提示词合同 | `AUTO_OK` | IntentCandidate新增matched/uncertain；uncertain必须清空意图/编号/答案；新增稳定System Prompt和JSON User Prompt构造；Router显式标记classification_uncertain并禁止控制动作；提示词2项、相关27项、全量252项通过 |
| `INTENT-02-LLM-ADAPTER-01` | `P0` | LLMIntentClassifier适配器 | `AUTO_OK` | 新增src/llm/intent_classifier.py；复用LLMClient.generate_json和提示词，将字符串解析为顶层JSON对象后严格构造IntentCandidate；合法、uncertain、非法JSON/非对象、额外字段、客户端异常5项通过；全量257项通过 |
| `INTENT-02-LLM-INTEGRATION-01` | `P0` | LLM适配器与IntentRouter模块集成 | `AUTO_OK` | FakeLLMClient→LLMIntentClassifier→IntentRouter→IntentPolicy完整链路7项通过；精确绕过、自然查看、高风险结束、uncertain、非法JSON、客户端异常、普通实验均覆盖；全量264项通过 |
| `INTENT-02-LLM-REAL-01` | `P0` | DeepSeek意图分类烟雾与延迟验收 | `REAL_OK` | 独立脚本固定5条非敏感文本全部符合预期；normal/review/end/uncertain/targeted_answer及策略出口正确；均1次成功，耗时1.700～1.884秒，平均约1.808秒；未接main，未保存/上传逐条响应 |
| `INTENT-02-ARCH-01` | `P0` | 独立意图调用与统一LLM调用架构决策 | `DESIGN` | 决策为“精确规则本地快速路径＋未命中统一一次LLM理解”；两组完整真实配对中独立两次为5.809/5.621秒，统一一次冷缓存10.980秒、热缓存2.636秒；统一首次格式失败后补齐跨字段规则；另两次统一请求遇SSL断连，证据不足归因架构；先正式化合同再扩大评测 |
| `INTENT-02-UNIFIED-CONTRACT-01` | `P0` | 统一输入理解三分支数据合同 | `AUTO_OK` | 新增UnifiedUnderstandingResult及experiment/control/uncertain不可变分支；严格拒绝缺失、额外、混合、原文篡改和uncertain伪装control；失败可降级为保留原文的未分类NOTE且不产生控制候选；新增7项专项、全量276项通过；未接真实LLM、main或ReplyCoordinator |
| `INTENT-02-UNIFIED-PROCESSOR-01` | `P0` | 正式统一提示词与Processor | `AUTO_OK` | 新增可信输入上下文、封闭三分支Prompt和UnifiedUnderstandingProcessor；Fake覆盖experiment/control/uncertain、非法JSON、客户端失败、指标与来源注入；相关15项、全量284项通过；未接真实LLM和main |
| `INTENT-02-UNIFIED-REAL-01` | `P0` | 正式统一理解真实烟雾 | `REAL_OK` | 固定5条非敏感文本真实验收；首轮实验分支因amount_value返回数字被严格拒绝并安全降级，补充“数值也必须是字符串”后完整复验5/5；均首次成功，耗时1.614～2.441秒；未打印/保存逐条原始响应，未接main |
| `INTENT-02-UNIFIED-ROUTE-01` | `P0` | 精确快速路径与统一理解模块组合 | `AUTO_OK` | 新增UnifiedUnderstandingRouter和单一路径UnifiedRouteResult；精确控制绕过完整LLM链，未命中才统一理解；自然结束经过风险策略只请求确认，指定回答DO_NOT_EXECUTE；experiment、uncertain、非法JSON、客户端失败和指标均覆盖；新增7项集成测试、全量293项通过；未接main |
| `INTENT-02-UNIFIED-DISPATCH-01` | `P0` | 统一路由结果分派合同 | `AUTO_OK` | 新增不可变UnifiedDispatchPlan、UnifiedDispatchDestination、UnifiedDispatchPermission和纯UnifiedDispatchPlanner；六类目标为实验链路、待确认上下文、精确结束执行候选、LLM结束确认、安全弃权、降级NOTE。统一优先规则为：degraded优先隔离、uncertain明确弃权、其余控制服从IntentDisposition、始终原样保留路由输入；目标与最小权限非法组合立即拒绝。Planner无存储、状态机、ReplyCoordinator或TTS依赖，不执行任何副作用；10项专项、4项真实Router→Planner Fake集成、连同既有路由共21项及Python3.11全量332项通过；未接main |
| `INTENT-02-UNIFIED-DISPATCH-INTEGRATION-01` | `P0` | 固定文本旁路分派集成 | `AUTO_OK` | 新增UnifiedDispatchBypassInput、UnifiedDispatchBypass和只读UnifiedDispatchObservation；只把最终ASRResult.asr_transcript转成UnifiedUnderstandingInput，明确不转发asr_model_raw_text；Router若替换文本立即失败。观察报告只含转写、路由来源、风险、处置、目标、最小权限和指标，不含执行方法或模型标签文本。独立模块脚本使用五类固定Fake结果验证experiment_pipeline、clarification_context、end_session_confirmation、abstention和degraded_note；首次直接脚本启动因Python导入路径失败，改用`python -m scripts.evaluate_unified_dispatch_bypass`成功。新增6项专项、全量338项通过；未访问网络、麦克风或存储，未接main |
| `INTENT-02-UNIFIED-DISPATCH-WAV-01` | `P0` | 固定WAV真实旁路验收 | `REAL_OK` | 新增独立真实旁路脚本和严格报告字段白名单；2项新测试证明报告不包含ASR模型标签、绝对路径、LLM原始响应或错误详情，真实Processor失败只能进入degraded_note；专项12项、Python3.11全量340项通过。经用户明确授权，固定`03_terms_second.wav`真实SenseVoice转写进入DeepSeek一次：18.072秒音频识别1.593秒，LLM首次成功1.961秒，路由为normal/pass_to_experiment，分派为experiment_pipeline＋forward_experiment_analysis，未降级。未写业务文件、未调用状态机、ReplyCoordinator或TTS；FunASR启动仍检查/刷新模型缓存，继续由MODEL-LOAD-02跟踪 |
| `INTENT-02-DISPATCH-EXECUTION-CONTRACT-01` | `P0` | 分派执行请求与结果合同 | `AUTO_OK` | 新增不可变DispatchExecutionRequest/Result、DispatchExecutionStatus、DispatchExecutor Protocol和无副作用FakeDispatchExecutor。请求绑定request/session/segment、最终ASRResult和UnifiedDispatchPlan，ASR原文不一致立即拒绝；结果回显身份、目标和最小权限，并把accepted/rejected/failed/no_action与state_changed、persisted、message_ids分开，未接受结果不得声称副作用。Plan和Result复用同一目标→权限规则；Fake可按权限接受/拒绝/失败，重复相同request_id返回同一结果且只计一次，不同请求碰撞同一ID立即拒绝。新增10项测试，相关24项、Python3.11全量350项通过；未接main、存储、状态机、ReplyCoordinator或TTS，因此只到AUTO_OK |
| `INTENT-02-EXPERIMENT-ACCEPTANCE-CONTRACT-01` | `P0` | 统一理解实验候选采用合同 | `AUTO_OK` | 新增纯ExperimentCandidateAcceptor、不可变AcceptedExperimentAnalysis和STRUCTURED_EXPERIMENT/DEGRADED_EVIDENCE_NOTE用途分类。采用时核对DispatchExecutionRequest、统一理解分支、request/session/segment、ASR忠实转写、每个事件来源、分派目标/权限、降级错误和事件数量；正常实验只从experiment_pipeline采用，degraded_note只能产生一个不改写原文且需确认的NOTE，降级形状即使伪造degraded=false也不能混入正常采用。旧可变LLMAnalysisResult被转换为规范JSON快照，可信source字段不混入模型业务JSON，需要交给旧存储边界时严格解析成全新对象，绝不再次调用LLM。新增10项测试，相关37项、Python3.11全量360项通过；未写事件、ASR或上下文，因此只到AUTO_OK |
| `INTENT-02-CLARIFICATION-ACCEPTANCE-01` | `P0` | 待确认动作采用合同 | `AUTO_OK` | 新增不可变ClarificationContextSnapshot、ClarificationAction及纯ClarificationActionPlanner。动作分为create/review/defer/answer/confirm/reject_suggestion/no_action，最小权限分为none/read_only/prepare_create/prepare_update；PREPARE只生成带目标clarification_id、display_number和expected_revision的计划，没有commit方法。精确规则查看可只读；暂缓、肯定、否定和指定回答只有目标存在且答案完整时才准备更新；编号不存在、缺答案或无当前问题转为no_action。低风险LLM查看只能只读，所有LLM中风险状态候选即使编号有效也保持abstention/no_action。已采用正常实验的追问可准备CREATE且要求先保存来源ASR；degraded NOTE不创建假问题。新增13项测试，相关43项、Python3.11全量373项通过；未访问或修改ReplyCoordinator、存储、状态机或TTS |
| `INTENT-02-ACCEPTANCE-INTEGRATION-01` | `P0` | 固定文本完整采用链集成 | `AUTO_OK` | 新增UnifiedAcceptanceBypass，把真实UnifiedUnderstandingRouter、UnifiedDispatchPlanner、DispatchExecutionRequest、ExperimentCandidateAcceptor和ClarificationActionPlanner串成无副作用链，配确定性Fake Processor与只读上下文。9项新增测试覆盖普通实验、实验追问CREATE、精确/LLM查看、精确暂缓、编号回答、LLM中风险弃权、degraded NOTE及请求身份/ASR原文贯穿；相关59项、Python3.11全量382项通过。旁路不持有存储、SessionContext、ReplyCoordinator或TTS，且暂不处理结束会话目标，因此只到AUTO_OK |
| `INTENT-02-MAIN-SHADOW-INTEGRATION-01` | `P0` | main影子观察接入 | `REAL_OK` | 新增默认关闭的UNIFIED_SHADOW_ENABLED开关、UnifiedShadowObserver和脱敏ShadowObservation；自动3项隔离、相关16项、Python3.11全量385项通过。用户明确授权本次逐条ASR忠实转写发送DeepSeek后开启本机开关，真实会话`20260810_120209`共4段：前三段进入experiment_pipeline/structured_experiment且只观察不执行；第4段精确结束候选进入旁路未开放的结束目标，被转换为ValueError失败摘要，旧流程继续，证明失败隔离生效。影子没有写业务文件、更新SessionContext/ReplyCoordinator或发TTS。真实结果同时发现追问一致性与旧main命令标准化问题，已拆分任务，REAL_OK只表示影子接线和隔离真实成立，不表示新业务判断全部正确 |
| `INTENT-02-FOLLOWUP-INVARIANT-01` | `P0` | 追问跨字段一致性合同 | `AUTO_OK` | 初步诊断误把旧链保存的missing_fields当成新影子链字段证据。测试优先复核发现src/llm/validation.py原本已计算requires_follow_up，并拒绝三类矛盾：有missing_fields却不追问、needs_confirmation为true却不追问、无任何事件依据却凭空追问；ExperimentCandidateAcceptor生成/物化规范快照时再次调用严格parse_analysis，构成下游复查。新增上游3项、下游2项反例测试，影子摘要新增missing_fields与follow_up_required但不含口述正文；相关25项、Python3.11全量390项通过。下次真实复验可直接区分“未识别缺失字段”和“追问决策矛盾” |
| `INTENT-02-END-NORMALIZATION-UNIFY-01` | `P0` | 结束命令标准化单一来源 | `REAL_OK` | 真实会话第4段ASR“接受实验记录。😔”复现规则漂移后，删除main独立END_SESSION_COMMANDS和独立正则；兼容入口委托InteractionCommandParser。新增情绪尾反例与一致性2项，相关37项、Python3.11全量392项通过。修改后真实短会话仅说结束命令：Python主程序已停止；asr_segments在测试前后均186条、experiment_events均133条，最后记录仍为上一会话旧记录，证明本次结束口述在segment分配前被截住，没有进入影子/旧LLM或业务存储；任务升级REAL_OK |
| `INTENT-02-SHADOW-FOLLOWUP-OBSERVE-01` | `P0` | 新链追问字段真实观察 | `REAL_OK` | 真实会话`20260810_180242`的ASR为“将溶液加热。”，业务记录从186增至187、事件从133增至134，结束命令未落库。影子终端与同一保存证据的单独重放一致：experiment_pipeline、structured_experiment、missing_fields=()、follow_up_required=false、clarification_action=no_action；旧链同句提取temperature/duration并生成追问。对比Prompt发现旧版明确规定操作缺少有意义的体积/浓度/温度/时间时登记missing_fields，新统一Prompt只规定missing_fields非空后的追问一致性，因此这是能力规则遗漏，不是跨字段合同失效 |
| `INTENT-02-UNIFIED-PROMPT-MISSING-FIELDS-01` | `P0` | 统一Prompt缺失字段能力对齐 | `REAL_OK` | 统一Prompt实验规则新增一行”操作缺少对当前实验有意义的体积、浓度、温度或时间时，写入missing_fields并生成一个简短追问”；Prompt合同测试新增关键词验证；全量392项通过；真实DeepSeek以”将溶液加热。”复验成功输出missing_fields=['temperature','duration']、should_ask_follow_up=True、follow_up_question=”加热到什么温度？需要加热多长时间？”，1次成功2.32秒 |
| `INTENT-02-LLM-TOKENS-01` | `P2` | 意图分类独立token上限 | `TODO` | 烟雾响应仅约33～50 completion tokens，但当前沿用LLM_MAX_TOKENS=2000；若保留独立调用，应增加较小的专用配置并复验截断 |
| `INTENT-02-REPLY-GATE-01` | `P1` | LLM答复候选进入ReplyCoordinator前的目标校验 | `AUTO_OK` | 新增ClarificationExecutor+ClarificationExecutionResult把ClarificationAction映射为ReplyCoordinator原子操作；ReplyCoordinator新增register_clarification/defer_clarification/confirm_clarification/find_clarification并重构_register_clarification委托到新方法；新增23项测试覆盖7种动作类型及全生命周期；全量415项通过；未接main.py，ANSWER暂不填充字段 |
| `INTENT-02-SEMANTIC-01` | `P3` | 本地自然表达穷举 | `TODO` | 不作为当前主线；仅在未来有离线、低延迟或特定短语需求时补充，不能要求用户背命令语料 |
| `MODEL-LOAD-01` | `P1` | ASR 和唤醒模型在进程内只加载一次 | `REAL_OK` | 当前 `main()` 启动时创建一次并跨会话复用 |
| `MODEL-LOAD-02` | `P2` | 固定FunASR模型修订并关闭不必要的启动更新检查 | `TODO` | 2026-08-08烟雾测试仍访问ModelScope master并检查/下载文件；需验证缓存和断网启动 |
| `AUDIO-PREROLL-01` | `P0` | 录音句首预缓冲 | `DESIGN` | 缓冲、时间线、组装和VadAudioRecorder假设备接入已完成；仍需“这/查/跳”各3次真实WAV回听与ASR分离验收 |
| `AUDIO-PREROLL-BUFFER-01` | `P0` | 固定容量PreRollBuffer | `AUTO_OK` | deque保存float32单声道块；溢出只丢最旧采样；输入和snapshot均复制隔离；10项专项测试及全量162项通过 |
| `AUDIO-PREROLL-INTEGRATE-01` | `P0` | 将预缓冲与语音段安全组装 | `AUTO_OK` | 新增无状态PreRollSpeechAssembler；重叠量必须显式给出且重复采样必须完全一致；11项专项测试及全量173项通过 |
| `AUDIO-PREROLL-TIMELINE-01` | `P0` | 为预缓冲标记绝对采样区间 | `AUTO_OK` | PreRollSnapshot使用半开区间[start,end)；溢出后保留绝对end；clear重置下一次录音；7项专项及全量180项通过 |
| `AUDIO-PREROLL-RECORDER-01` | `P0` | 按采样时间线接入VadAudioRecorder | `AUTO_OK` | 触发时冻结快照；用segment.start计算重叠；成功/超时均reset VAD；连续录音隔离；时间线7项、录音器4项，全量191项通过 |
| `AUDIO-PREROLL-REAL-TOOL-01` | `P0` | 真实句首WAV录制、即时回放和分阶段ASR工具 | `AUTO_OK` | 录制阶段只回放并保存人工结论；只有显式--asr才识别人工接受的WAV；4项专项及全量195项通过 |
| `AUDIO-PREROLL-REAL-01` | `P2` | 句首预缓冲真实WAV验收 | `TODO` | 首轮5/9完整、4/9截断、0重复；提示时机已修复；因用户当前不方便录音而后推，恢复时执行第二轮同样9句复验 |

### B. LLM 结构化与降级

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `LLM-01` | `P1` | 统一 LLMClient 接口 | `REAL_OK` | DeepSeek 真实请求通过 |
| `LLM-02` | `P1` | 严格 JSON 协议和额外字段拒绝 | `REAL_OK` | 自动测试通过；真实结构化成功 |
| `LLM-03` | `P0` | 保留 raw_text，不直接覆盖 ASR | `REAL_OK` | 真实事件同时保留 raw/normalized |
| `LLM-04` | `P1` | 空响应、超时、429、5xx 有限重试 | `AUTO_OK` | 重试单测通过；尚缺真实故障注入验收 |
| `LLM-05` | `P1` | DeepSeek 关闭 thinking 模式 | `REAL_OK` | 真实日志 `thinking.type=disabled` |
| `LLM-06` | `P2` | 尝试次数和处理耗时 | `REAL_OK` | 真实 JSONL 含 attempts/seconds |
| `LLM-07` | `P1` | 操作、观察、测量、异常分类 | `REAL_OK` | 会话 `20260806_102742` 四类结果正确 |
| `LLM-08` | `P1` | 缺少关键参数时产生追问 | `REAL_OK` | “将溶液加热”产生温度/时间追问 |
| `LLM-09` | `P1` | 阶段总结接口 | `AUTO_OK` | processor/validation 单测通过，未接主流程 |
| `LLM-10` | `P1` | 会话结束总结接入 | `TODO` | 依赖确认收尾流程 |

### C. 后台队列与会话上下文

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `QUEUE-01` | `P1` | LLM 后台处理，录音可继续 | `REAL_OK` | 真实日志显示 LLM 请求期间仍在录音 |
| `QUEUE-02` | `P1` | 单线程顺序保证 | `AUTO_OK` | 队列顺序测试通过 |
| `QUEUE-03` | `P1` | 最大积压和背压 | `AUTO_OK` | backpressure 测试通过 |
| `QUEUE-04` | `P1` | 会话结束优雅等待 | `REAL_OK` | 真实结束时等待剩余任务完成 |
| `SESSION-WORK-CONTRACT-01` | `P1` | 通用会话工作项与完成结果合同 | `TODO` | 当前CompletedSegment绑定旧ProcessOutcome[LLMAnalysisResult]；改为只表达任务身份、类型、完成/拒绝/失败状态和业务载荷，使队列只负责顺序、背压与异常隔离，不猜测所有任务都是旧实验LLM |
| `CTX-01` | `P1` | 最近事件上下文 | `REAL_OK` | 上下文进入真实提示词，单测通过 |
| `CTX-02` | `P0` | NOTE 使用 raw_text | `AUTO_OK` | SessionContext 单测通过 |
| `SESSION-CONTEXT-CONTRACT-01` | `P1` | 结构化会话上下文证据项 | `TODO` | 用不可变ContextEvidenceItem保存来源、证据类型、忠实文本、规范候选、确认与降级状态；给LLM前再格式化为字符串，避免当前deque[str]丢失来源和可信等级 |

### D. 存储、会话与导出

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `STORE-01` | `P0` | ASR JSONL 保存 | `REAL_OK` | 真实会话记录存在 |
| `STORE-02` | `P0` | 实验事件 JSONL 保存 | `REAL_OK` | `experiment_events.jsonl` 已核验 |
| `STORE-03` | `P0` | 事件可追溯到 session/segment | `REAL_OK` | 真实事件 source id 正确 |
| `STORE-04` | `P1` | LLM 降级元数据保存 | `REAL_OK` | 真实历史日志出现降级 NOTE |
| `EXPERIMENT-EVIDENCE-CONTRACT-01` | `P1` | 版本化实验事件证据合同 | `TODO` | 为事件记录增加schema_version、严格from_dict、未知字段拒绝、历史兼容读取、request_id、ASR证据引用、生成路径和采用状态；坚持新写新版本、旧读旧版本、不原地覆盖历史 |
| `SESSION-01` | `P0` | 每次实验使用独立 session_id | `REAL_OK` | 会话编号已进入 ASR/事件记录 |
| `SESSION-IDENTITY-CONTRACT-01` | `P2` | 会话内身份与编号合同 | `TODO` | 区分request_id、utterance_id、segment_id、experiment_step_id和clarification_id，规定生成者、唯一范围和跨记录引用，解决内部口述编号与用户实验步骤编号混用 |
| `SESSION-02` | `P1` | 按 session_id 查询完整实验 | `TODO` | 尚无统一查询命令 |
| `EXPORT-01` | `P1` | 导出单次实验 Markdown/JSON | `TODO` | TTS 前建议完成第一版 |
| `EXPORT-02` | `P3` | 导出报告文档 | `TODO` | 后期白名单工具功能 |

### E. 待确认与回复协调

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `CLARIFY-01` | `P1` | PendingClarification 数据结构 | `AUTO_OK` | 单元测试通过 |
| `CLARIFY-02` | `P1` | ReplyCoordinator 登记和部分解决 | `AUTO_OK` | 单元测试通过 |
| `CLARIFY-03` | `P1` | 每个安全间隙最多一条回复 | `AUTO_OK` | main 集成测试通过，尚缺真实验收 |
| `CLARIFY-04` | `P1` | 回复带来源段号和原文 | `AUTO_OK` | main 集成测试通过，尚缺真实验收 |
| `CLARIFY-05` | `P1` | 会话结束显示遗留项 | `AUTO_OK` | 已接 main，尚缺真实验收 |
| `CLARIFY-06` | `P1` | 明确肯定答复关闭最早 ASR 确认项 | `REAL_OK` | 会话 `20260806_203255` 已用真实语音关闭第 1 段确认项 |
| `CLARIFY-07` | `P1` | 否定并提供修正内容 | `TODO` | 当前“不是”不会自动关闭 |
| `CLARIFY-08` | `P2` | 问题优先级、合并、过期 | `TODO` | 当前主要按最早段号 |
| `CLARIFY-09` | `P1` | 待确认项支持暂缓、回看和稳定编号 | `AUTO_OK` | 新增9项生命周期测试；全量118项通过；暂缓问题可被后续字段补全，尚待真实口述 |
| `CLARIFY-TARGET-01` | `P1` | 用户按问题编号指定回答目标 | `REAL_OK` | 会话20260808_185630中“问题二，是的，是水域温度60摄氏度加热10分钟”成功解决问题2；随后回看只剩问题1；全量130项基线 |
| `CLARIFY-TARGET-02` | `P2` | 用户按实验步骤或唯一主题指定回答目标 | `TODO` | 支持“第2步”“离心时间”；匹配不唯一时必须追问，不自动选择 |
| `CLARIFY-TARGET-PERSIST-01` | `P1` | 持久化编号答复与目标问题的关联 | `TODO` | 当前答复原始ASR和结构化事件已保存，target_clarification_id只随内存后台任务传递；导出前需形成可审计关联记录 |
| `COMMAND-01` | `P0` | 定义统一 InteractionCommand 与命令解析器 | `AUTO_OK` | 暂缓/回看已通过处理器接main；结束/肯定仍沿用旧入口，待后续统一迁移 |
| `COMMAND-02` | `P0` | 命令匹配忽略 SenseVoice 句尾情绪符号 | `REAL_OK` | 会话20260808_144408中“这个先跳过。😔”成功暂缓问题1，“查看待确认问题。😔”成功回看；原文保留且均未进入实验事件 |
| `COMMAND-03` | `P0` | 自然命令表达的保守兼容策略 | `AUTO_OK` | Parser新增安全前缀+后缀和自然模式；Prompt新增uncertain兜底；418项通过；已知限制：如果用户在实验台前指着步骤列表说”这个先跳过”，会被判为DEFER——目前语音交互场景下概率极低，若复现则删对应前缀即可 |
| `CLARIFY-MAIN-01` | `P1` | 暂缓和回看命令接入main | `REAL_OK` | 会话20260808_141435中准确命令各执行2次；原始ASR已保存，命令未进入实验事件 |

### F. 确认答复持久化与主流程

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `CONF-STORE-01` | `P1` | ConfirmationRecord 数据结构 | `REAL_OK` | 会话 `20260806_203255` 生成真实确认记录 |
| `CONF-STORE-02` | `P1` | ConfirmationStore JSONL 保存 | `REAL_OK` | confirmations JSONL 已保存真实肯定答复 |
| `CONF-MAIN-01` | `P1` | ASR 确认答复接入 main | `REAL_OK` | 真实语音答复已完成 prepare/save/commit |
| `CONF-MAIN-02` | `P1` | 确认成功终端反馈 | `REAL_OK` | 真实流程显示“已保存对第 1 段的确认答复” |
| `CONF-MAIN-03` | `P0` | 确认答复不作为普通实验事件 | `REAL_OK` | ASR 共 4 条、实验事件仅 3 条，确认答复只进入确认记录 |

### G. 回复时机与会话收尾

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `TIMING-01` | `P1` | LLM 完成后不必等下一段才显示 | `TODO` | 当前被阻塞式录音等待延迟 |
| `TIMING-02` | `P1` | 用户正在说话时不输出/播放回复 | `TODO` | TTS 前硬性依赖 |
| `TIMING-03` | `P1` | 明确安全回复判断接口 | `TODO` | 供终端和未来 TTS 共用 |
| `CLOSING-01` | `P1` | 增加 CONFIRMING 收尾阶段 | `TODO` | 结束记录后仍可回答遗留项 |
| `CLOSING-02` | `P1` | “跳过确认/直接结束”指令 | `TODO` | 避免无法退出收尾阶段 |
| `CLOSING-03` | `P1` | 全部确认完成后进入 IDLE | `TODO` | 状态机集成测试和真实验收 |

### H. TTS 前稳定性验收

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `STABILITY-01` | `P1` | 连续至少 10 段实验口述 | `TODO` | 检查顺序、丢失、积压和延迟 |
| `STABILITY-02` | `P1` | 空响应/网络失败真实降级演练 | `TODO` | 原始数据不得丢失 |
| `STABILITY-03` | `P1` | 确认答复完整真实闭环 | `TODO` | 包含肯定、否定和遗留项 |
| `STABILITY-04` | `P1` | 会话结束总结和记录核验 | `TODO` | 结束后结果可使用 |

### H2. 用户输出与呈现策略

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `PRESENT-01` | `P1` | 定义 PresentationMessage 数据结构 | `AUTO_OK` | 10项协议单测及全量118项通过；移除RECORD消息渠道，增加ScreenTarget |
| `PRESENT-02` | `P1` | 当前回答回执优先于旧后台追问 | `REAL_OK` | 会话20260808_141435中暂缓/回看回执先展示，随后才展示ASR期间完成的旧后台结果 |
| `PRESENT-03` | `P1` | 按认知负担预算组成语音消息组 | `DESIGN` | 默认最多2条、50字、1个问题；支持“回执+相关问题” |
| `PRESENT-04` | `P1` | 内部口述编号与用户实验步骤编号分离 | `TODO` | 确认答复占号导致实验步骤从2跳到4 |
| `PRESENT-07` | `P1` | 指定编号答复完成后的明确状态回执 | `TODO` | CLARIFY-TARGET-01已能正确路由，但后台完成后暂未直接显示“问题N已解决/仍缺少哪些字段”；当前可用回看命令核验 |
| `PRESENT-05` | `P1` | 用户输出与 debug 日志分离 | `TODO` | 状态、路径、token、耗时默认不展示/不朗读 |
| `PRESENT-06` | `P1` | 输出顺序真实验收 | `TODO` | 先确认回执，再在后续安全间隙提出新问题 |
| `PRESENT-INTEGRATE-01` | `P1` | 将一种待确认结果接入统一消息链路 | `TODO` | ASR命令基线后、TTS前实施；先做PendingClarification→PresentationMessage→简单终端Presenter，不一次迁移全部print |
| `PRESENT-STYLE-01` | `P2` | 分离消息语义语调与具体前端/TTS样式 | `DESIGN` | 消息只表达kind/priority/channel/speech policy及可选抽象语调；颜色布局、音色、语速和具体情感参数由适配器决定 |

### H3. 系统故障与实验安全

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `SAFETY-01` | `P1` | 定义系统故障分类和严重程度 | `TODO` | 区分问题类型、严重程度、消息优先级；先覆盖可由程序确定的故障 |
| `SAFETY-02` | `P1` | 将确定的存储/音频故障转换为用户消息 | `TODO` | 存储不可写等关键故障必须明确提醒；可降级故障不得冒充严重危险 |
| `SAFETY-03` | `P3` | 确定 Demo 实验后建立风险规则白名单 | `TODO` | Demo、SOP 和术语尚未确定，当前不提前绑定具体实验风险规则 |
| `SAFETY-04` | `P2` | 实验风险提示的证据等级与确认流程 | `TODO` | 区分 confirmed、suspected、unknown；疑似 ASR 错词不得直接判定危险 |

### H4. 跨模块集成与个人能力拓展

这一组由A维护总体证据，但接口定稿和真实联调必须由相关队友共同确认。它们是“学习更多但不包揽”
的主要入口，不能提前打断ASR和IntentRouter主线。

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `ARCH-01` | `P2` | 维护端到端数据流和模块边界图 | `TODO` | INTENT-02后更新；必须标出数据所有者、失败边界和适配器，不画成所有模块互相调用 |
| `CONTRACT-01` | `P2` | 设备只读查询请求/响应/错误契约 | `TODO` | A/B共同确认；统一equipment_id及带时区时间；契约变更需版本记录 |
| `PLANNING-CLIENT-01` | `P2` | PlanningClient接口和Fake实现 | `TODO` | CONTRACT-01后；A可独立单测，不依赖B服务或数据库 |
| `CONTRACT-TEST-01` | `P2` | 跨仓库JSON契约测试 | `TODO` | Fake和真实服务对同一正常/错误样例给出兼容结构 |
| `PLANNING-CLIENT-02` | `P2` | 只读设备查询HTTP适配器 | `TODO` | 超时、服务不可用和非法响应不得破坏实验原始记录 |
| `E2E-QUERY-01` | `P2` | 语音查询设备端到端验收 | `TODO` | ASR→IntentRouter→PlanningClient→消息；有空/冲突/缺时间/服务失败四类路径 |
| `OBS-01` | `P2` | 跨模块request_id和关键耗时 | `TODO` | 调试信息进入开发日志，不默认显示或朗读给用户 |
| `E2E-DEMO-01` | `P2` | 2～3分钟Demo脚本和验收表 | `TODO` | 三人共同；连续跑通至少3次并包含断网或服务失败降级 |

### I. TTS 与后续阶段

| ID | 优先级 | 任务 | 状态 | 验收证据/备注 |
|---|---|---|---|---|
| `TTS-01` | `P3` | 定义 TTSClient 接口 | `TODO` | 先假客户端单测 |
| `TTS-02` | `P3` | 系统 TTS 第一版 | `TODO` | 不先接 GPT-SoVITS |
| `TTS-03` | `P3` | 增加 SPEAKING 状态 | `TODO` | 播放期间暂停 KWS/VAD |
| `TTS-04` | `P3` | 分句播放、失败降级 | `TODO` | TTS 失败回退终端文本 |
| `TTS-05` | `P3` | 用户打断策略 | `TODO` | 需要状态机和音频资源管理 |
| `TTS-06` | `P3` | 唤醒提示替换为“我在，请说” | `TODO` | 系统 TTS 稳定后 |
| `SOVITS-01` | `P3` | GPT-SoVITS HTTP 服务 | `TODO` | TTS 第一版之后 |
| `SOVITS-02` | `P3` | 超时、缓存、系统 TTS 回退 | `TODO` | 外部服务失败不影响主流程 |
| `LIVE2D-01` | `P3` | Live2D 表现层接入 | `TODO` | TTS 稳定后 |
| `AGENT-01` | `P3` | 白名单计时器/提醒/查询/导出 | `TODO` | TTS 与记录闭环后 |

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

第一版系统 TTS 不应早于输入可靠性、自然控制、输出协调和实验记录闭环。详细执行顺序以
第3.1～3.2节的当前看板和五阶段路线为准，概括如下：

```text
固定语料与ASR基线
→ 自然意图与风险路由
→ 输出协调和确认收尾
→ 会话总结、SessionRecord与Markdown/JSON导出
→ 系统TTS
→ GPT-SoVITS、Live2D与Word/PDF美化
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
| 2026-08-07 | 新增统一交互命令协议和保守解析器 | 新增15项单测通过；消息协议、命令、协调器共40项通过 | 未接main，不需要真实口述 | 项目venv全量回归后进入CLARIFY-09 |
| 2026-08-07 | 执行COMMAND-01验收并检查全量环境 | 相关40项全部通过；全量发现71项但7个测试模块导入失败 | 主venv失效；py314环境缺dotenv且ffmpeg权限失败 | 先修复统一测试环境，再确认全量基线 |
| 2026-08-07 | 完成待确认项暂缓生命周期和稳定编号 | 新增9项测试通过；命令、消息、生命周期、协调器共49项通过 | 未接main，不需要真实口述 | 环境恢复后接入main的暂缓/回看闭环 |
| 2026-08-07 | 暂缓/回看命令接入main并调整当前回复顺序 | 处理器新增5项测试；相关核心54项通过；main语法检查通过 | 待真实口述“这个先跳过/查看待确认问题” | 真实验收后做按问题编号回答 |
| 2026-08-08 | 恢复统一Python 3.11.9测试和运行环境 | 全量118项通过；src.main导入成功 | VAD、KWS、SenseVoice和FSMN-VAD模型加载成功 | 真实口述验收暂缓/回看闭环 |
| 2026-08-08 | 验收暂缓/回看并兼容SenseVoice情绪后缀 | 会话20260808_141435；全量121项通过 | 准确命令和回执顺序通过；带😔命令曾误入事件，现已修复待复验；模糊错词仍不猜测 | 真实口述复验 `COMMAND-02` |
| 2026-08-08 | 真实复验SenseVoice句尾情绪命令 | 会话20260808_144408；沿用全量121项基线 | 带😔的暂缓和回看均成功，原文保留且未进入事件；发现3种自然命令表达误入事件，登记COMMAND-03 | `CLARIFY-TARGET-01` |
| 2026-08-08 | 按稳定问题编号路由同句答案并接入main | 新增6项测试；全量127项通过；main语法检查通过 | 编号不存在/无答案不调用LLM；同字段多问题只更新目标；目标关联尚未独立持久化 | 真实口述验收 `CLARIFY-TARGET-01` |
| 2026-08-08 | 首次真实验收编号回答并修复混合确认死循环 | 会话20260808_183942；新增3项测试；全量130项通过 | LLM已提取水浴/60摄氏度/10分钟，但旧确认标志未关闭；现用明确肯定元数据关闭目标确认且排除疑问句；通用命令误识别登记ASR-CMD-01 | 复验目标回答后立即做命令ASR稳定性 |
| 2026-08-08 | 复验编号回答并确定自然语音演进方向 | 会话20260808_185630；沿用全量130项基线 | 问题2成功解决且问题1保留；“看待确认问题”误入事件并生成问题3，证明应先建命令语料和ASR基线 | `ASR-CMD-01` 先建语料与基线 |
| 2026-08-08 | 收束自然交互、意图路由和消息表现层设计 | 未改业务代码；全量基线仍为130项 | 明确混合路线：ASR尽量准确、低风险意图语义容错、高风险命令确认；消息协议已定义但尚未接main | 明日按 `NEXT_SESSION_HANDOFF_2026-08-09.md` 开始ASR-CMD-01 |
| 2026-08-09 | 建立控制命令固定语料、清单校验器和静态基线报告 | 新增5项测试；全量135项通过 | 使用4次历史真实会话的14条WAV；2条原话因证据不足保持needs_user_label，未自行猜测 | 试听标注2条音频并复跑基线，随后进入ASR-CMD-02 |
| 2026-08-09 | 重整近期执行看板和TTS前五阶段路线 | 未改业务代码；沿用135项基线 | 不需要真实验收；保留完整任务库和历史证据 | `ASR-CMD-REC-01` 独立语料采集器 |
| 2026-08-09 | 用户回听并补齐两条历史音频标签 | 静态基线复跑成功：文本8/14、意图9/14、漏触发5、误触发0 | 两条提示均为“这个先跳过”，但WAV实际只录入“个先跳过”；已分开保存prompt与reference，未把截音归咎于ASR | `ASR-CMD-REC-01` 需改善句首截音并采集24条新语料 |
| 2026-08-09 | 人工复核新会话的6条歧义音频 | 未改业务代码；正式14条基线不变 | “查看/跳过”2条确认句首截断；“记录/移液枪/放入离心机”音频完整但ASR错误；第1条再次确认WAV与ASR均为“那我再问”，属于音频内容与提示稿不同 | 采集器解决句首保留并增加录后确认，再用标准流程重录 |
| 2026-08-09 | 定义控制命令语料采集数据结构 | 新增11项测试；全量146项通过 | 未接真实麦克风；不需要真实录音验收 | `ASR-CMD-REC-STORE-01` 追加式JSONL存储 |
| 2026-08-09 | 根据三人分工讨论补充个人范围和跨模块学习任务 | 未改业务代码；沿用146项基线 | 分工尚待团队确认；明确A主责语音会话，同时通过契约、客户端、集成和E2E学习整体工程，不接管B数据库或C前端 | 当前仍先做`ASR-CMD-REC-STORE-01`；INTENT-02后启动CONTRACT-01 |
| 2026-08-09 | 完成语料录音尝试的原子JSONL存储 | 新增6项存储测试；专项17项、全量152项通过 | 未接麦克风；不需要真实录音验收 | `AUDIO-PREROLL-01` 先实现纯PreRollBuffer |
| 2026-08-09 | 完成纯音频PreRollBuffer | 新增10项测试；全量162项通过 | 未接麦克风和现有VAD，不代表句首问题已真实解决 | `AUDIO-PREROLL-INTEGRATE-01` 假边界组装测试 |
| 2026-08-09 | 完成预缓冲与VAD语音段的安全组装契约 | 新增11项测试；全量173项通过 | 未接VadAudioRecorder和真实麦克风；明确重叠才去重，声明不一致立即失败；确认Sherpa SpeechSegment提供start | `AUDIO-PREROLL-RECORDER-01` 假流时间线接入 |
| 2026-08-09 | 为预缓冲增加录音会话内的绝对采样时间线 | 新增7项测试；全量180项通过 | 未接VadAudioRecorder；PreRollSnapshot已能表达[start,end)，溢出和clear行为明确 | 继续`AUDIO-PREROLL-RECORDER-01`假流接入 |
| 2026-08-09 | 将句首预缓冲按Sherpa采样时间线接入VadAudioRecorder | 时间线对齐7项、录音器4项；全量191项通过 | 使用假音频流/假VAD验收；尚未证明真实设备上的句首完整性 | `AUDIO-PREROLL-REAL-01`真实WAV回听 |
| 2026-08-09 | 为当前看板、暂缓项、学习型任务和任务总表增加P0～P3优先级 | 文档结构检查通过；沿用191项代码测试基线 | 不涉及真实功能验收 | 仍为`P0 AUDIO-PREROLL-REAL-01`真实WAV回听 |
| 2026-08-09 | 建立真实句首验收工具并严格分开人工回听与ASR阶段 | 新增4项测试；验收工具+录音器专项8项、全量195项通过 | 等待用户真实录制9条并标记完整/截断/重复 | `P0 AUDIO-PREROLL-REAL-01`真实WAV回听 |
| 2026-08-09 | 首轮句首真实验收失败并修复麦克风就绪提示时机 | 新增1项顺序测试；专项9项、全量196项通过 | 9个最终样本中5完整、4截断、0重复；另保留1次人工重录；定位提示早于InputStream打开 | 第二轮同样9句复验，通过后再运行ASR和提交GitHub |
| 2026-08-09 | 用户暂不方便录音，保留真实复验并完成通用语料采集协调器 | 新增7项测试；相关28项、全量203项通过 | 未新增真实录音；首轮失败证据和待复验状态完整保留 | `P0 ASR-CMD-REC-PROMPTS-01`提示稿计划与断点恢复 |
| 2026-08-09 | 完成版本化24条控制语料计划和断点恢复规则 | 新增7项测试；相关18项、全量210项通过 | 不需要真实录音；专项9条脚本已改为从JSON计划加载 | `P0 ASR-CMD-REC-CLI-01`正式独立采集入口 |
| 2026-08-09 | 完成正式独立控制语料采集入口 | 新增5项会话测试；--status烟雾测试通过；全量215项通过 | 未打开真实麦克风；真实24条采集按用户条件后推 | `P0 ASR-CMD-02-LANGUAGE-01`既有14条WAV中文参数对照 |
| 2026-08-09 | 建立SenseVoice固定中文参数对照工具 | 新增3项比较测试，连同静态基线共8项先在3.14纯逻辑环境通过 | 已从当前安装源码确认支持`zh`；当时将沙箱拒绝执行误判为`.venv`目标消失，下一行已纠正 | 复核3.11环境并运行语言对照脚本 |
| 2026-08-09 | 纠正环境误判并完成固定中文参数真实对照 | Python3.11全量218项通过；比较工具8项通过 | `.venv`始终正常，先前为沙箱执行限制；14条WAV结果为auto文本8/14、意图9/14，zh文本8/14、意图10/14，但存在文本回退 | 先做错误归因和`INTENT-01`，热词后推 |
| 2026-08-09 | 定义统一意图风险与执行边界 | 新增7项专项测试；全量225项通过 | 纯策略层不需要麦克风；未接main且未启用语义或LLM候选 | `P0 INTENT-02`第一步连接精确解析与策略决策 |
| 2026-08-09 | 完成精确IntentRouter | 新增7项路由测试；路由/策略/解析器相关30项、全量232项通过 | 不需要真实麦克风；自然表达仍保守返回normal；未接协调器和main | `P0 INTENT-02-SEMANTIC-01`第一批本地自然表达候选 |
| 2026-08-09 | 定义LLM意图分类接口与严格候选结构 | 新增10项专项测试；全量242项通过 | Fake实现不调用外部服务；模型候选无执行权，非法/越权JSON被拒绝 | `P0 INTENT-02-CLASSIFIER-ROUTE-01`先用Fake接路由 |
| 2026-08-09 | FakeIntentClassifier接入精确路由与风险策略 | 新增6项集成测试；全量248项通过 | 无网络和真实LLM；精确优先、自然查看、高风险结束、指定答复、普通记录和超时降级均已验证；尚未调用ReplyCoordinator | `P0 INTENT-02-LLM-01`适配器与严格提示词 |
| 2026-08-09 | 增加模型弃权状态和严格意图提示词合同 | 提示词2项、意图相关27项、全量252项通过 | 未调用真实LLM；uncertain安全降级且不执行控制动作；动态输入以不可信JSON传递 | `P0 INTENT-02-LLM-ADAPTER-01`Fake客户端适配器 |
| 2026-08-09 | 实现LLMIntentClassifier适配器 | 新增5项适配器测试；全量257项通过 | Fake LLMClient，无网络；提示词传递、matched/uncertain、非法响应和客户端异常已覆盖 | `P0 INTENT-02-LLM-INTEGRATION-01`模块整链路 |
| 2026-08-09 | 完成Fake LLM意图模块整链路 | 新增7项模块集成测试；全量264项通过 | 无网络；从Fake客户端到风险出口的七类分支全部通过，未接main和ReplyCoordinator | `P0 INTENT-02-LLM-REAL-01`独立DeepSeek烟雾与延迟 |
| 2026-08-09 | 建立并完成真实DeepSeek意图烟雾 | 脚本结构及指标测试新增2项；全量266项通过 | 固定5条非敏感文本5/5符合预期；均1次请求；1.700～1.884秒，平均约1.808秒；高风险结束只请求确认 | `P0 INTENT-02-ARCH-01`先解决两次串行调用取舍 |
| 2026-08-09 | 对比独立两次与统一一次LLM理解 | 新增3项统一响应合同测试；全量269项通过；比较脚本可保留完整配对并记录失败轮次 | 首次统一输出因追问字段不一致被严格拒绝后补规则；有效配对：独立5.809/5.621秒，统一10.980冷/2.636热；后续统一请求两次遇SSL断连，未伪造完整均值 | 采用精确快速路径＋统一理解方向，先做`INTENT-02-UNIFIED-CONTRACT-01` |
| 2026-08-09 | 正式化统一输入理解数据合同 | 新增7项专项测试；Python3.11全量276项通过 | 三分支显式互斥；模型不能覆盖raw_text、夹带未选分支或把uncertain伪装成control；网络/格式失败边界为未分类NOTE且无控制候选 | 下一轮单独定义正式统一提示词与Processor，仍不接main |
| 2026-08-09 | 正式统一Prompt与Processor通过Fake验收 | 合同与Processor相关15项、Python3.11全量284项通过 | 动态上下文作为不可信JSON发送；三类合法输出严格解析；格式/网络失败保留原文和指标并降级为NOTE，不产生控制候选 | `INTENT-02-UNIFIED-REAL-01`固定非敏感文本真实烟雾，仍不接main |
| 2026-08-09 | 正式统一理解完成真实DeepSeek烟雾 | 新增2项脚本测试；Python3.11全量286项通过 | 首轮4/5，实验实体数值类型漂移被合同拒绝；修正Prompt后5/5，均1次成功、1.614～2.441秒；原始响应未打印/保存 | `INTENT-02-UNIFIED-ROUTE-01`先做精确快速路径＋统一理解Fake模块组合 |
| 2026-08-09 | 组合精确快速路径与正式统一理解 | 新增7项Fake模块集成测试；Python3.11全量293项通过 | 精确控制零LLM调用；未命中一次统一理解；所有LLM控制候选继续经过风险策略；不确定和失败不执行控制 | `INTENT-02-UNIFIED-DISPATCH-01`先定义安全分派合同，不直接改main |
| 2026-08-09 | 完成24条控制命令真实语料采集 | 24/24 accepted；31次尝试；31个WAV全部存在 | 7次重录请求作为失败证据保留；断点恢复只展示3条未接受样本，补录后每个样本恰有一条accepted | `ASR-CMD-01`后续使用这批固定WAV生成可重复的新基线；音频不上传GitHub |
| 2026-08-09 | 生成24条新语料真实ASR基线 | 新增4项Fake测试；Python3.11全量297项通过；同参数两次真实运行汇总一致 | 文本13/24、精确规则意图11/24、控制漏触发13、误触发0；13条漏触发全部由精确规则不覆盖自然表达造成，ASR额外意图漏触发0 | 保留统一意图理解路线；专业词“移液枪/水浴/滴定管”等再进入单变量ASR增强对照 |
| 2026-08-10 | 完成专业词后处理候选对照 | 新增4项Fake测试；Python3.11全量301项通过；24条真实保存文本完成对照 | SenseVoice不支持模型级hotword，任务BLOCKED；后处理候选术语0/4→4/4、文本13/24→16/24、零回退，原文未覆盖 | 不接main；回到`INTENT-02-UNIFIED-DISPATCH-01`安全分派合同 |
| 2026-08-10 | 新建热词模型候选验证任务 | 仅更新任务合同；沿用全量301项基线 | 新任务`ASR-CMD-02-MODEL-CANDIDATE-01`定义能力探针、四组同源对照、指标与独立语音复验门槛；不把可接收参数误当成模型已消费参数 | 当前唯一主线仍为`INTENT-02-UNIFIED-DISPATCH-01`；候选验证后续独立执行，不换模型、不接main |
| 2026-08-10 | 完成模型无关ASR后端合同与默认SenseVoice适配 | 新增7项专项、ASR下游38项、Python3.11全量308项通过；新工厂真实识别18.072秒固定WAV，识别耗时1.922秒 | main和真实脚本改由工厂创建后端；统一ASRResult及原始模型文本不变；未知后端提前失败；模型缓存仍在本机且未进入仓库 | `ASR-CMD-02-MODEL-CANDIDATE-01`后续只需新增候选适配器；当前正式主线仍回到`INTENT-02-UNIFIED-DISPATCH-01` |
| 2026-08-10 | 新建ASR与LLM原始证据命名合同任务 | 仅更新任务合同；沿用全量308项基线 | `ASR-EVIDENCE-CONTRACT-01`明确五层命名、不可覆盖边界和旧JSONL兼容迁移要求；本轮未直接重命名生产字段 | 先完成`INTENT-02-UNIFIED-DISPATCH-01`；随后在固定WAV主链路集成前实施证据合同 |
| 2026-08-10 | 完成ASR证据schema v2与历史只读兼容 | 新增10项合同测试；专项17项、下游47项、Python3.11全量318项通过 | 182条历史v1记录可读且SHA-256不变；真实18.072秒WAV生成v2，模型原始文本与忠实转写均非空且不同，识别1.482秒 | 回到`INTENT-02-UNIFIED-DISPATCH-01`；之后固定WAV主链路只传`asr_transcript`，不传模型标签或纠错候选 |
| 2026-08-10 | 完成统一路由结果安全分派合同 | 新增10项Planner专项、4项Router→Planner Fake集成；相关21项、Python3.11全量332项通过 | 纯合同不需要真实麦克风或外部LLM；六类目标及最小权限已固定，分派器没有执行依赖 | `INTENT-02-UNIFIED-DISPATCH-INTEGRATION-01`先做固定输入旁路可观察链路，仍不执行状态写入 |
| 2026-08-10 | 完成固定文本统一路由安全分派旁路 | 新增6项旁路专项；Python3.11全量338项通过；五类固定脚本烟雾输出符合预期 | Fake ASR/Processor，不代表真实模型效果；报告不含模型原始文本且没有执行依赖 | `INTENT-02-UNIFIED-DISPATCH-WAV-01`使用固定WAV和真实ASR/LLM做旁路验收，仍不接main |
| 2026-08-10 | 按教学约定整理累计工作区和交接文档 | Python3.11全量392项重新运行通过；compileall与git diff --check通过 | 当前仍在main，origin仍指向Kyra25906/asr_demo；20个已跟踪文件修改及30个新增代码/脚本/测试文件均为累计工作，未删除或提交；.env、真实录音、results、模型和venv保持忽略 | 下一项仍为`INTENT-02-UNIFIED-PROMPT-MISSING-FIELDS-01`；提交总仓前先确认远程、新建非main分支并按能力拆分提交 |
| 2026-08-11 | 完成统一Prompt缺失字段能力对齐 | Python3.11全量392项通过；1项Prompt合同关键词测试新增 | 真实DeepSeek以"将溶液加热。"复验：missing_fields=['temperature','duration']、should_ask_follow_up=True、follow_up_question="加热到什么温度？需要加热多长时间？"、降级=False、1次成功2.32秒 | 等待用户决定下一项优先级；可选`INTENT-02-REPLY-GATE-01`接入ReplyCoordinator、创建PR或真实验收pre-roll |
| 2026-08-11 | 完成ClarificationAction→ReplyCoordinator执行器 | Python3.11全量415项通过（+23项新测试） | ReplyCoordinator新增4个原子方法；新建ClarificationExecutor覆盖7种动作类型；项目拆平消除嵌套路径问题 | 下一步可接入main.py影子位或创建PR推远程 |
| 2026-08-11 | 项目拆平+影子真实复验+推送远程 | 415项通过；推送到total/codex/asr-demo-unified-understanding | 会话`20260811_103134`影子正确输出create+('temperature','duration')；旧流程正常创建追问；keywords.txt编码修复（UTF-16 LE→UTF-8） | 下一项设为`COMMAND-03`自然控制表达兼容 |
| 2026-08-11 | 完成COMMAND-03自然控制表达兼容 | 418项通过（+3项parser/评测测试） | DEFER新增6个安全前缀+跳过后缀；REVIEW新增2条自然模式；Prompt新增uncertain兜底 | 下一项`INTENT-02-REPLY-GATE-02`ANSWER实体填充 |
| 2026-08-11 | 完成REPLY-GATE-02 ANSWER实体填充 | 422项通过 | AnswerEntityExtractor+answer_clarification；统一理解control分支supplied_entities优化 | 下一项`INTENT-02-REPLY-GATE-03`影子接入执行器 |
| 2026-08-11 | 完成REPLY-GATE-03 影子位接入执行器 | 422项通过 | ShadowObservation新增executed字段；observe()内接executor.execute()；新增UNIFIED_SHADOW_EXECUTE_ENABLED开关；main.py创建executor并传入 | 下一项：真实验收 |

## 7. 每轮结束时必须更新

1. 更新对应任务的状态。
2. 填写自动测试数量和结果。
3. 如果进行了真实验收，记录 session_id 或日志证据。
4. 更新“当前唯一下一项”。
5. 在维护日志追加一行。
6. 如果文件结构变化，同步更新任务备注和交接文档。
7. 开发、测试或真实验收中发现的新问题，必须在本清单登记任务 ID 或写入维护日志，不能只保留在对话中。
8. 新问题需要注明发现来源、影响、依赖关系和建议处理时机；未确定方案时标记为 `TODO` 或 `DESIGN`，不得假装已经解决。

# 补充内容
知识库+RAG 帮 LLM 更精准地结构化口述（补全缺省参数、纠正专业词、发现 SOP 偏差），用户画像 减少重复追问（记住个人默认值和偏好），两者都是增强现有链路质量而非新增功能模块。

---
当前预留接口建议（3 处，不动业务逻辑）

1. SessionContext 扩展一个可选字段

当前 CTX-01 传"最近 N 条事件"给 LLM。在构建上下文时增加一个可选参数，现在什么都不传：

# 构建 LLM prompt 时
context = {
    "recent_events": [...],   # 已有
    "user_profile": {},       # 新增，当前为空字典
    "knowledge_hints": [],    # 新增，当前为空列表
}

user_profile 以后填：默认离心转速、常用体积、交互详细程度等。
knowledge_hints 以后填：SOP 匹配片段、术语纠错候选、安全提示等。

两个字段今天为空，LLM prompt 构造逻辑不需要改，只是数据结构上占位。

2. PendingClarification 追问增加来源标记

当前 CLARIFY-01/09 的追问结构里，追问只有 source_segment_id 和 missing_fields。增加一个可选字段标记追问的"知识来源"：

{
    "source_segment_id": 3,
    "missing_fields": ["离心时间"],
    "knowledge_source": null   # 新增，以后可以是 "sop:protocol_42" 或 "rag:exp_20260801"
}

用途：以后知识库触发的追问和 LLM 自己猜的追问可以区别对待——知识库触发的可以降低重复询问频率，LLM 猜的保持现有确认逻辑。

3. ExperimentEvent 实体字段预留标准化引用

当前 LLM-07 产出操作/观察/测量/异常四类事件。实体信息（试剂名、设备名、数值）目前混在 normalized_text 里。在数据结构中增加一个可选的对象字段*：

{
    "type": "observation",
    "normalized_text": "溶液变为蓝色",
    "entities": {               # 新增，当前为 null
        "reagent": null,
        "equipment": null,
        "measured_value": null,
        "matched_term": null
    }
}

matched_term 以后存知识库匹配到的标准术语（如 ASR 的"一液枪"匹配到标准词"移液枪"），reagent 以后可以关联到化学品属性库。

---
优先级

┌─────┬─────────────────┬─────────────┬───────────────────────────┐
│ 序  │      位置       │    成本     │           收益            │
│ 号  │                 │             │                           │
├─────┼─────────────────┼─────────────┼───────────────────────────┤
│ 1   │ SessionContext  │ 改一处构造  │ 画像和 RAG 都有了注入点   │
│     │ 加两个空字段    │             │                           │
├─────┼─────────────────┼─────────────┼───────────────────────────┤
│     │ PendingClarific │ 改一个数据  │ 区分"有依据的追问"和"猜测 │
│ 2   │ ation 加 knowle │ 结构        │ 追问"                     │
│     │ dge_source      │             │                           │
├─────┼─────────────────┼─────────────┼───────────────────────────┤
│ 3   │ ExperimentEvent │ 改一个数据  │ 实体可追溯、可纠错、可关  │
│     │  加 entities    │ 结构        │ 联外部库                  │
└─────┴─────────────────┴─────────────┴───────────────────────────┘

三处都是纯数据结构预留，不改一行业务判断逻辑。

---
注：这个可能已在你的领域记录设计中被覆盖（OUTPUT_PRESENTATION_POLICY.md 2.1 节的 ExperimentEvent 提到"实体"），如果已有字段就直接用，不需要重复加。
