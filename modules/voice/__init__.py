"""Componentes del pipeline de voz."""

from modules.voice.config import VoiceConfig
from modules.voice.speech_recognizer import SpeechRecognizer
from modules.voice.text_utils import clean_command_text
from modules.voice.vad_segmenter import VadSegmenter
from modules.voice.vosk_engine import VoskEngine
from modules.voice.wake_word_detector import WakeWordDetector

__all__ = [
    "VoiceConfig",
    "VoskEngine",
    "WakeWordDetector",
    "SpeechRecognizer",
    "VadSegmenter",
    "clean_command_text",
]
