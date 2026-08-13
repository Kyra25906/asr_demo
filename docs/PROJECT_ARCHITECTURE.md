# asr_demo 项目架构设计文档

## 一、项目概览

**asr_demo** 是一个语音驱动的实验记录助手。实验人员用自然语言口述操作步骤（"将溶液加热到60摄氏度"、"加入5毫升试剂"），系统通过 ASR 转录、LLM 结构化理解、追问机制补齐缺失字段，最终将结构化实验记录持久化为 JSONL 证据文件。

当前阶段：**文本终端交互**，无 TTS 语音输出（P3 远期规划）。

> 2026-08-12 实现状态说明：统一理解链已经在真实会话中接管主要处理，但代码仍保留
> shadow 命名、双 flag 和旧 `SegmentProcessor.submit()` 回退路径。因此下图同时包含
> 当前过渡实现和目标边界，不能把它理解为清理已经完成。

---

## 二、总体架构哲学

### 2.1 设计原则

| 原则 | 含义 | 为什么 |
|---|---|---|
| **数据不可变性** | 跨模块边界的合同全部用 `frozen=True` dataclass，构造时校验 | 一旦通过校验，下游可以无条件信任；避免"半成品"数据在模块间传播 |
| **纯逻辑与副作用分离** | Planner/Acceptor 纯计算，不访问文件、网络、状态机 | 可独立单元测试；行为可预测；不会因为外部资源状态产生意外 |
| **协议注入 + 工厂** | 业务代码依赖 `Protocol`，工厂函数创建具体实现 | 测试时可替换 Fake；真实后端更换不影响业务逻辑 |
| **失败降级，不崩溃** | LLM 调用失败 → 降级为 NOTE 事件，不抛异常中断会话 | 实验人员正在做实验，崩了就是数据丢失 |
| **先存原始数据，后推断** | ASR 原文先写入 JSONL，LLM 结构化结果后写入 | 原始证据永远可回溯；模型推断错误不会覆盖原始事实 |
| **版本化证据格式** | ASRResult v2 可读 v1，但只写 v2 | 格式演进不破坏历史数据 |

### 2.2 分层架构

```
┌─────────────────────────────────────────────┐
│  main.py  —— 组合根 + 会话循环               │
│  负责：创建对象、连接依赖、控制主循环          │
├─────────────────────────────────────────────┤
│  src/core/  —— 领域逻辑层                      │
│  纯数据合同 + 纯规划器 + 状态管理              │
│  不访问文件、网络、麦克风、模型               │
├─────────────────────────────────────────────┤
│  src/asr/   │ src/llm/   │ src/audio/       │
│  src/wakeword/          │ src/storage/      │
│  基础设施层 —— 有副作用的适配器               │
└─────────────────────────────────────────────┘
```

**核心约束**：领域层（`src/core/`）不导入基础设施层的具体实现。领域层的 Planner、Acceptor、Coordinator 只操作不可变数据合同，副作用由 `main.py` 和 Executor 在边界执行。

---

## 三、数据流全景

### 3.1 完整链路

```
用户说话
  │
  ▼
WakeWordDetector  ──→  "小科小科" 唤醒
  │
  ▼
VadAudioRecorder  ──→  Silero VAD + 0.5s 预录制 → vad_segment_*.wav
  │
  ▼
SenseVoiceBackend  ──→  FunASR SenseVoiceSmall → ASRResult (v2 证据)
  │
  ▼
InteractionCommandParser  ──→  精确规则匹配
  │                              ├─ 控制命令 → 快速路径（零 LLM）
  │                              └─ 其他文本 → 进入统一理解
  ▼
UnifiedUnderstandingRouter
  │                              ┌─ experiment  → 实验记录链路
  ├─ UnifiedUnderstandingProcessor (一次 LLM) ──┼─ control     → 风险策略与控制候选
  │                              └─ uncertain   → 弃权，不伪装成事实
  ▼
UnifiedDispatchPlanner  ──→  纯规则规划，产出 DispatchPlan
  │
  ▼
采用合同 / 当前 main 过渡接线  ──→  副作用边界：
  │                     - 写入 ASR 到 JSONL
  │                     - 结构化事件写入 JSONL
  │                     - 更新 ReplyCoordinator 状态
  ▼
ReplyCoordinator  ──→  管理待确认问题
  │                     - 追问缺失字段
  │                     - 确认 ASR 误识别
  │                     - 版本守卫防并发冲突
  ▼
终端输出（未来：TTS 语音输出）
```

### 3.2 当前实现与目标架构的差距

| 差距 | 当前表现 | 目标 |
|---|---|---|
| 配置不变量 | 两个 shadow flag 可形成非法组合 | 配置加载时拒绝非法组合，最终删除过渡 flag |
| 证据提交顺序 | 部分澄清动作可能先改内存、后写 ASR | 统一采用 prepare → persist → commit |
| 会话上下文 | 新链没有传入或更新 `SessionContext` | 每段读取提交前快照，事件落盘成功后更新上下文 |
| 执行边界 | main、observer、executor 共同承担过渡接线 | main 只组合依赖，正式执行器负责原子提交 |
| 错误恢复 | 唤醒/会话异常统一立即重试 | 区分暂时性与不可恢复错误，增加退避和退出边界 |

这些问题不会否定已有合同设计，但必须在接入查询、安全或 RAG 前修复，否则新能力会继承
不一致的证据顺序和空会话上下文。

### 3.3 三条处理路径

| 路径 | 触发条件 | LLM 调用 | 示例 |
|---|---|---|---|
| **精确命令快速路径** | 文本匹配到控制命令词表 | 0 次 | "结束实验记录"、"问题1 60度" |
| **统一理解路径** | 文本不是控制命令 | 1 次 | "将溶液加热到60摄氏度" |
| **降级路径** | LLM 调用失败或格式非法 | 0 次有效 | 网络超时 → NOTE 事件 |

---

## 四、模块职责与设计决策

### 4.1 `src/asr/` — 语音识别层

**核心决策：Protocol 隔离 + 版本化证据格式**

```python
# 业务代码只依赖这个协议，不导入 FunASR
class ASRBackend(Protocol):
    def recognize(self, audio_path, *, language="auto") -> ASRResult: ...
```

**ASRResult v2 的关键区分**：
- `asr_transcript`：经过去情绪、去标点后处理的可信转录文本——**全链路消费这个字段**
- `asr_model_raw_text`：模型原始输出（含情绪标签如 `<|HAPPY|>`）——**仅用于调试回溯**

**为什么这样设计**：
- SenseVoice 的 `rich_transcription_postprocess` 会做情绪标签转换和 ITN（逆文本归一化），结果才是"用户实际说的内容"
- 保留原始输出是为了防止后处理 bug 导致信息丢失——出问题时可以回溯
- v1/v2 共存读写保证了历史数据不会被新代码破坏

### 4.2 `src/llm/` — 模型访问层

**核心决策：两代处理器共存 + 统一路由 + 降级策略**

**旧链（`ExperimentLLMProcessor`）**：
- 两次 LLM 调用：`analyze_segment` → `summarize`（可选）
- 通过 `SegmentProcessor` → `SessionProcessingQueue` 在后台单线程执行
- 优点：经过大量验收，稳定可靠
- 缺点：两次调用延迟高；分析和控制命令分离，需要额外协调

**新链（`UnifiedUnderstandingProcessor` + `UnifiedUnderstandingRouter`）**：
- **一次 LLM 调用**同时完成：意图分类 + 实体提取 + 控制命令识别
- `UnifiedUnderstandingRouter.route()` 决策逻辑：
  1. 先用 `InteractionCommandParser` 做精确规则匹配（零 LLM）
  2. 匹配到控制命令 → 快速路径返回
  3. 没匹配到 → 调用一次 `UnifiedUnderstandingProcessor`
- 输出严格三选一：`experiment` XOR `control` XOR `uncertain`

**为什么从两次调用改为一次**：
- 减少延迟：一次 LLM 往返替代两次
- 降低不一致风险：分析和意图分类在同一上下文中完成
- 降低成本：token 消耗减半

**降级策略**：
- `OpenAICompatibleLLMClient` 只在 429/5xx/超时 时重试
- 最终失败 → `UnavailableLLMClient` 兜底
- 上层 `UnifiedUnderstandingProcessor.understand()` 捕获所有异常 → `build_degraded_understanding()` 生成 NOTE 事件
- **核心原则：LLM 挂了，实验记录不丢**

### 4.3 `src/core/` — 领域逻辑层

这是项目架构最密集的部分，26 个文件遵循严格的职责分离。

#### 4.3.1 意图识别与风险策略

**三层识别机制**：

```
Layer 1: InteractionCommandParser (精确规则，零 LLM)
  ├─ 硬编码词表匹配（"结束实验记录" → END_SESSION）
  ├─ 正则模式匹配（"问题3 60度" → TARGETED_ANSWER）
  └─ 安全前缀/后缀匹配（防误触发："跳过过滤步骤" ≠ DEFER）

Layer 2: IntentClassifier (语义分类，可选 LLM)
  └─ 对 Layer 1 无法匹配的文本做意图分类

Layer 3: UnifiedUnderstandingProcessor (统一 LLM)
  └─ 同时完成意图 + 实体 + 控制分支识别
```

**IntentPolicy — 风险分级策略**：

| 意图类型 | 风险等级 | 精确规则命中 | LLM 候选 |
|---|---|---|---|
| NORMAL | NONE | → 实验链路 | → 实验链路 |
| REVIEW_PENDING | LOW | → 需要上下文 | → 需要上下文 |
| DEFER_CURRENT | MEDIUM | → 需要上下文 | 不可逆 → 不执行 |
| AFFIRM/DENY | MEDIUM | → 需要上下文 | 不可逆 → 不执行 |
| TARGETED_ANSWER | MEDIUM | → 需要上下文 | 不可逆 → 不执行 |
| END_SESSION | HIGH | → 直接执行 | → **必须二次确认** |

**为什么这样设计**：
- 精确规则优先：能确定的事不浪费 LLM 调用，且不会产生 LLM 幻觉
- 风险越高，证据要求越严格：HIGH 风险操作即使是 LLM 候选也要用户确认
- 可逆性影响决策：可逆操作允许语义容错，不可逆操作必须更谨慎

#### 4.3.2 分派系统

**UnifiedDispatchPlanner** — 纯规则规划器：

```
UnifiedRouteResult
  │
  ▼
UnifiedDispatchPlanner.plan()
  │
  ├─ 降级      → DEGRADED_NOTE     (保存口述但不结构化)
  ├─ 弃权      → ABSTENTION        (模型说不理解，不伪装)
  ├─ 实验理解  → EXPERIMENT_PIPELINE (进入结构化存储)
  ├─ 需要上下文 → CLARIFICATION_CONTEXT (等用户回答追问)
  ├─ 结束执行  → END_SESSION_EXECUTION (精确命令，直接结束)
  ├─ 结束确认  → END_SESSION_CONFIRMATION (LLM候选，二次确认)
  └─ 不执行    → ABSTENTION        (证据不足)
```

**关键设计**：
- Planner 是纯函数，不持有任何状态、文件句柄、网络连接
- 产出 `UnifiedDispatchPlan` 后，由 `DispatchExecutor` 执行副作用
- 每个 destination 对应唯一的最小权限（`UnifiedDispatchPermission`）——下游只能做分派允许的事

#### 4.3.3 追问协调系统

**ReplyCoordinator** — 会话级追问状态管理：

```
ingest_analysis()
  ├─ 提取已提供字段 → 自动填充旧问题的 missing_fields
  ├─ 需要追问 → 注册新的 PendingClarification
  └─ 确认 ASR 推测 → 标记旧问题已确认

pop_next_reply()
  └─ 按段号顺序返回最早的未播报问题

prepare_confirmation() → 外部保存 → commit_confirmation()
  └─ 两阶段提交 + 版本守卫，防止并发冲突
```

**PendingClarification 的生命周期**：

```
ACTIVE ──→ DEFERRED ──→ ACTIVE (重新激活)
  │           │
  ├───────────┼──→ RESOLVED (字段补齐或确认)
  │           │
  └───────────┴──→ RESOLVED (过期)
```

**为什么需要版本守卫（revision）**：
- `supply_fields`、`defer`、`confirm` 每次操作都会 `revision += 1`
- 外部调用者必须先 `prepare_confirmation()` 获取 `expected_revision`，保存成功后再 `commit_confirmation()`
- 如果两次操作之间状态被其他路径修改，`commit` 会因版本不匹配而拒绝
- 防止：用户口头回答和 LLM 自动提取同时修改同一个问题的状态

### 4.4 `src/audio/` — 音频采集层

**核心决策：VAD + 预录制缓冲区**

```
VadAudioRecorder:
  ┌──────────────────────────────────────────┐
  │  PreRollBuffer (0.5s, deque of float32)  │
  │  持续写入，始终保持最近 0.5s 音频          │
  └──────────────────────────────────────────┘
                    │
                    ▼
  Silero VAD (sherpa-onnx, threshold=0.25)
                    │
        ┌───────────┼───────────┐
        ▼                       ▼
   语音开始                 语音结束 (静音 > 2s 或 超过 30s)
        │                       │
        └───────┬───────────────┘
                ▼
  TimelineSpeechAssembler
  ├─ 从预录制缓冲区取 0.5s 前置音频
  ├─ 验证样本重叠（防数据丢失）
  └─ 拼接为完整 vad_segment_*.wav
```

**为什么需要预录制缓冲区**：
- VAD 检测有固有延迟——当它判断"语音开始"时，第一个音素可能已经过去了
- 0.5s 预录制确保句首不被截断，对中文短指令（如"加热"）尤为重要
- `TimelineSpeechAssembler` 验证重叠样本数，防止拼接时出现音频间隙

### 4.5 `src/storage/` — 持久化层

**三种 JSONL 存储**：

| 存储 | 文件 | 内容 |
|---|---|---|
| `ASRResultStore` | `results/asr_segments.jsonl` | 原始转录证据 |
| `ExperimentEventStore` | `results/experiment_events.jsonl` | 结构化实验事件 |
| `ConfirmationStore` | `results/experiment_confirmations.jsonl` | 确认/答复记录 |

**共同设计**：
- 原子追加：先写临时文件，再替换原文件
- `ConfirmationStore` 写入前去重（扫描已有记录）
- 所有写入由 `main.py` 控制时序，存储层自身不做业务判断

---

## 五、新旧链路过渡策略

### 5.1 当前状态：统一链已接管，影子过渡代码待清理

```
用户口述
  │
  ├──→ 当前正式路径：统一理解 → 采用合同 → main 过渡写入
  │      └─ 真实会话已验证零旧 LLM 重复调用
  │
  └──→ 仍保留的回退代码：SegmentProcessor → SessionProcessingQueue
         └─ 受旧 flag 控制，待删除，不再作为目标架构
```

**两个开关**：
- `UNIFIED_SHADOW_ENABLED`：是否构建影子观察器（只读运行新链路）
- `UNIFIED_SHADOW_EXECUTE_ENABLED`：是否让新链路真正写入（替代旧链路）

**当前任务**：先修配置不变量、证据提交顺序和 SessionContext 断链，再执行 INTENT-02 五步清理——删除开关、删除旧提交分支、统一命令入口、重命名影子概念、真实验收。

### 5.2 为什么当时采用影子模式

1. **零风险对比**：新旧链路同时运行，可对比输出差异
2. **渐进验证**：先观察（read-only）→ 确认正确 → 切换写入
3. **快速回退**：出问题只需关掉 `EXECUTE` 开关，旧链路继续工作
4. **持续交付**：每一步都是可工作的系统，不需要长时间停服重构

影子模式已经完成验证使命，不应继续承载新功能。查询、安全和 RAG 必须接入清理后的单一路径。

---

## 六、设计模式总结

| 模式 | 应用位置 | 目的 |
|---|---|---|
| **Protocol + DI** | ASRBackend, LLMClient, IntentClassifier, DispatchExecutor | 测试可替换，实现可切换 |
| **Factory** | create_asr_backend, create_llm_client | 集中创建逻辑，fail-fast |
| **Frozen Dataclass + 校验** | 所有跨模块合同 | 构造即正确，下游无条件信任 |
| **纯 Planner + 副作用 Executor** | UnifiedDispatchPlanner, ClarificationActionPlanner | 核心逻辑可单元测试 |
| **两阶段提交** | ReplyCoordinator prepare/commit | 外部 I/O 成功才修改内存状态 |
| **影子/ Pilot** | UnifiedShadowObserver | 新旧链路共存验证 |
| **单一工作线程 + 背压** | SessionProcessingQueue (max_pending_tasks=4) | ASR 不会无限领先 LLM |
| **策略模式** | IntentPolicyEvaluator | 风险等级决定执行边界 |
| **状态机 + 观察者** | StateManager (FMS) | 应用生命周期可观测 |

---

## 七、关键数据合同

### 7.1 UnifiedUnderstandingResult（统一理解输出）

```
┌─────────────────────────────────────────┐
│ UnifiedUnderstandingResult (frozen)     │
│ ├─ raw_text: str                        │
│ └─ 三选一：                              │
│     ├─ experiment: ExperimentUnderstanding │ → 实验记录链路
│     ├─ control: ControlUnderstanding      │ → 控制命令链路
│     └─ uncertain: UncertainUnderstanding  │ → 弃权，记录但不结构化
└─────────────────────────────────────────┘
```

### 7.2 ProcessOutcome[T]（通用结果包装）

```
┌──────────────────────────────────┐
│ ProcessOutcome[T] (frozen)       │
│ ├─ value: T                      │ ← 成功结果
│ ├─ degraded: bool                │ ← 是否降级
│ ├─ error: str | None             │ ← 错误信息
│ ├─ llm_attempts: int             │ ← LLM 调用次数
│ └─ llm_processing_seconds: float │ ← 处理耗时
└──────────────────────────────────┘
```

所有 LLM 调用都返回 `ProcessOutcome`，上层不需要 try/catch，只需检查 `degraded` 标志。

---

## 八、测试分层

```
Layer 4: 端到端（真实麦克风 + 真实 LLM）
  └─ scripts/ 中的手动测试脚本
  └─ 真实验收会话

Layer 3: 真实服务测试
  └─ 固定输入 → 真实 ASR/LLM → 验证输出格式

Layer 2: 集成测试（Fake 连线）
  └─ FakeUnderstandingProcessor + 真实 Router + 真实 Planner
  └─ 验证模块间数据合同兼容

Layer 1: 单元测试（Fake）
  └─ 纯逻辑测试（Planner、Parser、PolicyEvaluator）
  └─ 状态机转换测试
  └─ 422 个测试，全部通过
```

**测试原则**：
- Arrange–Act–Assert，每个测试只验证一个行为
- 测试公共接口，不依赖私有实现
- 同时覆盖正常、边界和失败路径
- 修复后必须运行全量测试防回归

---

## 九、扩展点（为未来预留）

当前架构已为以下方向预留了清晰的扩展点：

1. **新意图类型**：扩展 `InteractionCommandType` + `IntentPolicy` + `INTENT_POLICIES` 映射
2. **新分派目标**：扩展 `UnifiedDispatchDestination` + `UnifiedDispatchPlanner.plan()` 分支
3. **TTS 输出**：`PresentationMessage` + `VoiceDeliveryPolicy` 已定义合同，只需接入 TTS 引擎
4. **新 ASR 后端**：实现 `ASRBackend` Protocol，注册到 `factory.py`
5. **新 LLM 提供商**：实现 `LLMClient` Protocol，注册到 `factory.py`
6. **新会话能力**：扩展 `UnifiedInputKind` + `UnifiedUnderstandingResult` 分支

### 已规划的下一批扩展（详见 `PROJECT_TASK_CHECKLIST.md` 第 I 节）

**口述查询识别**：
- `UnifiedInputKind` 增加第 4 分支 `QUERY`
- `UnifiedDispatchDestination` 增加 `KNOWLEDGE_BASE` 目标
- 一次 LLM 调用同时识别实验/控制/不确定/查询四类输入
- 查询子类型：设备占用、实验信息、协议参考、通用知识

**安全警示**：
- `SafetyCheck` Protocol 插入实验采用管线
- 7 种危险类型：高温、危险化学品、高压、生物危害、锐器、电气、其他
- 3 级处置：ALLOW / WARN_BUT_PROCEED / BLOCK_UNTIL_ACKNOWLEDGED
- 复用现有 `MessageKind.SAFETY_ALERT` 消息类型

**用户画像 + 知识库（RAG）**：
- `KnowledgeBase` Protocol 定义最小检索接口
- `UserProfile` 存储用户偏好和默认值
- `SessionContext` 扩展携带画像和知识提示
- `PendingClarification.knowledge_source` 区分知识库触发 vs LLM 推测追问
- `ExperimentEntities.matched_term` 存储知识库匹配的标准术语

---

## 十、文件清单

```
src/
├── main.py                    # 组合根 + 会话循环 (1193行)
├── config.py                  # 集中配置 + 环境变量
├── asr/                       # ASR 后端 (Protocol + SenseVoice 适配器)
├── audio/                     # 音频采集 (VAD + 预录制 + 唤醒音)
├── wakeword/                  # 唤醒词检测 ("小科小科")
├── llm/                       # LLM 客户端 + 两代处理器
├── core/                      # 领域逻辑 (26个文件，纯数据合同+规划器)
├── storage/                   # JSONL 持久化
└── evaluation/                # 离线评估工具
```
