# asr_demo 开发暂停交接记录

更新时间：2026-08-06

真实项目：`C:\Users\dahli\Desktop\asr_demo`

## 1. 固定协作要求

1. 每轮只推进一个可以独立验证的能力。
2. 不同时接入过多模块，避免难以定位问题。
3. 先定义稳定的数据结构和接口，再连接真实服务。
4. 先完成单元测试，再做模块集成测试，最后做真实环境验收。
5. 外部服务失败不能破坏已经完成的核心工作。
6. 原始数据必须优先保存，模型推断不能覆盖原始事实。
7. 主流程保持精简，复杂业务放入独立模块。
8. 模块之间传递数据对象或明确接口，不直接控制彼此的底层资源。
9. 每轮按“目的、技术路线、设计原因、实现功能、本轮开发知识、验收方法、下一步建议”说明。
10. 文件结构或项目结构发生变化时必须明确反馈。
11. 第 4、5 部分按相同文件顺序讲解，开发知识面向零基础新手并联系当前代码。
12. 真实项目修改需要明确范围；代码可先在可写交付区生成并审查。

## 2. 当前已经完成的能力

- 离线唤醒、VAD 录音、FunASR 识别。
- 一次唤醒后连续记录多段实验口述。
- DeepSeek/OpenAI-compatible `LLMClient`。
- 强制 JSON 输出、严格格式校验和保真降级。
- DeepSeek 关闭 thinking 模式。
- 空响应、超时、429、5xx 有限重试。
- 每段记录 LLM 尝试次数和处理耗时。
- ASR 原文与结构化实验事件分别保存为 JSONL。
- 单线程后台 LLM 队列，保证顺序和优雅退出。
- `SessionContext` 保存最近结构化上下文。
- 结束指令及已观察到的 ASR 变体。
- `PendingClarification` 待确认数据对象。
- `ReplyCoordinator`：登记问题、部分解决、完全解决、每个安全间隙最多一条回复。
- `main.py` 已接入协调器，可以显示带来源的问题和会话遗留项。
- 协调器纯逻辑已支持明确肯定答复关闭最早 ASR 错词确认项。

## 3. 最近修改的真实项目文件

### 新增

- `src/core/pending_clarification.py`
- `src/core/reply_coordinator.py`
- `tests/test_reply_coordinator.py`
- `tests/test_reply_coordinator_integration.py`

### 修改

- `src/main.py`：创建会话级协调器、登记后台结果、每批最多显示一条回复、结束时显示遗留项。
- `src/core/pending_clarification.py`：增加 `confirm()` 状态转换。
- `src/core/reply_coordinator.py`：增加 `ConfirmationResolution`、`try_confirm_oldest()` 和保守肯定文本识别。
- `tests/test_reply_coordinator.py`：增加肯定、否定、误判、最早项和部分解决测试。

## 4. 当前测试基线

最近一次协调器测试：

```text
Ran 13 tests
OK
```

最近一次完整回归：

```text
Ran 65 tests
OK
```

命令：

```powershell
cd C:\Users\dahli\Desktop\asr_demo

.\.venv\Scripts\python.exe -B -m unittest `
    tests.test_reply_coordinator `
    -v

.\.venv\Scripts\python.exe -B -m unittest discover `
    -s tests `
    -v
```

## 5. 当前准确停点

协调器已经具备以下纯逻辑接口：

```python
resolution = reply_coordinator.try_confirm_oldest(
    segment_id=answer_segment_id,
    raw_text=answer_raw_text,
)
```

支持的明确肯定示例：

```text
是
是的
对
对的
正确
没错
确认
是的，是移液枪
没错，是500微升
确认是移液枪
```

明确否定不会关闭：

```text
不是
不对
说错了
```

普通实验句子不会因“对”字误判：

```text
对溶液继续加热。
```

重要：`main.py` 尚未调用 `try_confirm_oldest()`，所以真实语音说“是的”目前仍不会关闭确认项。本轮只完成了纯逻辑和单元测试。

## 6. 已发现但尚未解决的问题

### 问题 A：待确认问题显示较晚

现象：LLM 已经在后台完成，但问题通常要等下一段口述结束后才显示。

根因：主线程阻塞在 `record_until_silence()` 等待人声，暂时不能执行 `processing_queue.collect_ready()`。

这不是 ReplyCoordinator 的算法问题，而是录音等待和后台完成通知之间缺少事件驱动或短周期轮询。

### 问题 B：结束会话后不能继续语音确认

现象：说“结束实验记录”后，程序等待后台任务结束，显示遗留项，然后销毁会话级协调器并回到 IDLE。

根因：当前没有独立的 `CONFIRMING` 或“会话收尾确认”状态。

未来目标状态：

```text
SESSION_ACTIVE
    ↓ 结束实验记录
CONFIRMING
    ↓ 确认完成或明确跳过
IDLE
```

## 7. 恢复工作后的下一轮唯一目标

只做：将明确肯定的 ASR 答复接入 `main.py`。

建议数据流：

```text
ASR 得到新文本
    ↓
检查当前是否有活动 ASR 确认项
    ↓
调用 try_confirm_oldest()
    ├─ 匹配：保存确认原文并显示“第X段确认完成”
    └─ 不匹配：按普通实验段提交后台队列
```

实现前必须先决定确认答复如何持久化。不能直接丢弃“是的”这段 ASR 原文，也不应把它错误保存为普通实验操作。建议先定义独立的确认记录数据结构和存储接口，再接 `main.py`。

本轮不要同时解决“即时显示”和“结束后确认阶段”。

## 8. 后续建议顺序

1. 定义并保存确认答复记录，然后接入 `main.py`。
2. 解决后台结果在等待录音期间不能及时显示的问题。
3. 增加 `CONFIRMING` 会话收尾阶段。
4. 再接系统 TTS 和 `SPEAKING` 状态。
5. TTS 稳定后再考虑 GPT-SoVITS。

## 9. 数据安全与配置

- `.env` 中可能包含真实 API Key，不要复制到文档、测试或对话。
- `raw_text` 必须保留，模型修正只能写入 `normalized_text` 并附确认状态。
- LLM 失败时继续保存 ASR 原文和降级 NOTE。
- 不要清空或覆盖现有 `results/*.jsonl`。

## 10. 恢复时建议先执行

```powershell
cd C:\Users\dahli\Desktop\asr_demo

.\.venv\Scripts\python.exe -B -m unittest discover `
    -s tests `
    -v
```

确认仍为 65 项通过后，再开始下一轮修改。
