"""旧导入路径的兼容层；新代码请使用ASRBackend和工厂。"""

from src.asr.backend import ASRBackend


SpeechRecognizer = ASRBackend

__all__ = ["ASRBackend", "SpeechRecognizer"]
