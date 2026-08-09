# 2026-08-09 开发接手说明

## 1. 明日唯一目标

完成 `ASR-CMD-01` 的第一小步：建立控制意图文本语料、真实音频清单和当前 SenseVoice 基线报告。

本轮只测量当前系统，不调整 ASR 参数、不增加模糊命令白名单、不接入 IntentRouter、不重构消息输出。

## 2. 当前可靠基线

- 真实项目：`C:\Users\dahli\Desktop\asr_demo`
- 正式解释器：`.venv` 中的 Python 3.11.9
- 全量自动测试：`130 tests OK`
- 最近真实会话：`20260808_185630`
- `CLARIFY-TARGET-01`：`REAL_OK`，编号答复成功只解决问题2并保留问题1
- 已知核心问题：“看待确认问题”等ASR错误会绕过精确命令解析，进入实验LLM并产生伪NOTE/伪追问

## 3. 开始前命令

```powershell
cd C:\Users\dahli\Desktop\asr_demo

.\.venv\Scripts\python.exe --version

.\.venv\Scripts\python.exe -B -m unittest discover `
    -s tests `
    -v

git status --short
```

预期 Python 为 `3.11.9`，全量测试为 `130 tests OK`。工作区存在今天尚未提交的环境恢复、命令兼容、编号回答、测试和文档修改，不得覆盖或回退。

## 4. 建议新增结构

```text
evaluation/
  asr_commands/
    intents.json
    manifest.jsonl
    confusion_terms.json
    README.md
scripts/
  evaluate_asr_commands.py
tests/
  test_asr_command_evaluation.py
```

新增目录和文件后必须在任务清单及当轮交付中明确报告。

## 5. 四种数据的职责

### intents.json

定义自然表达、预期意图和风险等级，例如 `review_pending`、`defer_current`、`end_session`、`targeted_answer`。不要只写固定口令，也要写“还有什么没回答”“这个先放着”等自然表达。

### manifest.jsonl

每行对应一个真实WAV，至少包含：`sample_id`、`audio_path`、`reference_text`、`observed_asr_text`、`expected_intent`、`session_id`、`critical_terms`。第一版优先引用现有 `audio/recordings`，不要复制或修改原音频。

### confusion_terms.json

记录真实观察到的混淆，例如离心机/离婚机/离星期、水浴/水域、摄氏度/设施度、查看/看待。它是评测和候选生成数据，不是自动覆盖原文的替换表。

### evaluate_asr_commands.py

第一版读取清单并输出静态基线，不重新调用真实模型也可以。至少统计：样本数、ASR精确文本命中率、当前确定性解析器的意图命中率、控制命令漏触发数、普通内容误触发数。输出应可被单元测试验证。

## 6. 第一批真实证据

优先从以下会话对应WAV和JSONL选择样本：

- `20260808_141435`：歌先跳过、短线跳过、带情绪符号的暂缓/回看
- `20260808_144408`：我先跳过、想看待确认问题、可先跳过
- `20260808_183942`：麻烦待确认问题、待确认问题、编号回答
- `20260808_185630`：看待确认问题、问题二明确回答、结束实验记录

必须由用户实际说法作为 `reference_text`。如果日志只能证明ASR结果、不能确定用户原话，就标记 `reference_status=needs_user_label`，不得自行猜测。

## 7. 验收顺序

1. 先为语料数据结构和统计函数写单元测试。
2. 再填入少量可确认的真实样本。
3. 运行评测脚本生成当前基线。
4. 核对正常路径：正确命令能命中。
5. 核对边界：文本错误但意图仍可能正确。
6. 核对失败路径：缺失音频或非法意图应明确报错，不静默跳过。
7. 最后运行全量测试，并更新 `PROJECT_TASK_CHECKLIST.md` 和学习日志。

## 8. 本轮故意不做

- 不训练或微调SenseVoice。
- 不先假设热词一定有效。
- 不把所有观察到的错词加入命令白名单。
- 不让LLM直接执行结束、删除等高风险操作。
- 不接TTS。
- 不一次迁移main中的所有print。

## 9. 后续顺序

```text
ASR-CMD-01 语料与基线
→ ASR-CMD-02 同数据对比中文参数/热词/二次识别
→ INTENT-01/02 自然表达与风险分层IntentRouter
→ PRESENT-INTEGRATE-01 轻量消息链路接入
→ 否定修正、会话总结、SessionRecord和Markdown/JSON导出
→ TTS
```

消息层的既定边界是：业务消息描述内容和抽象输出要求；Presenter决定此刻是否送达；前端/TTS适配器决定颜色、布局、音色、语速和具体情感参数。当前只保留这个设计，不在ASR评测轮实现。
