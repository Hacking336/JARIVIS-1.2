import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional
import httpx

from app.config import get_settings


class LlamaCppServerError(Exception):
    '''Raised when llama.cpp server management fails.'''
    pass


class LlamaCppServerNotFoundError(LlamaCppServerError):
    '''Raised when llama-server executable is not found.'''
    pass


class LlamaCppModelNotFoundError(LlamaCppServerError):
    '''Raised when GGUF model file is not found.'''
    pass


class LlamaCppServerStartupError(LlamaCppServerError):
    '''Raised when server fails to start within timeout.'''
    pass


class LlamaCppServerManager:
    '''Manages llama.cpp server subprocess lifecycle.'''

    def __init__(self):
        self._settings = get_settings()
        self._process = None
        self._base_url = ''
        self._ready = False

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None and self._ready

    def _validate_executable(self) -> Path:
        '''Verify llama-server executable exists.'''
        server_path = self._settings.llamacpp_server_path
        if not os.path.isabs(server_path):
            found = shutil.which(server_path)
            if found:
                return Path(found)
            raise LlamaCppServerNotFoundError(
                f'llama-server executable not found in PATH: {server_path}'
            )
        path = Path(server_path)
        if not path.exists():
            raise LlamaCppServerNotFoundError(
                f'llama-server executable not found at: {server_path}'
            )
        return path

    def _validate_model(self) -> Path:
        '''Verify GGUF model file exists.'''
        model_path = Path(self._settings.llamacpp_model_path)
        if not model_path.exists():
            raise LlamaCppModelNotFoundError(
                f'GGUF model not found at: {model_path}'
            )
        return model_path

    def _build_command(self, executable: Path, model: Path) -> list[str]:
        '''Build llama-server command line.'''
        s = self._settings
        cmd = [
            str(executable),
            '--model', str(model),
            '--host', s.llamacpp_host,
            '--port', str(s.llamacpp_port),
            '--ctx-size', str(s.llamacpp_ctx_size),
        ]
        if s.llamacpp_n_gpu_layers >= 0:
            cmd.extend(['--n-gpu-layers', str(s.llamacpp_n_gpu_layers)])
        if s.llamacpp_threads > 0:
            cmd.extend(['--threads', str(s.llamacpp_threads)])
        return cmd

    async def start(self) -> str:
        '''Start llama-server subprocess and wait for readiness.'''
        if self.is_running:
            return self._base_url

        executable = self._validate_executable()
        model = self._validate_model()

        self._base_url = f'http://{self._settings.llamacpp_host}:{self._settings.llamacpp_port}/v1'
        cmd = self._build_command(executable, model)

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )

        start_time = time.time()
        timeout = self._settings.llamacpp_startup_timeout
        health_timeout = self._settings.llamacpp_health_check_timeout

        while time.time() - start_time < timeout:
            if self._process.poll() is not None:
                stdout, stderr = self._process.communicate()
                stdout_str = stdout.decode() if stdout else ''
                stderr_str = stderr.decode() if stderr else ''
                raise LlamaCppServerStartupError(
                    f'llama-server exited unexpectedly with code {self._process.returncode}. '
                    f'stdout: {stdout_str}, stderr: {stderr_str}'
                )

            try:
                async with httpx.AsyncClient(timeout=health_timeout) as client:
                    resp = await client.get(f'{self._base_url}/models')
                    if resp.status_code == 200:
                        self._ready = True
                        return self._base_url
            except Exception:
                pass

            await asyncio.sleep(0.5)

        self.stop()
        raise LlamaCppServerStartupError(
            f'llama-server did not become ready within {timeout} seconds'
        )

    def stop(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=2)
            except Exception:
                pass
        self._process = None
        self._ready = False
        self._base_url = ''

    async def health_check(self) -> bool:
        if not self.is_running:
            return False
        try:
            async with httpx.AsyncClient(timeout=self._settings.llamacpp_health_check_timeout) as client:
                resp = await client.get(f'{self._base_url}/models')
                return resp.status_code == 200
        except Exception:
            return False

    def get_diagnostics(self) -> dict:
        return {
            'running': self.is_running,
            'base_url': self._base_url,
            'pid': self._process.pid if self._process else None,
            'exit_code': self._process.poll() if self._process else None,
            'executable': self._settings.llamacpp_server_path,
            'model': self._settings.llamacpp_model_path,
            'host': self._settings.llamacpp_host,
            'port': self._settings.llamacpp_port,
        }
