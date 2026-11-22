import asyncio
import json
import numpy as np
import sounddevice as sd
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, AsyncGenerator

from app.config import get_settings


@dataclass
class SpeechResult:
    text: str
    confidence: float
    language: str
    duration: float


class VoskSpeechInput:
    '''Offline speech recognition using Vosk with sounddevice for audio capture.'''

    def __init__(self):
        self._settings = None
        self._model = None
        self._recognizer = None
        self._stream = None
        self._listening = False
        self._sample_rate = 16000
        self._device = None

    def _get_settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_model(self):
        if self._model is None:
            settings = self._get_settings()
            if settings.vosk_model_path:
                model_path = Path(settings.vosk_model_path)
                if not model_path.exists():
                    raise RuntimeError('Vosk model not found at: ' + str(model_path))
                try:
                    from vosk import Model
                    self._model = Model(str(model_path))
                except ImportError:
                    raise RuntimeError('Vosk not installed. Install with: pip install vosk')
        return self._model

    def _get_recognizer(self):
        if self._recognizer is None:
            model = self._get_model()
            if model:
                from vosk import KaldiRecognizer
                self._recognizer = KaldiRecognizer(model, self._sample_rate)
                self._recognizer.SetWords(True)
        return self._recognizer

    def is_available(self) -> bool:
        try:
            self._get_model()
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            return self._model is not None and len(input_devices) > 0
        except Exception:
            return False

    def get_diagnostics(self) -> dict:
        try:
            model = self._get_model()
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            default_input = sd.query_devices(kind='input')
            return {
                'model_loaded': self._model is not None,
                'model_path': str(self._settings.vosk_model_path) if self._settings else None,
                'input_devices': len(input_devices),
                'default_input_device': default_input['name'] if input_devices else None,
                'sample_rate': self._sample_rate,
                'vosk_available': True,
            }
        except Exception as e:
            return {
                'model_loaded': False,
                'error': str(e),
                'vosk_available': False,
            }

    async def listen_once(
        self,
        timeout: Optional[float] = None,
        phrase_timeout: Optional[float] = None,
        language: Optional[str] = None,
    ) -> SpeechResult:
        settings = self._get_settings()
        timeout = timeout or settings.speech_timeout
        phrase_timeout = phrase_timeout or settings.speech_phrase_timeout
        language = language or settings.speech_language

        recognizer = self._get_recognizer()
        if not recognizer:
            raise RuntimeError('Vosk recognizer not available. Check model path and Vosk installation.')

        loop = asyncio.get_event_loop()
        result_queue = asyncio.Queue()
        stop_event = asyncio.Event()

        def audio_callback(indata, frames, time_info, status):
            if status:
                print('Audio status: ' + str(status))
            # Convert cffi buffer to bytes for Vosk
            audio_bytes = bytes(indata)
            if recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(recognizer.Result())
                text = result.get('text', '').strip()
                if text:
                    result_queue.put_nowait(text)

        def _listen():
            try:
                with sd.RawInputStream(
                    samplerate=self._sample_rate,
                    blocksize=4000,
                    dtype='int16',
                    channels=1,
                    device=self._device,
                    callback=audio_callback,
                ):
                    import time
                    start_time = time.time()
                    while not stop_event.is_set():
                        if time.time() - start_time > timeout:
                            break
                        if not result_queue.empty():
                            break
                        time.sleep(0.1)
            except Exception as e:
                result_queue.put_nowait('__ERROR__:' + str(e))

        stop_event = asyncio.Event()
        listen_task = loop.run_in_executor(None, _listen)

        try:
            text = await asyncio.wait_for(result_queue.get(), timeout=timeout + 1.0)
            stop_event.set()
        except asyncio.TimeoutError:
            stop_event.set()
            return SpeechResult(text='', confidence=0.0, language=language, duration=0.0)

        await listen_task

        if text.startswith('__ERROR__:'):
            raise RuntimeError(text[10:])

        return SpeechResult(
            text=text,
            confidence=1.0,
            language=language,
            duration=0.0,
        )

    async def listen_continuous(
        self,
        language: Optional[str] = None,
        callback=None,
    ) -> AsyncGenerator[SpeechResult, None]:
        self._listening = True
        settings = self._get_settings()
        language = language or settings.speech_language

        recognizer = self._get_recognizer()
        if not recognizer:
            raise RuntimeError('Vosk recognizer not available.')

        while self._listening:
            try:
                result = await self.listen_once(language=language)
                if result.text:
                    if callback:
                        await callback(result)
                    yield result
            except Exception as e:
                if self._listening:
                    yield SpeechResult(text='', confidence=0.0, language=language, duration=0.0)
                await asyncio.sleep(0.5)

    def stop_listening(self):
        self._listening = False

    def is_listening(self) -> bool:
        return self._listening

    def list_microphones(self) -> list:
        devices = sd.query_devices()
        return [str(i) + ': ' + d['name'] for i, d in enumerate(devices) if d['max_input_channels'] > 0]

    def set_microphone(self, device_index: int):
        self._device = device_index

    def cleanup(self):
        self.stop_listening()
        if self._stream:
            self._stream.close()
            self._stream = None
