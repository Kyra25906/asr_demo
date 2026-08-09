# 控制命令 ASR 固定评测集

这里保存用于比较 ASR/意图方案的固定证据，不参与主程序运行。

## 文件职责

- `intents.json`：自然表达、预期意图和风险等级。
- `manifest.jsonl`：真实音频、人工参考文本、既有 ASR 输出和预期意图。
- `confusion_terms.json`：真实观察到的混淆词，不是自动替换表。
- `baseline.json`：运行评测脚本后生成的当前静态基线。
- `language_comparison.json`：同一批 WAV 在 `auto` 与 `zh` 下的候选结果和指标，不覆盖清单。
- `manual_audio_reviews.jsonl`：用户回听后的人工复核证据。采集条件尚未标准化的记录先不混入固定基线。

`reference_status=user_confirmed` 才计入文本准确率；无法从日志确认用户原话的样本标为
`needs_user_label`。如果提示文字与 WAV 真正录入的内容不同，`prompt_text` 保存原本准备朗读的
文字，`reference_text` 保存音频中实际可听内容，`capture_note` 说明截音等录制问题。评估 ASR
时必须以 `reference_text` 为准，不能要求模型识别音频中不存在的字。

人工复核记录使用 `capture_quality` 区分完整录音和句首截断。`baseline_eligible=false` 表示该音频
可以用于定位问题，但在独立采集流程、标签字段和样本纳入规则统一之前，不参与正式基线分母。

## 运行

```powershell
cd C:\Users\dahli\Desktop\asr_demo
.\.venv\Scripts\python.exe -B -m scripts.evaluate_asr_commands
```

这一步不会重新加载 SenseVoice。它使用历史真实 ASR 输出测量当前解析器，因此适合快速、
可重复的回归。下一轮对比不同 ASR 参数时，必须使用同一批 WAV，并把新输出另存为新的候选结果，
不得覆盖 `observed_asr_text`。

## 固定中文参数对照

```powershell
cd C:\Users\dahli\Desktop\asr_demo
.\.venv\Scripts\python.exe -B -m scripts.compare_asr_languages
```

当前安装的 SenseVoice 实现明确支持 `auto`、`zh`、`en`、`yue`、`ja`、`ko` 和
`nospeech`。中文对照使用模型实际支持的 `zh`，不是自行猜测的 `zh-cn`。脚本只改变
`language`，保持 `use_itn=True`、`batch_size_s=60` 和 WAV 顺序不变。
