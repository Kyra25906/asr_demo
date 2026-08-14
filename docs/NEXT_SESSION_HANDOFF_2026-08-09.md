# asr_demo 当前工作区交接说明

最后整理：2026-08-14

> 本文件是下一会话的短入口，不保存完整历史。任务状态以
> `PROJECT_TASK_CHECKLIST.md` 为准，架构原因见 `PROJECT_ARCHITECTURE.md`，
> 文档关系见 `docs/README.md`。

## 1. 当前结论

- 正式解释器：Python 3.11.9，项目 `.venv` 可用。
- 核心依赖和 `src.main` 导入成功；冷启动约 113 秒。
- 全量自动测试：`Ran 468 tests in 1.196s — OK`。
- `MAIN-SESSION-CONTEXT-01`/`MAIN-RUNTIME-HARDEN-01`/`INTENT-02-CLEANUP-FLAGS-01`/`INTENT-02-CLEANUP-SUBMIT-01`/`INTENT-02-CLEANUP-COMMAND-01`：全部 REAL_OK。
- A+B（任务 34/35/36）：**全部 REAL_OK**；显示一致性修复 **REAL_OK**（会话 `20260814_113958` 验证：兜底接住后显示自洽"待确认动作=answer"；"仍需补充：空"→"仍需确认"）。
- `INTENT-02-ASR-ROBUSTNESS-01`：REAL_OK；7 缺口登记 `ASR-ROBUSTNESS-RULE-GAPS-01`；补充观察登记 `ASR-ROBUSTNESS-RULE-GAPS-02`（项 E 显示 bug 已结案，其余**用户指示先不改代码、等确认**）。
- 最近真实会话：`20260814_113958`。
- 最近真实会话：`20260814_113237`。
- `INTENT-02-ASR-ROBUSTNESS-01` ASR 误识别鲁棒性评测：**REAL_OK（提前执行，用户直接要求，不改变 NAMING-01 的 P0 顺序）**。交付：`evaluation/narration_robustness/narration_plan.json`（28 段噪声口述语料，每段 spoken/observed 双文本+期望标注）、`src/evaluation/narration_robustness_plan.py`（严格 schema）、`tests/test_narration_robustness_plan.py`（21 项）、`scripts/evaluate_narration_robustness.py`（--mode deterministic/real）。确定性：零误触发 13/依赖 LLM 7/精确命中 5/已知限制 3。真实 DeepSeek 旁路（只读）：**21/28 一致、7 缺口**。
- **重要：7 个缺口用户明确指示先不改代码、只记录**（已登记任务清单第 37 项 `ASR-ROBUSTNESS-RULE-GAPS-01`，每条含段号/输入/实际/期望/修复方向；详见该行与 LEARNING_REVIEW 最新条目）。
- 孤儿模块（`clarification_command_handler.py`、`targeted_clarification.py`）main 已不调用，删除与否留待 VERIFY 前集中处理。
- 工作区存在用户累计未提交修改；不得覆盖、回退或混入无关变更。

## 2. 当前唯一下一项

待用户定夺：①`INTENT-02-CLEANUP-NAMING-01` 去影子命名（纯机械改名，不改变行为）；②`ASR-ROBUSTNESS-RULE-GAPS-01/02` 各项缺口定案（用户指示先不改代码、等确认——含 7 缺口 + 复验补充观察 5 项：DEFER 漏识别×2、否定修正未接住、自然结束语 ValueError、"仍需补充：空"显示 bug、半路弃权）。

> 说明（2026-08-14）：`INTENT-02-ASR-ROBUSTNESS-01` 因用户直接要求**提前执行完毕**（只建评测体系、不改代码），其发现的 7 个缺口已登记 `ASR-ROBUSTNESS-RULE-GAPS-01` 待定案。这两项都不改变 NAMING-01 的 P0 顺序。

真实会话核验工具：`.\.venv\Scripts\python.exe -B -m scripts.verify_session_context <session_id>`（输出 ASR 段数、事件数、预期上下文计数）。

## 3. 后续固定顺序

```text
MAIN-SESSION-CONTEXT-01（REAL_OK）
→ MAIN-RUNTIME-HARDEN-01
→ INTENT-02-CLEANUP-FLAGS/SUBMIT/COMMAND/NAMING/VERIFY
→ Query / Safety / Knowledge 类型合同
→ QUERY 第四分支与只读分派
→ PRESENT 稳定后接真实安全规则、设备查询和 RAG
```

为什么这样排：当前系统首先要保证配置合法、原始证据先于状态变化、会话上下文不断链；
随后删除双轨代码。否则未来查询、安全和 RAG 会复制当前过渡层的错误边界。

## 4. main 已知风险

| 优先级 | 风险 | 期望修复 |
|---|---|---|
| `P0` | execute flag 可在 observer 未创建时开启 | **已修（2026-08-14）**：两个 shadow flag 已随 CLEANUP-FLAGS-01 删除，配置校验函数一并移除 |
| `P0` | `ClarificationExecutor` 可能先改协调器，main 后写 ASR | 统一采用 prepare → persist → commit |
| `P0` | 新链 observe 未传 `recent_context`、事件落盘后未更新 `SessionContext` | **已修（2026-08-14，REAL_OK）**：observe 传 `as_prompt_context()` 快照；事件落盘成功后 `add_analysis`；会话 20260814_092200 复验通过 |
| `P1` | `experiment_segment_count` 在确认实验分析前加一 | **已修（2026-08-14，REAL_OK）**：`is_experiment_evidence` 判定，只统计实验/降级证据段；会话 20260814_093515 复验通过 |
| `P1` | 持续唤醒错误立即重试 | **已修（2026-08-14）**：`src/core/retry.py` 指数退避 1→2→4→8→10s 封顶，成功重置，Ctrl+C 不受影响 |
| `P2` | Answer 执行器有重复 `if not supplied_fields` | **已修（2026-08-14）**：删除不可达重复分支 |
| `P1` | 统一链识别到 review 时无查看结果输出（只显示"已保存"） | `INTENT-02-REVIEW-OUTPUT-01`：review 动作显示待确认列表或"没有待确认问题"；随 `CLEANUP-COMMAND-01` 删旧门卫时把显示职责搬进新链 |

## 5. 恢复命令

```powershell
cd C:\Users\dahli\Desktop\asr_demo

.\.venv\Scripts\python.exe --version

.\.venv\Scripts\python.exe -B -c `
  "import dotenv, sherpa_onnx, sounddevice, soundfile, funasr, modelscope, torch; import src.main; print('IMPORTS_AND_MAIN_OK')"

.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v

git status --short
git diff --check
```

受限沙箱中的 `Access denied` 不等于虚拟环境损坏。先在获准执行边界中验证解释器，
不要直接删除 `.venv`，也不要用 Python 3.14 加载 Python 3.11 的二进制依赖。

## 6. 真实验收门槛

修改涉及 `main.py`、麦克风、真实 ASR/LLM、存储或状态提交时：

1. 先通过单元和集成测试；
2. 说明真实输入、数据外发范围和成功/失败标准；
3. 获得本轮明确授权后再启动真实设备或外部 LLM；
4. 记录 session_id、终端证据和 JSONL 数量；
5. 更新任务清单、学习日志和本交接文件。

下一次真实连续会话至少覆盖：实验、CREATE、ANSWER、REVIEW、DEFER、结束命令，
并验证 ASR/事件证据顺序和最终 SessionContext 数量。

`MAIN-SESSION-CONTEXT-01` 的专门复验标准：**已完成（2026-08-14，会话 20260814_092200）**
- 至少 2 段普通实验口述（第二段依赖第一段内容，如"先加缓冲液"→"加热到六十度"）：✅ 2 段；
- 结束时终端打印"最终上下文包含 N 条事件"，N 必须等于各段已落盘事件总数（修复前为 0）：✅ N=2=事件数；
- 结束命令不进入分段；ASR/事件 JSONL 数量与显示一致：✅ 3 录音文件仅 2 条 ASR 记录；
- 附加证据：第 2 段 prompt_tokens 959→971（cached 896 不变），前文上下文条目确实进入提示词。

## 7. 数据与 Git 边界

- `.env`：本机密钥和配置，不提交。
- `audio/recordings/`、`results/`：真实数据，不提交。
- `.venv*`、模型缓存：不提交。
- 当前目标分支：`codex/asr-demo-unified-understanding`。
- 未经用户明确要求，不提交、不推送、不创建 PR。
- 当前工作区已有累计修改，只处理本轮范围，不清理用户其他改动。
