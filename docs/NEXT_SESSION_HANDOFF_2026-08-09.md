# asr_demo 当前工作区交接说明

最后整理：2026-08-11

## 1. 当前唯一下一项

`INTENT-02-UNIFIED-PROMPT-MISSING-FIELDS-01` **已完成**（REAL_OK）。

下一项待用户决定，候选：
- `INTENT-02-REPLY-GATE-01`（P1）：把已采用 `ClarificationAction` 接入 `ReplyCoordinator`
- 提交 PR 到 total 远程仓库
- AUDIO-PREROLL-REAL-01 句首预缓冲真实验收

## 2. 可复现基线

- 真实项目：`C:\Users\dahli\Desktop\asr_demo`
- 正式解释器：`.venv` 中的 Python 3.11.9
- 全量自动测试：`392 tests OK`（2026-08-11重新运行）
- 当前 Git 分支：`main`
- 当前远程：`origin = https://github.com/Kyra25906/asr_demo.git`
- 工作区存在累计未提交修改，不得覆盖、回退或把无关文件混入清理。

恢复命令：

```powershell
cd C:\Users\dahli\Desktop\asr_demo
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -B -m unittest discover
git status --short
git diff --check
```

## 3. 已完成的主要能力

### ASR与证据

- ASR 后端改为 Protocol＋Factory＋SenseVoice 适配器，业务代码不再绑定具体模型类。
- `ASRResult` schema v2 区分模型原始文本、忠实转写和后续纠错候选。
- 历史 schema v1 可只读兼容，真实结果文件不迁移、不覆盖。
- 24条控制语料真实采集与基线已经完成；专业词后处理仅为评测候选，尚未接入主流程。

### 统一理解与安全分派

- 精确控制命令走本地快速路径，未命中文本最多进入一次统一理解调用。
- 统一理解严格使用 experiment/control/uncertain 三分支合同。
- 安全分派固定目标与最小权限，不直接产生副作用。
- 执行请求绑定 request/session/segment、最终 ASR 证据、目标和权限，并有幂等 Fake 验收。

### 采用合同

- 实验候选经过来源、原文、目标、权限和降级形状检查后，才生成不可变规范快照。
- 待确认动作被建模为 create/review/defer/answer/confirm/reject_suggestion/no_action。
- PREPARE_CREATE/PREPARE_UPDATE 只表示准备动作，没有 commit 方法。
- LLM 中风险状态候选不能直接修改问题；降级 NOTE 不能制造正式问题。

### main影子模式

- `UNIFIED_SHADOW_ENABLED` 默认 false；本机 `.env` 当前为真实测试临时开启状态，提交时 `.env` 不进入 Git。
- 影子链读取同一最终 ASR 证据和只读待确认快照。
- 影子摘要只显示目标、权限、采用类型、缺失字段、追问标志和动作类型。
- 影子不写业务文件、不改 SessionContext/ReplyCoordinator、不发 TTS；异常只产生失败摘要，旧流程继续。

## 4. 最近真实验收

### main影子接入

- 会话：`20260810_120209`
- 前3段真实进入 experiment_pipeline/structured_experiment，影子明确“未执行”。
- 结束候选进入旁路未开放目标后安全失败，旧流程继续，证明失败隔离。

### 结束命令单一来源

- 真实问题：“接受实验记录。😔”被旧 main 当作 NOTE。
- 已删除 main 独立结束字典/正则，统一委托 `InteractionCommandParser`。
- 修改后短真实会话中，ASR业务记录保持186条、事件保持133条，结束口述没有进入分段、LLM或存储。
- 状态：`REAL_OK`。

### 新旧追问差异

- 会话：`20260810_180242`
- 真实 ASR：”将溶液加热。”
- 旧链：`missing_fields=[temperature, duration]`，生成追问。
- 新统一链及保存证据重放：`missing_fields=()`、`follow_up_required=False`、`no_action`。
- 根因不是合同矛盾：统一 Prompt 缺少”何时登记缺失字段”的业务能力规则。

### 统一Prompt缺失字段能力修复

- 修改：`unified_prompts.py` 实验规则新增一行，与旧 `ANALYSIS_SYSTEM_PROMPT` 第4条规则文字一致。
- 真实 DeepSeek 复验”将溶液加热。”：`missing_fields=['temperature','duration']`、`should_ask_follow_up=True`、`follow_up_question=”加热到什么温度？需要加热多长时间？”`、降级=False、1次成功2.32秒。
- 状态：`REAL_OK`。

## 5. 当前工作区构成

累计修改大致分为：

```text
src/asr/              后端抽象与证据schema
src/core/             统一理解、分派、执行、采用、影子合同
src/llm/              统一Processor与Router
src/evaluation/       控制语料基线与术语后处理对照
scripts/              Fake/真实旁路及评测入口
tests/                每个新增边界的专项和集成测试
docs/                 任务清单、交接和学习记录
```

本机数据边界：

- `.env`：忽略，包含本机配置/密钥，不提交。
- `audio/recordings/`：忽略，真实录音不提交。
- `results/`：忽略，真实会话数据不提交。
- `.venv*`、模型下载缓存：忽略，不提交。
- `audio/wav/`：仓库已有固定非敏感测试样本，保持跟踪。
- `evaluation/asr_commands/` 中的计划、人工基线和清单可跟踪；采集尝试与生成报告已忽略。

## 6. 仍未开放的能力

- 新统一链尚未接管旧 SegmentProcessor 或真实存储。
- ClarificationAction 尚未提交到 ReplyCoordinator。
- 结束会话副作用尚未通过统一执行器开放；main仍在正式本地Parser命中后直接结束。
- 热词候选模型尚未验证或切换。
- 专业词后处理尚未接入主链。
- Presentation/TTS 尚未接入。
- 未提交、未推送、未创建 PR。

## 7. 提交前整理门

当前分支是 `main`，且累计改动较多。提交到新总仓前必须：

1. 确认目标远程地址，不把改动误推到当前 `origin`。
2. 新建 `codex/` 前缀工作分支，不在 `main` 提交。
3. 复核 `git status --short`，只暂存源码、测试、脚本和文档。
4. 确认 `.env`、录音、结果、模型、虚拟环境没有进入暂存区。
5. 运行 `392+` 全量测试与 `git diff --check`。
6. 按能力边界拆分提交；不要把全部累计修改压成无法审查的一次提交。
7. 推送前检查远程和分支名；未经用户明确要求不提交、不推送。

建议提交分组：

```text
1. ASR后端抽象＋ASR证据schema v2
2. 控制语料基线＋术语后处理评测
3. 统一理解Prompt/Processor/Router
4. 安全分派＋执行请求合同
5. 实验/待确认采用合同＋集成旁路
6. main影子模式＋结束命令单一来源
7. 任务清单、交接与学习日志
```

## 8. 教学与真实验收约定

每轮按“目的、技术路线、设计原因、实现功能、本轮知识、验收方法、下一步建议”讲解。

修改触及麦克风、真实 ASR、真实 LLM、持久化或主流程时，自动测试通过后必须主动安排真实环境验收；验收前说明输入、数据外发范围、观察指标和成功/失败标准，验收后用终端、文件计数、会话编号等证据更新状态。历史单次外发授权不能自动扩大。
