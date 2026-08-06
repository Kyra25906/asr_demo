# 高校实验具身语音智能体：项目总览与开发交接

> 更新时间：2026-08-05  
> 参赛项目：中国科学技术大学“107杯”智能体开发大赛  
> 当前主项目目录：`C:\Users\dahli\Desktop\asr_demo`  
> 推荐启动方式：在项目根目录执行 `python -m src.main`

## 1. 项目总任务

### 核心定位

面向高校实验与学习场景的具身语音智能体：让学生能够边操作、边口述，系统自动形成结构化实验记录，并持续跟进学习任务。

一句话版本：

> 一个能听懂实验过程、主动追问关键信息、整理实验记录，并陪伴后续复盘的桌面智能体。

### 核心问题

学生做实验时双手经常被占用，纸笔或电脑记录会打断操作；普通录音只能保存声音，不能主动发现缺失信息，也不能形成便于检索、复盘和生成报告的结构化记录。

本项目要形成以下闭环：

```text
语音唤醒
  → 连续监听实验口述
  → VAD 自动切分语音段
  → FunASR 转写
  → LLM 理解上下文并结构化实验事件
  → 对缺失或矛盾信息主动追问
  → 保存会话记录并生成总结/后续任务
  → TTS / GPT-SoVITS 语音反馈
  → Live2D 展示状态、表情和口型
  → 可选 Agent 执行计时、检索、导出等动作
```

### 产品边界

- 核心不是普通聊天机器人，而是“实验记录与学习跟进”智能体。
- 唤醒一次后应进入持续实验会话，不要求每句话重复唤醒。
- ASR 只负责忠实转写；结构化、纠错建议、追问和任务决策由 LLM 层承担。
- 原始音频和原始识别文本必须保留，数值、单位和实验事实不能被静默改写。
- Agent 是可选增强能力，不应阻塞“口述—记录—追问”的核心闭环。
- 第一版采用半双工：智能体说话时暂停麦克风监听，避免把自己的 TTS 当成用户输入。

## 2. 总体技术架构

### 输入与会话层

- `sherpa-onnx KeywordSpotter`：离线检测唤醒词“小科小科”。
- `sherpa-onnx Silero VAD`：检测开始说话和自然停顿，自动切分录音。
- 状态机：管理 `IDLE`、`SESSION_ACTIVE`、`LISTENING`、`PROCESSING`、`SPEAKING`。

### 识别与理解层

- `FunASR + SenseVoiceSmall`：中文实验口述识别。
- `FSMN-VAD`：作为 FunASR 模型内部的语音分段能力；外层 Silero VAD 负责麦克风实时端点检测。
- 后续 LLM：把多段 ASR 文本合并到会话上下文，输出结构化事件、追问、建议和可选工具调用。

### 输出与展示层

- 当前 Windows `winsound`：临时唤醒反馈，已验证可播放。
- 后续统一 TTS 接口：`synthesize(text, emotion) -> audio`。
- GPT-SoVITS：计划作为独立服务生成个性化语音，避免与主程序 Python 依赖冲突。
- Live2D-LLM-Chat：计划作为展示层，接收状态、回复文本、情绪、动作和口型数据，不直接负责业务推理。

### 数据层

- 每段原始 WAV 保存在 `audio/recordings/`。
- ASR 结果按 JSONL 追加到 `results/asr_segments.jsonl`。
- 每次实验拥有唯一 `session_id`，其中每段拥有递增 `segment_id`。
- 后续增加实验事件、追问、用户补充、总结和任务的独立数据结构。

## 3. 已经完成并验证的功能

### 3.1 Python 与依赖环境

- 已使用 Python 3.11 重建 `.venv`，避开 Python 3.14 与部分语音/AI依赖不兼容的问题。
- Python 3.11 路径：`C:\Users\dahli\AppData\Local\Programs\Python\Python311\python.exe`。
- 已安装并验证：FunASR、ModelScope、PyTorch CPU、torchaudio、sounddevice、soundfile、sherpa-onnx、pypinyin。
- 曾观察到版本：FunASR 1.4.1、transformers 5.14.1、torch 2.13.0+cpu。
- `from funasr import AutoModel` 已可正常导入。FunASR 首次导入可能较慢；此前的 `KeyboardInterrupt` 是等待时人工中止，不是项目代码异常。

进入环境：

```powershell
cd C:\Users\dahli\Desktop\asr_demo
.\.venv\Scripts\Activate.ps1
python -m src.main
```

退出环境：

```powershell
deactivate
```

### 3.2 FunASR 工程化

- `SpeechRecognizer` 在程序启动时创建，SenseVoiceSmall 只加载一次。
- 同一进程可以识别多段实验口述，不会每段重复加载模型。
- 麦克风以 16 kHz、单声道录音并保存 PCM16 WAV。
- 已定义 `ASRResult`，保存清洗文本、原始文本、音频路径、音频时长、识别耗时、模型、语言等信息。
- 已实现 JSONL 追加保存，并用 `session_id`、`segment_id` 标记会话及语音段。
- 实测约 15.31 秒录音识别耗时约 1.44 秒，基本满足原型展示要求。
- 录音、识别、保存流程已经通过。

### 3.3 语音唤醒

- 已下载并接入 `sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20`。
- 官方测试音频已成功识别关键词。
- 已生成自定义唤醒词“小科小科”的 token 文件。
- 解决了 PowerShell UTF-8 BOM 导致首词被识别为 `﻿小科小科`、无法进入词典的问题。
- 当前自定义参数为：`x iǎo k ē x iǎo k ē :3.0 #0.10 @小科小科`。
- 麦克风实时唤醒已经可用；测试中曾出现一次“小哥小哥”近音误触，当前可接受，后续再做数据化调参。
- KWS 检测结束后会关闭麦克风，再将控制权交给录音模块，避免两个输入流冲突。

为什么无 BOM 才能工作：BOM 是文件开头的隐藏 Unicode 标记。关键词工具没有自动剥离它，于是首个词实际变成“BOM + 小科小科”，既不等于配置词，也不是正常汉字序列，因此被跳过。

### 3.4 VAD 自动录音

- 已下载并加载 `models/vad/silero_vad.onnx`，模型只加载一次。
- 已独立验证 VAD 能检测人声。
- 已实现 `VadAudioRecorder.record_until_silence()`：等待人声、开始录制、检测自然停顿、保存 WAV。
- 静音结束阈值由 1 秒调整到 2 秒，避免一句话中正常思考停顿就过早结束。
- 单段最大语音时长当前为 30 秒。
- 当前开始说话等待超时为 8 秒。
- 原来的手动 Enter 录音器保留，可作为比赛现场兜底方案。

### 3.5 状态机和持续会话骨架

- 已有状态：`IDLE`、`SESSION_ACTIVE`、`LISTENING`、`PROCESSING`、`SPEAKING`。
- 外层循环负责等待唤醒；唤醒后创建新的实验 `session_id`。
- 内层实验会话可以保存多段口述，并共享同一个 `session_id`。
- 单段失败不会直接销毁整个实验会话。
- 会话结束后重新回到 `IDLE`，等待下一次唤醒。

### 3.6 唤醒反馈音

- 用 `sounddevice` 单独播放提示音正常，但从 KWS 切换后没有声音。
- 改用 Windows `winsound.MessageBeep()` 后已验证正常。
- 这说明扬声器和唤醒模块能够共存，问题只在 `sounddevice` 播放流切换，不影响未来 GPT-SoVITS。
- 当前提示音只是确认“系统已进入会话”；未来可替换为 TTS 回复“我在，请说”。

## 4. 当前代码的真实运行状态

当前主流程为：

```text
启动程序并加载 ASR、VAD、KWS
  → 等待“小科小科”
  → 播放 Windows 提示音
  → 创建实验会话
  → VAD 等待说话并自动结束一段录音
  → FunASR 识别并保存
  → 仍需按 Enter 开始下一段，或输入 q 结束会话
  → 回到等待唤醒
```

因此目前已经实现“唤醒一次进入会话”和“单段自动端点检测”，但还没有完成“会话内部完全免按键的连续语音交互”。

## 5. 已知问题与暂缓事项

### ASR 专业术语

已出现：

- “移液枪”被识别为“营业枪”或“一液枪”。
- “离心管”被识别为“离锌管”。

当前决定：暂不预先建立大而不确定的术语库。继续保留真实音频和错误文本，后续根据实际实验场景收集高频误识别，再加入热词、术语纠错或上下文校正。任何校正都应保留原文并对关键数值保持谨慎。

### 唤醒词精度

- “小科小科”曾约 5 次命中 2 次，经调参后已可唤醒。
- 曾有一次“小哥小哥”误触。
- 后续应建立固定测试集，分别统计真阳性、漏唤醒和误唤醒，而不是只凭少数试说继续调参。
- 可比较更有区分度的唤醒词，例如“你好小科”。

### 音频输入输出切换

- `sounddevice` 在 KWS 后播放自制提示音存在问题，当前使用 `winsound` 绕过。
- 后续 TTS 应单独封装 `AudioPlayer`，按“关闭监听 → 播放完成 → 延迟 200–300 ms → 恢复监听”的顺序工作。

### 依赖风险

- GPT-SoVITS、FunASR、Live2D 相关依赖可能冲突，不建议全部装进主程序的同一个虚拟环境。
- GPT-SoVITS 后期采用独立进程/HTTP 服务；主程序只依赖稳定接口。
- 如以后 FunASR 与 Transformers 5 出现兼容问题，可评估固定 `transformers>=4.32,<5`，目前不必为了“可能的问题”改动已可运行环境。

## 6. 下一轮的明确任务

### 目的

让用户唤醒一次后，在整个实验 session 中只用语音连续记录，不再通过 Enter 控制段落。

### 技术路线

1. 将 `VadAudioRecorder.start_timeout_seconds` 从固定 8 秒改为可选值；实验会话中允许无限等待用户下一次开口。
2. 每段 ASR 和保存完成后，程序自动重新进入 VAD 监听。
3. 先用确定性的结束指令退出会话，例如：
   - “结束实验记录”
   - “结束记录”
   - “结束本次实验”
   - “退出实验记录”
4. 结束指令由 ASR 文本匹配，不作为实验内容写入记录。
5. 保留 Ctrl+C 作为程序级退出，并保留手动录音模式作为现场兜底。

### 为什么先这样设计

- 当前还没有接 LLM，先用明确指令可独立验证“录音—识别—会话控制”闭环。
- 会话控制与实验内容分离，避免结束命令污染实验数据。
- 无限等待符合真实实验：两次操作之间可能间隔数十秒甚至数分钟。
- 等这一层稳定后，LLM 才接入，否则难以判断问题来自音频状态、ASR 还是语言理解。

### 验收标准

- 说一次唤醒词后进入实验会话。
- 不碰键盘，可以连续口述至少 3 段。
- 每段在自然停顿约 2 秒后自动识别。
- 三段具有相同 `session_id` 和连续 `segment_id`。
- 说结束指令后退出会话，结束指令不写入实验记录。
- 退出后重新进入待机，并能再次被唤醒。

## 7. 后续开发规划

### 阶段 A：完成纯语音会话控制

- 自动连续监听。
- 语音结束会话。
- 空白、噪声、超长录音和异常恢复。
- 会话内提示策略：优先视觉反馈，避免每段都播放声音干扰操作。

### 阶段 B：建立 LLM 实验记录核心

先定义稳定的输入输出结构，再选择具体模型或 API。建议事件结构至少包含：

```json
{
  "event_type": "operation | observation | measurement | anomaly | question",
  "raw_text": "用户原始口述",
  "normalized_text": "规范化但可追溯的表达",
  "entities": {
    "object": null,
    "action": null,
    "quantity": null,
    "unit": null,
    "condition": null
  },
  "missing_fields": [],
  "needs_confirmation": false
}
```

LLM 第一版功能：

- 根据多轮上下文合并实验步骤。
- 区分操作、观察、测量、异常。
- 发现缺少体积、浓度、温度、时间等关键信息时追问。
- 对疑似 ASR 错词提出确认，不直接覆盖原文。
- 生成阶段总结和会话结束总结。

### 阶段 C：TTS 与对话闭环

- 先用系统 TTS 或简单 TTS 验证接口和状态切换。
- 引入 `SPEAKING` 状态，播放期间暂停 KWS/VAD。
- 支持简短回复、分句播放、失败降级和用户打断策略。
- 将唤醒提示音替换为“我在，请说”。

### 阶段 D：GPT-SoVITS

- 独立部署 GPT-SoVITS，通过 HTTP 接收文本和情感参数，返回 WAV。
- 主程序增加超时、缓存及失败时回退到系统 TTS。
- 先验证普通音色，再考虑训练/微调展示音色。

### 阶段 E：Live2D

- 参考 `suzuran0y/Live2D-LLM-Chat`，但只把它作为前端表现层。
- 状态映射：待机、倾听、思考、说话、异常。
- 情绪映射来自 LLM 输出或 SenseVoice 情感标签。
- 用 TTS 音量包络或音素时间戳驱动口型。
- Live2D 崩溃不能影响录音、识别和实验数据保存。

### 阶段 F：Agent 与学习跟进

- 计时器、实验提醒、资料查询、报告导出等功能使用白名单工具。
- 外部写入、高风险操作或不可逆动作必须要求确认。
- 会话结束后生成复盘问题、待办和下一次学习提醒。

### 阶段 G：比赛演示与评测

- 准备 2–3 分钟稳定演示脚本和断网可用的降级方案。
- 建立 ASR 专业词、KWS、VAD、结构化准确率和端到端延迟测试集。
- 展示重点不是模块数量，而是完整闭环：边做边说、自动记录、发现缺项、主动追问、最终生成可用记录。

## 8. 建议的模块边界

```text
src/
  audio/          麦克风、VAD、播放与音频格式
  wakeword/       离线唤醒检测
  asr/            FunASR 识别与识别结果结构
  core/           状态机、会话控制器、事件调度
  llm/            提示词、结构化输出、会话理解
  tts/            TTS统一接口、系统TTS与GPT-SoVITS适配器
  live2d/         状态/情绪/动作消息适配
  agents/         白名单工具与执行确认
  storage/        ASR、实验事件、会话、任务持久化
```

模块之间尽量传递数据对象或事件，不直接相互控制底层设备。例如 LLM 不直接播放声音，Live2D 不直接调用 LLM。

## 9. 开发原则与学习方式

每一轮只推进一个可独立验证的能力，并按以下顺序说明：

1. 目的：这一轮解决什么真实问题。
2. 技术路线：数据怎样流动、涉及哪些模块。
3. 设计原因：为什么现在这样做，有什么取舍。
4. 实现功能：代码完成后系统新增什么行为。
5. 所需知识：本轮应掌握的 Python、音频或架构概念。
6. 验证方法：用哪些输入和输出证明功能成立。
7. 下一步建议：验证通过后再进入哪一层。

代码说明以文件、类和函数的职责为主，不必逐行解释；重要状态变化、资源生命周期和容易出错的边界必须说明。

## 10. 当前关键文件

- `src/main.py`：程序入口、唤醒外循环和实验会话内循环。
- `src/config.py`：路径、采样率、ASR/KWS/VAD 模型配置。
- `src/asr/recognizer.py`：FunASR 模型加载和识别。
- `src/asr/schemas.py`：ASR 结果数据结构。
- `src/audio/vad_recorder.py`：VAD 自动录音。
- `src/audio/recorder.py`：手动录音兜底。
- `src/audio/feedback.py`：当前 Windows 唤醒提示音。
- `src/wakeword/detector.py`：关键词检测。
- `src/core/states.py`、`src/core/state_manager.py`：状态定义与切换。
- `src/storage/result_store.py`：JSONL 保存。

## 11. 恢复开发时的快速检查

```powershell
cd C:\Users\dahli\Desktop\asr_demo
.\.venv\Scripts\Activate.ps1
python -c "import torch; from funasr import AutoModel; print(torch.__version__); print('FunASR导入正常')"
python -m src.audio.test_vad
python -m src.wakeword.test_microphone
python -m src.main
```

运行主程序后，依次验证：模型只加载一次、唤醒成功、提示音正常、VAD 能自然停顿结束、ASR 输出和 JSONL 保存正常。

---

下一次从这里继续：**去掉实验 session 内的 Enter/q 控制，改为 VAD 自动连续监听，并使用语音结束指令退出会话。**
