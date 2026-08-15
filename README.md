# asr_demo —— 语音实验记录智能体

> 面向高校实验与学习场景的**具身语音智能体**：对着麦克风"说"出实验过程，系统听懂、结构化记录、追问确认，全程不用动手打字。

中国科学技术大学「107杯」智能体开发大赛项目。

---

## 它解决什么问题

做实验时，手是湿的、戴着护目镜、盯着操作台，不方便停下来打字记录。这个系统让你**边做实验边口述**：

```
你：先加 5 毫升缓冲液，然后加热到 60 度……
系统：听懂了，结构化记录成一条条实验事件；缺信息会追问，疑似听错会确认。
```

核心价值：**让"记录"这件事从"事后补、手动敲"变成"边做边说、自动结构化"**，实验过程和原始口述都完整可追溯。

---

## 核心能力

| 能力 | 说明 |
|---|---|
| 🎙️ 离线唤醒 | 说「小科小科」免按键启动，本地模型识别，不依赖联网 |
| ⚡ 连续口述不卡 | 后台单线程处理，说话**不等大模型**（非阻塞 + 背压），可以连珠炮式说 |
| 🧠 结构化理解 | 把口述理解成结构化实验事件（操作/观察/测量/异常），缺字段自动追问 |
| ❓ 追问与确认 | 缺温度/时长→追问；疑似同音错词（"移液枪"听成"一夜枪"）→确认，不覆盖原文 |
| 🗣️ 自然语言控制 | "这个问题先跳过""查看待确认问题""今天先记录到这里吧"等口语命令 |
| 🔒 安全确认 | 高风险动作（如结束会话）必须二次确认，不靠大模型猜 |
| 🛡️ 降级容错 | 大模型失败时保留原始记录，并明确告诉用户"结构化处理暂时不可用" |
| 📦 数据可追溯 | 原始 ASR、结构化事件、确认记录分别落盘 JSONL，带 session/segment 编号 |

---

## 系统架构（分层）

```text
麦克风 ──> VAD 分段 ──> SenseVoice 中文识别（ASR）
                              │
              ┌───────────────┴────────────────┐
              │  精确命令快速路径（零 LLM）       │
              │  如"这个问题先跳过"             │
              └───────────────┬────────────────┘
                              │
                   统一理解（DeepSeek LLM）
                    实验 / 控制 / 弃权 / 降级
                              │
                    分派 → 采用 → 执行
                    （创建追问/回答/暂缓/确认/结束确认）
                              │
                    持久化：ASR JSONL + 事件 JSONL + 确认 JSONL
                              │
                    会话上下文（后续段能"看见"前文）
```

**非阻塞设计**：主线程只负责"录音→提交后台队列"，后台单线程按序执行"理解→落盘→执行"六步，结果算完当场显示——录音和 LLM 互不阻塞。

**分层原则**（架构核心）：

- **机制与业务分离**：后台队列 `OrderedTaskQueue` 是通用"传送带"（不认识任何业务词），业务工人 `UnifiedSegmentProcessor` 是"装配工"（六步流水线）——换领域可复用队列、不重写。
- **原始数据优先**：模型推断永远不覆盖原始 ASR 原文。
- **高风险必确认**：结束、状态写入等高风险动作有明确边界。

---

## 快速开始

```powershell
# 1. 创建并激活虚拟环境（Python 3.11.9）
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell 激活

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 DeepSeek：复制 .env.example 为 .env，填 API Key
#    （.env 已被 .gitignore 排除，不提交）

# 4. 启动（在项目根目录）
python -B -m src.main
```

启动后：说「小科小科」唤醒 → 听到提示音 → 开始口述实验过程 → 说完说「结束实验记录」（或自然表达"今天先记录到这里吧"再确认）。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 唤醒 | sherpa-onnx（离线关键词唤醒） |
| 语音识别 | FunASR / SenseVoice（中文，模型无关后端） |
| 大模型 | DeepSeek（统一理解 + 结构化输出） |
| 音频 | sounddevice / soundfile |
| 语言 | Python 3.11.9 |

---

## 项目结构（关键文件）

```text
src/
  main.py                      # 入口：组合根 + 主循环（录音→提交后台→显示）
  audio/                       # 唤醒、VAD、录音、提示音
  asr/                         # 模型无关 ASR 后端 + 工厂
  core/
    interaction_command.py     # 精确命令解析（零 LLM 快速路径）
    unified_understanding.py   # 统一理解数据合同
    unified_acceptance_bypass.py  # 分派→采用链
    clarification_executor.py  # 追问/回答/暂缓/确认执行
    ordered_task_queue.py      # 通用后台队列（机制层，单线程+背压）
    unified_segment_processor.py # 六步业务流水线（业务层）
    reply_coordinator.py       # 待确认问题协调器
    session_context.py         # 会话上下文
  storage/                     # ASR/事件/确认 JSONL 持久化
tests/                         # 单元 + 集成测试
docs/                          # 文档（任务清单/架构/交接等）
```

---

## 当前状态

- **自动测试**：`490 tests OK`（Python 3.11.9）
- **硬问题已清零**（非阻塞录音、结束确认、暂缓、降级提示等均真实验收通过）
- **下一步**：`PRESENT-INTEGRATE-01`（最小消息链路，做输出层展示）

---

## 文档指引

- 任务进度与验收状态：`docs/PROJECT_TASK_CHECKLIST.md`
- 架构与设计取舍：`docs/PROJECT_ARCHITECTURE.md`
- 环境配置：`docs/ENVIRONMENT_SETUP.md`
- 输出/展示政策：`docs/OUTPUT_PRESENTATION_POLICY.md`
- 体验走查清单：`docs/UX_WALKTHROUGH_CHECKLIST.md`
- 学习复盘：`LEARNING_REVIEW_FROM_DEVELOPMENT.md`
