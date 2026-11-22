import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import httpx

from app.voice.fish_audio import FishAudioProvider, LocalTTSProvider, TTSResult
from app.config import Settings


class TestFishAudioProvider:
    @pytest.fixture
    def provider(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = "test-api-key"
            settings.fish_audio_voice_model_id = "14129c3e320149449d6bada6862f7338"
            settings.fish_audio_base_url = "https://api.fish.audio"
            settings.fish_audio_speed = 1.0
            settings.fish_audio_sample_rate = 44100
            mock_settings.return_value = settings
            return FishAudioProvider()

    def test_provider_initialization(self, provider):
        assert provider._settings.fish_audio_api_key == "test-api-key"
        assert provider._settings.fish_audio_voice_model_id == "14129c3e320149449d6bada6862f7338"

    def test_cache_key_generation(self, provider):
        key1 = provider._get_cache_key("hello", 1.0)
        key2 = provider._get_cache_key("hello", 1.0)
        key3 = provider._get_cache_key("hello", 1.5)
        key4 = provider._get_cache_key("world", 1.0)

        assert key1 == key2
        assert key1 != key3
        assert key1 != key4
        assert len(key1) == 32

    def test_cache_path_generation(self, provider):
        path = provider._get_cache_path("testkey123")
        assert path.name == "testkey123.mp3"
        assert "voice_cache" in str(path)

    @pytest.mark.asyncio
    async def test_synthesize_no_api_key(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = None
            mock_settings.return_value = settings
            provider = FishAudioProvider()

            with pytest.raises(ValueError, match="Fish Audio API key not configured"):
                await provider.synthesize("test")

    @pytest.mark.asyncio
    async def test_synthesize_success(self, provider):
        mock_response = Mock()
        mock_response.content = b"fake-audio-data"
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        provider._client = mock_client

        result = await provider.synthesize("Hello world")

        assert isinstance(result, TTSResult)
        assert result.audio_data == b"fake-audio-data"
        assert result.format == "mp3"
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_synthesize_cached(self, provider):
        # First call to cache
        mock_response = Mock()
        mock_response.content = b"cached-audio-data"
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        await provider.synthesize("Cache test")

        # Second call should use cache
        result = await provider.synthesize("Cache test")
        assert result.cached is True
        assert result.audio_data == b"cached-audio-data"

    @pytest.mark.asyncio
    async def test_synthesize_http_error(self, provider):
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=httpx.HTTPError("401 Unauthorized"))

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        with pytest.raises(httpx.HTTPError):
            await provider.synthesize("test")

    @pytest.mark.asyncio
    async def test_synthesize_with_custom_speed(self, provider):
        mock_response = Mock()
        mock_response.content = b"audio-data"
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        result = await provider.synthesize("test", speed=1.5)
        assert result is not None

        # Verify the payload includes custom speed
        call_args = mock_client.post.call_args
        assert call_args[1]['json']['speed'] == 1.5

    @pytest.mark.asyncio
    async def test_close(self, provider):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        provider._client = mock_client

        await provider.close()

        mock_client.aclose.assert_called_once()
        assert provider._client is None

    def test_clear_cache(self, provider):
        # Create some fake cache files
        provider._cache_dir.mkdir(exist_ok=True)
        (provider._cache_dir / "test1.mp3").write_bytes(b"test")
        (provider._cache_dir / "test2.mp3").write_bytes(b"test")

        count = provider.clear_cache(max_age_days=0)
        assert count >= 2

    def test_get_cache_size(self, provider):
        provider._cache_dir.mkdir(exist_ok=True)
        (provider._cache_dir / "test.mp3").write_bytes(b"x" * 1000)

        size = provider.get_cache_size()
        assert size >= 1000


class TestLocalTTSProvider:
    @pytest.fixture
    def provider(self):
        return LocalTTSProvider()

    def test_initialization(self, provider):
        assert provider._engine is None

    def test_synthesize_without_pyttsx3(self, provider):
        with patch.dict('sys.modules', {'pyttsx3': None}):
            with pytest.raises(RuntimeError, match="pyttsx3 not installed"):
                provider.synthesize("test")

    @pytest.mark.asyncio
    async def test_synthesize_async(self, provider):
        with patch.dict('sys.modules', {'pyttsx3': None}):
            with pytest.raises(RuntimeError):
                await provider.synthesize_async("test")


class TestTTSResult:
    def test_result_creation(self):
        result = TTSResult(
            audio_data=b"test-audio",
            format="mp3",
            sample_rate=44100,
            duration_estimate=5.0,
            cached=False,
        )
        assert result.audio_data == b"test-audio"
        assert result.format == "mp3"
        assert result.sample_rate == 44100
        assert result.duration_estimate == 5.0
        assert result.cached is False

    def test_result_cached(self):
        result = TTSResult(
            audio_data=b"cached-audio",
            format="mp3",
            sample_rate=44100,
            duration_estimate=3.0,
            cached=True,
        )
        assert result.cached is True


class TestFishAudioAPIIntegration:
    @pytest.mark.asyncio
    async def test_api_endpoint_format(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = "test-key"
            settings.fish_audio_voice_model_id = "14129c3e320149449d6bada6862f7338"
            settings.fish_audio_base_url = "https://api.fish.audio"
            settings.fish_audio_speed = 1.0
            settings.fish_audio_sample_rate = 44100
            mock_settings.return_value = settings

            provider = FishAudioProvider()
            client = await provider._get_client()

            assert client.base_url == "https://api.fish.audio"
            assert client.headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = "test-key"
            settings.fish_audio_voice_model_id = "14129c3e320149449d6bada6862f7338"
            settings.fish_audio_base_url = "https://api.fish.audio"
            settings.fish_audio_speed = 1.0
            settings.fish_audio_sample_rate = 44100
            mock_settings.return_value = settings

            provider = FishAudioProvider()

            mock_response = Mock()
            mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=Mock(),
                response=Mock(status_code=429)
            ))

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            provider._client = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.synthesize("test")

    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = "invalid-key"
            settings.fish_audio_voice_model_id = "14129c3e320149449d6bada6862f7338"
            settings.fish_audio_base_url = "https://api.fish.audio"
            settings.fish_audio_speed = 1.0
            settings.fish_audio_sample_rate = 44100
            mock_settings.return_value = settings

            provider = FishAudioProvider()

            mock_response = Mock()
            mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=Mock(),
                response=Mock(status_code=401)
            ))

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            provider._client = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.synthesize("test")

    @pytest.mark.asyncio
    async def test_unavailable_model(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = "test-key"
            settings.fish_audio_voice_model_id = "nonexistent-model"
            settings.fish_audio_base_url = "https://api.fish.audio"
            settings.fish_audio_speed = 1.0
            settings.fish_audio_sample_rate = 44100
            mock_settings.return_value = settings

            provider = FishAudioProvider()

            mock_response = Mock()
            mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=Mock(status_code=404)
            ))

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            provider._client = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.synthesize("test")

    @pytest.mark.asyncio
    async def test_network_failure(self):
        with patch('app.voice.fish_audio.get_settings') as mock_settings:
            settings = Mock()
            settings.fish_audio_api_key = "test-key"
            settings.fish_audio_voice_model_id = "14129c3e320149449d6bada6862f7338"
            settings.fish_audio_base_url = "https://api.fish.audio"
            settings.fish_audio_speed = 1.0
            settings.fish_audio_sample_rate = 44100
            mock_settings.return_value = settings

            provider = FishAudioProvider()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.is_closed = False
            provider._client = mock_client

            with pytest.raises(httpx.ConnectError):
                await provider.synthesize("test")