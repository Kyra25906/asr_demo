# asr_demo 当前工作区交接说明

最后整理：2026-08-15

> 本文件是下一会话的短入口，不保存完整历史。任务状态以
> `PROJECT_TASK_CHECKLIST.md` 为准，架构原因见 `PROJECT_ARCHITECTURE.md`，
> 文档关系见 `docs/README.md`。

## 1. 当前结论

- 正式解释器：Python 3.11.9，项目 `.venv` 可用。
- 核心依赖和 `src.main` 导入成功；冷启动约 113 秒。
- 全量自动测试：`Ran 483 tests — OK`（含 RESTORE-NONBLOCK-01 非阻塞 15 项）。
- `RESTORE-NONBLOCK-01`（P0）恢复非阻塞录音 + 拆两句谎话：**REAL_OK**（会话 20260815_094954 连说 10 段不卡、计数正确；新建 `OrderedTaskQueue` + `UnifiedSegmentProcessor`，main 主循环改为"录音→提交后台→显示"；两句谎话已拆）。体验=用户接受当前"结果延后显示"节奏，前瞻要求 **TTS 不乱序朗读**（登记 TIMING-02）。
- 三个硬 GAPS + TIMING-01：**END-01/DEFER-01/TIMING-01 REAL_OK、ADJACENCY-01 AUTO_OK**（会话 20260815_111049/112341）。真实验收抓出并修复"`register_clarification` 不设 current 导致暂缓弃权"根因（新问题创建即当前问题）。全量 **488 项**。**defer_targeted（按编号暂缓"问题二先跳过"）仍 TODO**。
- `MAIN-SESSION-CONTEXT-01`/`MAIN-RUNTIME-HARDEN-01`/`INTENT-02-CLEANUP-FLAGS-01`/`INTENT-02-CLEANUP-SUBMIT-01`/`INTENT-02-CLEANUP-COMMAND-01`：全部 REAL_OK。
- A+B（任务 34/35/36）与显示一致性：**全部 REAL_OK**（会话 `20260814_113958` 验证兜底显示自洽）。
- `INTENT-02-CLEANUP-NAMING-01` 去影子命名：**AUTO_OK**（shadow 全部改为正式执行链命名：`UnifiedObserver`/`UnifiedObservation`/`display_observation`/`unified-` 前缀/`[统一链]` 显示；468 项通过），待一次轻量真实会话不退化复验。
- `INTENT-02-ASR-ROBUSTNESS-01`：REAL_OK；7 缺口登记 `ASR-ROBUSTNESS-RULE-GAPS-01`；补充观察登记 `ASR-ROBUSTNESS-RULE-GAPS-02`（项 E 已结案，其余**用户指示先不改代码、等确认**）。
- **`UX-BASELINE-01` 体验基线走查（用户 2026-08-14 提出"终端看不出体验"后建立）：完成，体验状态 UX_ISSUES**。产出：`docs/UX_WALKTHROUGH_CHECKLIST.md`（九维走查表 + 标准脚本 + 判定规则 + **7.5 UX 价值追踪表**（UX 问题↔任务映射，回答"当前工作对体验有没有用"），体验状态已入任务清单）；会话 `20260814_174441` 走查，11 项问题 UX-01~11，证据 `results/walkthrough_baseline_session_20260814_174441.txt`，逐行标注版 `results/walkthrough_baseline_annotated_20260814_174441.md`。**用户 2026-08-14 决定暂不与 PRESENT 强制绑定**；UX-09 提示音登记 `UX-FIX-TONE-01`（P1，**等 GAPS 修复完成后做**）；UX-10 嘈杂识别三个真实样例已入鲁棒性语料（`narration_plan.json` 段 29/30/31，28→31 段，全量 468 项通过），修复走既有 ASR 线；**UX-11 用户版/管理员版输出分层与 PRESENT-INTEGRATE-01 同源，作为其用户可见验收标准，登记 `UX-MODE-01`（随 PRESENT 排期 8/23 落地）**。注意：GAPS 阶段即解决 UX-03（ANSWER-HINT 编号提示）与 UX-05（END 固定结束语提示）两个体验项，不必等 PRESENT。
- 最近真实会话：`20260814_174441`（体验基线走查）。
- **评委审计发现（2026-08-14，三笔此前漏记的债）**：①**非阻塞录音丢失**——删后台线程后 main 主循环同步串行（observe 调 LLM 期间麦关闭，热2.6s/冷10.98s），但 main.py 319-320 仍打印"无需等待 LLM 处理完成"（**系统在说谎**）；旧路靠 SessionProcessingQueue 后台线程+背压真机验收过"连续5段不卡"，此能力已丢且 5.3 表曾误写成"无此需求"。②**降级人话提示丢失**——LLM 失败时用户看不到"原始记录已保存"，只有开发日志。③**文案与行为一致性**未核查。已登记 `RESTORE-NONBLOCK-01`(P0)/`RESTORE-DEGRADED-HINT-01`(P1)/`SYNC-UI-CLAIMS-01`(P1)；硬/软判据补充"文案说谎"归类规则（误导操作节奏=硬问题）。
- `INTENT-02-ASR-ROBUSTNESS-01` ASR 误识别鲁棒性评测：**REAL_OK（提前执行，用户直接要求，不改变 NAMING-01 的 P0 顺序）**。交付：`evaluation/narration_robustness/narration_plan.json`（28 段噪声口述语料，每段 spoken/observed 双文本+期望标注）、`src/evaluation/narration_robustness_plan.py`（严格 schema）、`tests/test_narration_robustness_plan.py`（21 项）、`scripts/evaluate_narration_robustness.py`（--mode deterministic/real）。确定性：零误触发 13/依赖 LLM 7/精确命中 5/已知限制 3。真实 DeepSeek 旁路（只读）：**21/28 一致、7 缺口**。
- **重要：7 个缺口用户明确指示先不改代码、只记录**（已登记任务清单第 37 项 `ASR-ROBUSTNESS-RULE-GAPS-01`，每条含段号/输入/实际/期望/修复方向；详见该行与 LEARNING_REVIEW 最新条目）。
- **ASR 后处理接入计划（2026-08-14 决策）**：`ASR-CMD-02-POSTPROCESS-01` 已 REAL_OK（术语后处理 0/4→4/4、零回退），但样本内选词有过拟合风险故未接 main。**接入时机 = 组长确定演示实验领域（生物/物理/医药）后，重启该领域术语采集 + 独立语音复验 + 接入**（工厂给 `SenseVoiceBackend` 注入术语后处理函数，下游无感，不影响换模型等后续路线）。**提醒：组长确定后立刻启动，别压到 8 月底**——后处理是 P2 不阻塞评审，但赶工风险要规避。
- 孤儿模块（`clarification_command_handler.py`、`targeted_clarification.py`）main 已不调用，删除与否留待 VERIFY 前集中处理。
- 工作区存在用户累计未提交修改；不得覆盖、回退或混入无关变更。

## 2. 当前唯一下一项

**明天开工清单（2026-08-14 夜定）**：按"硬问题清零即进 PRESENT"的闸门，先做硬问题：

1. ~~`RESTORE-NONBLOCK-01`~~ ✅ **已完成 REAL_OK（2026-08-15，会话 20260815_094954）**；开工从第 2 项起
2. ~~`GAPS-FIX-END-01`~~ ✅ **REAL_OK**（会话 111049：追问"是否结束？"→"是"→结束）
3. ~~`GAPS-FIX-DEFER-01`~~ ✅ **REAL_OK**（会话 112341：暂缓生效；defer_targeted 按编号暂缓已补）
4. ~~`ANSWER-FALLBACK-ADJACENCY-01`~~ ✅ **AUTO_OK**（紧邻约束 + 单测）
5. ~~`RESTORE-DEGRADED-HINT-01`~~ ✅ **REAL_OK**（降级打印人话"原始记录已保存，结构化处理暂时不可用"）
6. ~~`GAPS-REVERIFY-01`~~ ✅ **REAL_OK**（真实旁路 21/31；真实会话 E/③/D 闭环）

> **硬问题已清零，下一步进 PRESENT-INTEGRATE-01**。遗留：②同音错词确认（走 ASR 层）、"是"单字易被 ASR 听成"Sure."（已改提示语引导说"是的"，根治走 ASR 层）。

软问题（显示/话术/误识别，与 PRESENT 并行、不阻塞）：`SYNC-UI-CLAIMS-01` 改文案、`GAPS-FIX-ANSWER-HINT-01` 编号提示、UX 系列、`ASR-CMD-02-POSTPROCESS-01`（等组长定演示领域后重启采集接入）。

> 原待办：①`INTENT-02-CLEANUP-NAMING-01` 去影子命名（纯机械改名）；②`ASR-ROBUSTNESS-RULE-GAPS-01/02` 各项缺口定案——已并入上面第 3/6 项。

> **GAPS 收尾验收方式（用户 2026-08-14 拍板）**：GAPS 修复完成后做**轻量检查**——聚焦行为正确性（结束语不崩/暂缓生效/回答编号提示出现且内容对），用现有工具（`verify_session_context`、JSONL 计数、真实会话）+ 九维表轻量对照（只看 GAPS 触及维度：维3/维6 的行为部分）；不追求输出美化（留给 PRESENT）。**UX-FIX-TONE-01 提示音已顺延到 PRESENT-INTEGRATE-01 之后做**（触发点挂消息链路，输出层只动一次避免返工）。
>
> **PRESENT 与 GAPS 返工风险评估（用户 2026-08-14 反向提问后记录）**：GAPS 修核心层（判断/状态机），PRESENT 修输出层（展示）——职责边界按 `OUTPUT_PRESENTATION_POLICY.md` 第 9 节画死（PRESENT 不识别命令、不改待确认状态），数据流单向，故 PRESENT 不会推翻 GAPS 行为逻辑。唯一风险：PRESENT 重构 main.py 时误伤 GAPS 判断顺序——防护 = PRESENT 后全量测试 + 真实会话回归 + 对照基线会话 `20260814_174441` 行为证据。ANSWER-HINT 提示在 PRESENT 时从散落 print **迁移**到消息链路（迁移非返工，行为判据在轻量检查时记录）。
>
> **推进闸门（用户 2026-08-14 最终决策）**：硬问题（崩溃/数据丢错/核心交互失败，判定标准见任务清单第 1 节"硬问题 vs 软问题"）修完即进 PRESENT，**不设固定日期**（进展快于计划则提前）；软问题（显示/话术/误识别但语义兜底/边缘表达）与 PRESENT 并行、出现即修。**历史教训**：过去把软问题（显示矛盾/双句号/降级无人话/误识别）也标成必修，导致 PRESENT 无限推迟——今后真实验收暴露问题必须先过硬/软判据再定优先级，不得"发现即必修"。

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
