import asyncio
import io
import tempfile
import os
import sys
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Try pygame for cross-platform audio
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None

# Windows native audio playback
if sys.platform == 'win32':
    try:
        import winsound
        WINSOUND_AVAILABLE = True
    except ImportError:
        WINSOUND_AVAILABLE = False
else:
    WINSOUND_AVAILABLE = False


@dataclass
class PlaybackState:
    playing: bool = False
    paused: bool = False
    current_text: str = ''
    position: float = 0.0
    duration: float = 0.0


class AudioPlayer:
    def __init__(self):
        self._state = PlaybackState()
        self._initialized = False
        self._temp_file: Optional[str] = None
        self._lock = asyncio.Lock()
        self._use_winsound = WINSOUND_AVAILABLE and sys.platform == 'win32'
        self._use_pygame = PYGAME_AVAILABLE and not self._use_winsound

    def _init_mixer(self):
        if self._use_pygame:
            if not self._initialized:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
                self._initialized = True
        elif not self._use_winsound:
            raise RuntimeError('No audio backend available. Install pygame or use Windows.')

    async def play(self, audio_data: bytes, format: str = 'mp3') -> bool:
        async with self._lock:
            try:
                self.stop()
                self._init_mixer()

                with tempfile.NamedTemporaryFile(suffix=f'.{format}', delete=False) as tmp:
                    tmp.write(audio_data)
                    self._temp_file = tmp.name

                if self._use_winsound:
                    # winsound only supports WAV
                    if format.lower() != 'wav':
                        # Convert would be needed, but LocalTTSProvider outputs WAV
                        pass
                    winsound.PlaySound(self._temp_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    self._state.playing = True
                    self._state.paused = False
                    return True
                elif self._use_pygame:
                    pygame.mixer.music.load(self._temp_file)
                    pygame.mixer.music.play()
                    self._state.playing = True
                    self._state.paused = False
                    return True
                return False
            except Exception as e:
                print(f'Audio playback error: {e}')
                return False

    async def play_file(self, file_path: str) -> bool:
        async with self._lock:
            try:
                if self._use_winsound:
                    self.stop()
                    winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    self._state.playing = True
                    self._state.paused = False
                    return True
                elif self._use_pygame:
                    self.stop()
                    self._init_mixer()
                    pygame.mixer.music.load(file_path)
                    pygame.mixer.music.play()
                    self._state.playing = True
                    self._state.paused = False
                    return True
                return False
            except Exception as e:
                print(f'Audio playback error: {e}')
                return False

    def pause(self):
        if self._use_pygame and self._state.playing and not self._state.paused:
            pygame.mixer.music.pause()
            self._state.paused = True
        # winsound doesn't support pause

    def resume(self):
        if self._use_pygame and self._state.playing and self._state.paused:
            pygame.mixer.music.unpause()
            self._state.paused = False

    def stop(self):
        if self._use_winsound:
            # winsound doesn't have explicit stop, but we can play a silent sound
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            self._state.playing = False
            self._state.paused = False
            self._state.position = 0.0
            if self._temp_file:
                try:
                    os.unlink(self._temp_file)
                except OSError:
                    pass
                self._temp_file = None
        elif self._use_pygame:
            if self._state.playing:
                pygame.mixer.music.stop()
                self._state.playing = False
                self._state.paused = False
                self._state.position = 0.0
                if self._temp_file:
                    try:
                        os.unlink(self._temp_file)
                    except OSError:
                        pass
                    self._temp_file = None

    def set_volume(self, volume: float):
        if self._use_pygame:
            volume = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(volume)

    def get_state(self) -> PlaybackState:
        if self._use_pygame and self._state.playing:
            self._state.position = pygame.mixer.music.get_pos() / 1000.0
        return self._state

    def is_playing(self) -> bool:
        if self._use_winsound:
            # No reliable way to check with winsound SND_ASYNC
            return self._state.playing
        elif self._use_pygame:
            return self._state.playing and pygame.mixer.music.get_busy()
        return False

    def cleanup(self):
        self.stop()
        if self._use_pygame and self._initialized:
            pygame.mixer.quit()
            self._initialized = False


class VoiceOutput:
    def __init__(self):
        self._player = AudioPlayer()
        self._fish_audio = None
        self._local_tts = None
        self._speaking = False
        self._current_task: Optional[asyncio.Task] = None

    def _get_fish_audio(self):
        if self._fish_audio is None:
            from app.voice.fish_audio import FishAudioProvider
            self._fish_audio = FishAudioProvider()
        return self._fish_audio

    def _get_local_tts(self):
        if self._local_tts is None:
            from app.voice.fish_audio import LocalTTSProvider
            self._local_tts = LocalTTSProvider()
        return self._local_tts

    async def speak(
        self,
        text: str,
        provider: str = 'auto',
        speed: Optional[float] = None,
    ) -> bool:
        if not text.strip():
            return False

        self._speaking = True

        try:
            if provider == 'fish_audio' or (provider == 'auto' and self._has_fish_audio()):
                return await self._speak_fish_audio(text, speed)
            else:
                return await self._speak_local(text)
        except Exception as e:
            print(f'Speech synthesis error: {e}')
            if provider == 'fish_audio' or provider == 'auto':
                try:
                    return await self._speak_local(text)
                except Exception:
                    pass
            return False
        finally:
            self._speaking = False

    def _has_fish_audio(self) -> bool:
        from app.config import get_settings
        settings = get_settings()
        return bool(settings.fish_audio_api_key)

    async def _speak_fish_audio(self, text: str, speed: Optional[float]) -> bool:
        fish_audio = self._get_fish_audio()
        result = await fish_audio.synthesize(text, speed=speed)
        return await self._player.play(result.audio_data, result.format)

    async def _speak_local(self, text: str) -> bool:
        local_tts = self._get_local_tts()
        result = await local_tts.synthesize_async(text)
        return await self._player.play(result.audio_data, result.format)

    async def speak_streaming(
        self,
        text: str,
        speed: Optional[float] = None,
    ) -> bool:
        if not self._has_fish_audio():
            return await self._speak_local(text)

        self._speaking = True
        try:
            fish_audio = self._get_fish_audio()
            self._player._init_mixer()

            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                temp_path = tmp.name

            try:
                async for chunk in fish_audio.synthesize_streaming(text, speed=speed):
                    with open(temp_path, 'ab') as f:
                        f.write(chunk)

                return await self._player.play_file(temp_path)
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        finally:
            self._speaking = False

    def stop_speaking(self):
        self._player.stop()
        self._speaking = False

    def pause_speaking(self):
        self._player.pause()

    def resume_speaking(self):
        self._player.resume()

    def is_speaking(self) -> bool:
        return self._speaking or self._player.is_playing()

    def set_volume(self, volume: float):
        self._player.set_volume(volume)

    def get_state(self) -> PlaybackState:
        return self._player.get_state()

    def cleanup(self):
        self.stop_speaking()
        self._player.cleanup()
        if self._fish_audio:
            try:
                asyncio.get_event_loop().create_task(self._fish_audio.close())
            except RuntimeError:
                pass
