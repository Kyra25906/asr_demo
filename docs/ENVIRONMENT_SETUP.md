# asr_demo 本地运行环境

最后验证：2026-08-10

## 1. 统一版本

本项目当前统一使用：

```text
Python 3.11.9 64-bit
虚拟环境：C:\Users\dahli\Desktop\asr_demo\.venv
```

Python 3.14 环境仅保留在 `.venv-py314` 作为备用实验环境，不作为项目验收环境。

## 2. 创建环境

安装 Python 3.11.9 后，在项目目录执行：

```powershell
C:\Users\dahli\AppData\Local\Programs\Python\Python311\python.exe `
    -m venv .venv

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

不要把 `.venv`、模型缓存、真实 `.env` 或录音文件提交到 Git。

## 3. 配置 DeepSeek

复制 `.env.example` 为 `.env`，再填写本地 API Key。`.env` 已由 `.gitignore` 排除。

统一合同影子模式默认关闭：

```text
UNIFIED_SHADOW_ENABLED=false
```

只有在明确允许本次最终 ASR 忠实转写发送给 DeepSeek 后，才可在本机 `.env` 临时改为 `true`。该开关不会上传音频，但会让非精确命令额外调用一次统一理解模型；不得把一次真实测试授权视为长期外发授权。

## 4. 验证环境

```powershell
.\.venv\Scripts\python.exe --version

.\.venv\Scripts\python.exe -c `
    "import dotenv, sherpa_onnx, sounddevice, soundfile, funasr, modelscope, torch; print('imports OK')"

.\.venv\Scripts\python.exe -B -m unittest discover `
    -s tests `
    -v
```

2026-08-10 的已验证基线：

```text
src.main import OK
Ran 392 tests
OK
VAD模型加载成功
唤醒词模型加载成功
SenseVoice与FSMN-VAD模型加载成功
```

## 5. 模型缓存说明

SenseVoice 和 FunASR VAD 模型缓存在用户目录的 ModelScope 缓存中，不保存在项目仓库。
当前 `AutoModel` 使用模型名和 `master` 修订，启动时可能联网检查模型文件。
后续任务将固定模型修订并关闭不必要的更新检查，以支持更快、更稳定的离线启动。
