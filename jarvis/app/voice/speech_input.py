import asyncio
import tempfile
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, AsyncGenerator

import speech_recognition as sr

from app.config import get_settings


@dataclass
class SpeechResult:
    text: str
    confidence: float
    language: str
    duration: float


class SpeechInput:
    '''Speech input supporting multiple providers (Google, Vosk).'''

    def __init__(self):
        self._settings = None
        self._recognizer = sr.Recognizer()
        self._microphone = None
        self._listening = False
        self._vosk_model = None
        self._vosk_input = None

    def _get_settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_microphone(self):
        if self._microphone is None:
            self._microphone = sr.Microphone()
        return self._microphone

    def _get_vosk_input(self):
        if self._vosk_input is None:
            from app.voice.vosk_input import VoskSpeechInput
            self._vosk_input = VoskSpeechInput()
        return self._vosk_input

    def _setup_vosk(self):
        if self._vosk_model is None:
            settings = self._get_settings()
            if settings.vosk_model_path:
                try:
                    from vosk import Model
                    self._vosk_model = Model(settings.vosk_model_path)
                except ImportError:
                    pass
        return self._vosk_model

    def is_microphone_available(self) -> bool:
        try:
            devices = sr.Microphone.list_microphone_names()
            return len(devices) > 0
        except Exception:
            import sounddevice as sd
            devices = sd.query_devices()
            return any(d['max_input_channels'] > 0 for d in devices)

    def is_vosk_available(self) -> bool:
        try:
            vosk_input = self._get_vosk_input()
            return vosk_input.is_available()
        except Exception:
            return False

    def get_microphone_status(self) -> dict:
        try:
            import sounddevice as sd
            sd_devices = sd.query_devices()
            input_devices = [d for d in sd_devices if d['max_input_channels'] > 0]
            default_input = sd.query_devices(kind='input')
            return {
                'microphone_available': len(input_devices) > 0,
                'default_device': default_input['name'],
                'input_devices_count': len(input_devices),
                'vosk_available': self.is_vosk_available(),
            }
        except Exception as e:
            return {
                'microphone_available': False,
                'error': str(e),
                'vosk_available': False,
            }

    async def listen_once(
        self,
        timeout: Optional[int] = None,
        phrase_timeout: Optional[int] = None,
        language: Optional[str] = None,
    ) -> SpeechResult:
        settings = self._get_settings()
        timeout = timeout or settings.speech_timeout
        phrase_timeout = phrase_timeout or settings.speech_phrase_timeout
        language = language or settings.speech_language

        provider = settings.speech_provider

        if provider == 'vosk':
            vosk_input = self._get_vosk_input()
            return await vosk_input.listen_once(
                timeout=timeout,
                phrase_timeout=phrase_timeout,
                language=language,
            )

        loop = asyncio.get_event_loop()

        def _listen():
            mic = self._get_microphone()
            with mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_timeout,
                )
            return audio

        audio = await loop.run_in_executor(None, _listen)

        def _recognize():
            try:
                if provider == 'google':
                    result = self._recognizer.recognize_google(audio, language=language, show_all=True)
                    if isinstance(result, dict) and result.get('alternative'):
                        best = result['alternative'][0]
                        return SpeechResult(
                            text=best.get('transcript', ''),
                            confidence=best.get('confidence', 0.0),
                            language=language,
                            duration=0.0,
                        )
                elif provider == 'vosk':
                    model = self._setup_vosk()
                    if model:
                        from vosk import KaldiRecognizer
                        rec = KaldiRecognizer(model, 16000)
                        rec.AcceptWaveform(audio.get_wav_data())
                        import json
                        result = json.loads(rec.FinalResult())
                        return SpeechResult(
                            text=result.get('text', ''),
                            confidence=result.get('confidence', 0.0),
                            language=language,
                            duration=0.0,
                        )
                else:
                    result = self._recognizer.recognize_google(audio, language=language, show_all=True)
                    if isinstance(result, dict) and result.get('alternative'):
                        best = result['alternative'][0]
                        return SpeechResult(
                            text=best.get('transcript', ''),
                            confidence=best.get('confidence', 0.0),
                            language=language,
                            duration=0.0,
                        )
            except sr.UnknownValueError:
                return SpeechResult(text='', confidence=0.0, language=language, duration=0.0)
            except sr.RequestError as e:
                raise RuntimeError(f'Speech recognition error: {e}')
            return SpeechResult(text='', confidence=0.0, language=language, duration=0.0)

        return await loop.run_in_executor(None, _recognize)

    async def listen_continuous(
        self,
        language: Optional[str] = None,
        callback=None,
    ) -> AsyncGenerator[SpeechResult, None]:
        settings = self._get_settings()
        provider = settings.speech_provider
        language = language or settings.speech_language

        if provider == 'vosk':
            vosk_input = self._get_vosk_input()
            async for result in vosk_input.listen_continuous(language=language, callback=callback):
                yield result
            return

        self._listening = True
        language = language or settings.speech_language

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
        if self._vosk_input:
            self._vosk_input.stop_listening()

    def is_listening(self) -> bool:
        return self._listening

    def list_microphones(self) -> list:
        try:
            return sr.Microphone.list_microphone_names()
        except Exception:
            import sounddevice as sd
            devices = sd.query_devices()
            return [str(i) + ': ' + d['name'] for i, d in enumerate(devices) if d['max_input_channels'] > 0]

    def set_microphone(self, device_index: int):
        self._microphone = sr.Microphone(device_index=device_index)
        if self._vosk_input:
            self._vosk_input.set_microphone(device_index)
