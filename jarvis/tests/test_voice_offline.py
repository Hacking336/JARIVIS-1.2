import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from app.voice.vosk_input import VoskSpeechInput
from app.voice.speech_input import SpeechInput
from app.voice.speech_output import VoiceOutput, AudioPlayer
from app.config import Settings


class TestVoskSpeechInput:
    @pytest.fixture
    def mock_settings(self):
        settings = Mock(spec=Settings)
        settings.vosk_model_path = '/fake/vosk-model'
        settings.speech_timeout = 5
        settings.speech_phrase_timeout = 3
        settings.speech_language = 'en-US'
        return settings

    @pytest.fixture
    def vosk_input(self, mock_settings):
        with patch('app.voice.vosk_input.get_settings', return_value=mock_settings):
            return VoskSpeechInput()

    def test_is_available_model_not_found(self, vosk_input):
        with patch('pathlib.Path.exists', return_value=False):
            assert vosk_input.is_available() is False

    def test_is_available_model_found(self, vosk_input):
        with patch('pathlib.Path.exists', return_value=True):
            with patch('vosk.Model'):
                with patch('sounddevice.query_devices', return_value=[{'max_input_channels': 1}]):
                    assert vosk_input.is_available() is True

    @pytest.mark.asyncio
    async def test_listen_once_timeout(self, vosk_input):
        with patch.object(vosk_input, '_get_model'):
            with patch.object(vosk_input, '_get_recognizer'):
                with patch('sounddevice.RawInputStream'):
                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock()
                        result = await vosk_input.listen_once(timeout=0.1)
                        assert result.text == ''
                        assert result.confidence == 0.0


class TestSpeechInputVosk:
    @pytest.fixture
    def mock_settings(self):
        settings = Mock(spec=Settings)
        settings.speech_provider = 'vosk'
        settings.vosk_model_path = '/fake/vosk-model'
        settings.speech_timeout = 5
        settings.speech_phrase_timeout = 3
        settings.speech_language = 'en-US'
        return settings

    @pytest.fixture
    def speech_input(self, mock_settings):
        with patch('app.voice.speech_input.get_settings', return_value=mock_settings):
            return SpeechInput()

    def test_is_vosk_available(self, speech_input):
        with patch.object(speech_input, '_get_vosk_input') as mock_get_vosk:
            mock_vosk = Mock()
            mock_vosk.is_available.return_value = True
            mock_get_vosk.return_value = mock_vosk
            assert speech_input.is_vosk_available() is True

    @pytest.mark.asyncio
    async def test_listen_once_uses_vosk(self, speech_input):
        with patch.object(speech_input, '_get_vosk_input') as mock_get_vosk:
            mock_vosk = AsyncMock()
            from app.voice.speech_input import SpeechResult
            result = SpeechResult(text='hello', confidence=1.0, language='en-US', duration=0.0)
            mock_vosk.listen_once.return_value = result
            mock_get_vosk.return_value = mock_vosk

            result = await speech_input.listen_once()
            assert result.text == 'hello'
            mock_vosk.listen_once.assert_called_once()


class TestVoiceOutputLocalTTS:
    @pytest.fixture
    def voice_output(self):
        return VoiceOutput()

    @pytest.mark.asyncio
    async def test_speak_local(self, voice_output):
        with patch.object(voice_output, '_get_local_tts') as mock_get_tts:
            mock_tts = AsyncMock()
            mock_tts.synthesize_async.return_value = Mock(
                audio_data=b'fake_audio',
                format='wav',
                sample_rate=22050,
                duration_estimate=1.0
            )
            mock_get_tts.return_value = mock_tts

            with patch.object(voice_output._player, 'play', return_value=True) as mock_play:
                result = await voice_output.speak('test', provider='local')
                assert result is True
                mock_tts.synthesize_async.assert_called_once_with('test')
                mock_play.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_local_fallback(self, voice_output):
        with patch.object(voice_output, '_get_fish_audio') as mock_get_fish:
            mock_fish = AsyncMock()
            mock_fish.synthesize.side_effect = Exception('API error')
            mock_get_fish.return_value = mock_fish

            with patch.object(voice_output, '_get_local_tts') as mock_get_tts:
                mock_tts = AsyncMock()
                mock_tts.synthesize_async.return_value = Mock(
                    audio_data=b'fake_audio',
                    format='wav',
                    sample_rate=22050,
                    duration_estimate=1.0
                )
                mock_get_tts.return_value = mock_tts

                with patch.object(voice_output._player, 'play', return_value=True):
                    result = await voice_output.speak('test', provider='auto')
                    assert result is True
                    mock_tts.synthesize_async.assert_called_once_with('test')
