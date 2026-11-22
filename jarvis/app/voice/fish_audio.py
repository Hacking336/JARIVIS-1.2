import asyncio
import concurrent.futures
import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiofiles
import httpx

from app.config import get_settings


@dataclass
class TTSResult:
    audio_data: bytes
    format: str
    sample_rate: int
    duration_estimate: float
    cached: bool = False


class FishAudioProvider:
    def __init__(self):
        self._settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None
        self._cache_dir = Path('voice_cache')
        self._cache_dir.mkdir(exist_ok=True)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._settings.fish_audio_base_url,
                headers={
                    'Authorization': f'Bearer {self._settings.fish_audio_api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=60.0,
            )
        return self._client

    def _get_cache_key(self, text: str, speed: float) -> str:
        content = f'{text}:{speed}:{self._settings.fish_audio_voice_model_id}'
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f'{cache_key}.mp3'

    async def _load_from_cache(self, cache_key: str) -> Optional[bytes]:
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            async with aiofiles.open(cache_path, 'rb') as f:
                return await f.read()
        return None

    async def _save_to_cache(self, cache_key: str, audio_data: bytes) -> None:
        cache_path = self._get_cache_path(cache_key)
        async with aiofiles.open(cache_path, 'wb') as f:
            await f.write(audio_data)

    async def synthesize(
        self,
        text: str,
        speed: Optional[float] = None,
        sample_rate: Optional[int] = None,
    ) -> TTSResult:
        if not self._settings.fish_audio_api_key:
            raise ValueError('Fish Audio API key not configured')

        speed = speed or self._settings.fish_audio_speed
        sample_rate = sample_rate or self._settings.fish_audio_sample_rate
        cache_key = self._get_cache_key(text, speed)

        cached_audio = await self._load_from_cache(cache_key)
        if cached_audio:
            return TTSResult(
                audio_data=cached_audio,
                format='mp3',
                sample_rate=sample_rate,
                duration_estimate=len(text) * 0.08 / speed,
                cached=True,
            )

        client = await self._get_client()
        payload = {
            'text': text,
            'model_id': self._settings.fish_audio_voice_model_id,
            'speed': speed,
            'sample_rate': sample_rate,
        }

        response = await client.post('/v1/tts', json=payload)
        response.raise_for_status()

        audio_data = response.content
        await self._save_to_cache(cache_key, audio_data)

        return TTSResult(
            audio_data=audio_data,
            format='mp3',
            sample_rate=sample_rate,
            duration_estimate=len(text) * 0.08 / speed,
            cached=False,
        )

    async def synthesize_streaming(
        self,
        text: str,
        speed: Optional[float] = None,
        sample_rate: Optional[int] = None,
    ):
        if not self._settings.fish_audio_api_key:
            raise ValueError('Fish Audio API key not configured')

        speed = speed or self._settings.fish_audio_speed
        sample_rate = sample_rate or self._settings.fish_audio_sample_rate

        client = await self._get_client()
        payload = {
            'text': text,
            'model_id': self._settings.fish_audio_voice_model_id,
            'speed': speed,
            'sample_rate': sample_rate,
            'streaming': True,
        }

        async with client.stream('POST', '/v1/tts', json=payload) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def clear_cache(self, max_age_days: int = 30) -> int:
        count = 0
        now = time.time()
        max_age = max_age_days * 86400
        for cache_file in self._cache_dir.glob('*.mp3'):
            try:
                if now - cache_file.stat().st_mtime > max_age:
                    cache_file.unlink()
                    count += 1
            except OSError:
                pass
        return count

    def get_cache_size(self) -> int:
        total = 0
        for cache_file in self._cache_dir.glob('*.mp3'):
            try:
                total += cache_file.stat().st_size
            except OSError:
                pass
        return total


class LocalTTSProvider:
    def __init__(self):
        self._engine = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='tts')

    def _get_engine(self):
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', 180)
                self._engine.setProperty('volume', 0.9)
            except ImportError:
                raise RuntimeError('pyttsx3 not installed. Install with: pip install pyttsx3')
        return self._engine

    def synthesize(self, text: str) -> TTSResult:
        import tempfile
        engine = self._get_engine()

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            temp_path = tmp.name

        try:
            engine.save_to_file(text, temp_path)
            engine.runAndWait()

            with open(temp_path, 'rb') as f:
                audio_data = f.read()

            return TTSResult(
                audio_data=audio_data,
                format='wav',
                sample_rate=22050,
                duration_estimate=len(text) * 0.06,
                cached=False,
            )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def synthesize_async(self, text: str) -> TTSResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.synthesize, text)

    def __del__(self):
        if self._executor:
            self._executor.shutdown(wait=False)
