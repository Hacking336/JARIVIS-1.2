import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, PropertyMock

import pytest

from app.integrations.ai.llamacpp_server import (
    LlamaCppServerManager,
    LlamaCppServerError,
    LlamaCppServerNotFoundError,
    LlamaCppModelNotFoundError,
    LlamaCppServerStartupError,
)
from app.config import Settings


class TestLlamaCppServerManager:
    @pytest.fixture
    def mock_settings(self):
        settings = Mock(spec=Settings)
        settings.llamacpp_server_path = 'llama-server.exe'
        settings.llamacpp_model_path = '/fake/model.gguf'
        settings.llamacpp_host = '127.0.0.1'
        settings.llamacpp_port = 8081
        settings.llamacpp_ctx_size = 4096
        settings.llamacpp_n_gpu_layers = -1
        settings.llamacpp_threads = 0
        settings.llamacpp_startup_timeout = 5
        settings.llamacpp_health_check_timeout = 2
        return settings

    @pytest.fixture
    def manager(self, mock_settings):
        with patch('app.integrations.ai.llamacpp_server.get_settings', return_value=mock_settings):
            return LlamaCppServerManager()

    def test_validate_executable_not_found(self, manager):
        with patch('shutil.which', return_value=None):
            with pytest.raises(LlamaCppServerNotFoundError):
                manager._validate_executable()

    def test_validate_executable_found_in_path(self, manager):
        with patch('shutil.which', return_value='/usr/bin/llama-server.exe'):
            path = manager._validate_executable()
            assert path.name == 'llama-server.exe'

    def test_validate_executable_absolute_path_exists(self, manager):
        mock_settings = Mock()
        mock_settings.llamacpp_server_path = '/absolute/path/llama-server.exe'
        manager._settings = mock_settings
        with patch('os.path.isabs', return_value=True):
            with patch('pathlib.Path.exists', return_value=True):
                path = manager._validate_executable()
                assert Path(str(path)).as_posix() == '/absolute/path/llama-server.exe'

    def test_validate_executable_absolute_path_not_exists(self, manager):
        mock_settings = Mock()
        mock_settings.llamacpp_server_path = '/nonexistent/llama-server.exe'
        manager._settings = mock_settings
        with patch('os.path.isabs', return_value=True):
            with patch('pathlib.Path.exists', return_value=False):
                with pytest.raises(LlamaCppServerNotFoundError):
                    manager._validate_executable()

    def test_validate_model_exists(self, manager):
        with patch('pathlib.Path.exists', return_value=True):
            path = manager._validate_model()
            assert Path(str(path)).as_posix() == '/fake/model.gguf'

    def test_validate_model_not_exists(self, manager):
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(LlamaCppModelNotFoundError):
                manager._validate_model()

    def test_build_command_basic(self, manager):
        mock_settings = Mock()
        mock_settings.llamacpp_host = '127.0.0.1'
        mock_settings.llamacpp_port = 8081
        mock_settings.llamacpp_ctx_size = 4096
        mock_settings.llamacpp_n_gpu_layers = -1
        mock_settings.llamacpp_threads = 0
        manager._settings = mock_settings

        cmd = manager._build_command(Path('/fake/llama-server.exe'), Path('/fake/model.gguf'))
        cmd_str = ' '.join(cmd)
        assert 'llama-server.exe' in cmd[0]
        assert '--model' in cmd
        assert 'model.gguf' in cmd_str
        assert '--host' in cmd
        assert '127.0.0.1' in cmd
        assert '--port' in cmd
        assert '8081' in cmd
        assert '--ctx-size' in cmd
        assert '4096' in cmd

    def test_build_command_with_gpu_layers(self, manager):
        mock_settings = Mock()
        mock_settings.llamacpp_host = '127.0.0.1'
        mock_settings.llamacpp_port = 8081
        mock_settings.llamacpp_ctx_size = 4096
        mock_settings.llamacpp_n_gpu_layers = 20
        mock_settings.llamacpp_threads = 4
        manager._settings = mock_settings

        cmd = manager._build_command(Path('/fake/llama-server.exe'), Path('/fake/model.gguf'))
        assert '--n-gpu-layers' in cmd
        assert '20' in cmd
        assert '--threads' in cmd
        assert '4' in cmd

    @pytest.mark.asyncio
    async def test_start_executable_not_found(self, manager):
        with patch.object(manager, '_validate_executable', side_effect=LlamaCppServerNotFoundError('not found')):
            with pytest.raises(LlamaCppServerNotFoundError):
                await manager.start()

    @pytest.mark.asyncio
    async def test_start_model_not_found(self, manager):
        with patch.object(manager, '_validate_executable', return_value=Path('/fake/exe')):
            with patch.object(manager, '_validate_model', side_effect=LlamaCppModelNotFoundError('not found')):
                with pytest.raises(LlamaCppModelNotFoundError):
                    await manager.start()

    @pytest.mark.asyncio
    async def test_start_server_exits_immediately(self, manager):
        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = (b'stdout', b'stderr error')
        with patch.object(manager, '_validate_executable', return_value=Path('/fake/exe')):
            with patch.object(manager, '_validate_model', return_value=Path('/fake/model.gguf')):
                with patch('subprocess.Popen', return_value=mock_process):
                    with pytest.raises(Exception) as exc_info:
                        await manager.start()
                    assert 'exited unexpectedly' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_timeout(self, manager):
        mock_process = Mock()
        mock_process.poll.return_value = None
        with patch.object(manager, '_validate_executable', return_value=Path('/fake/exe')):
            with patch.object(manager, '_validate_model', return_value=Path('/fake/model.gguf')):
                with patch('subprocess.Popen', return_value=mock_process):
                    with patch('httpx.AsyncClient.get', side_effect=Exception('connection failed')):
                        with pytest.raises(Exception) as exc_info:
                            await manager.start()
                        assert 'did not become ready' in str(exc_info.value)

    def test_stop_not_running(self, manager):
        manager._process = None
        manager.stop()

    def test_stop_running(self, manager):
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        manager._process = mock_process
        manager._ready = True
        manager.stop()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()

    def test_stop_kill_on_timeout(self, manager):
        mock_process = Mock()
        mock_process.poll.return_value = None
        timeout_exc = subprocess.TimeoutExpired('wait', 5)
        mock_process.wait.side_effect = [timeout_exc, None]
        manager._process = mock_process
        manager._ready = True
        manager.stop()
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_is_running_false_when_not_started(self, manager):
        assert manager.is_running is False

    def test_get_diagnostics(self, manager):
        diag = manager.get_diagnostics()
        assert 'running' in diag
        assert 'base_url' in diag
        assert 'pid' in diag
        assert 'executable' in diag
        assert 'model' in diag
