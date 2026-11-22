from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import (
    get_base_path,
    get_database_path,
    get_llama_server_path,
    get_model_path,
    get_vosk_model_path,
    get_data_dir,
    get_log_dir,
    get_voice_cache_dir,
    get_webengine_cache_dir,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Application
    app_host: str = '127.0.0.1'
    app_port: int = 3000
    app_debug: bool = False
    app_secret_key: str = Field(default_factory=lambda: __import__('secrets').token_urlsafe(32))

    # AI Provider
    ai_provider: str = 'llamacpp'
    local_ai_base_url: str = 'http://localhost:11434/v1'
    local_ai_model: str = 'llama3.2:3b'
    local_ai_api_key: str = 'not-required'
    cloud_ai_api_key: Optional[str] = None
    cloud_ai_model: str = 'gpt-4o-mini'
    cloud_ai_base_url: Optional[str] = None

    # llama.cpp Server (local inference without Ollama)
    llamacpp_enabled: bool = True
    llamacpp_server_path: str = Field(default_factory=lambda: str(get_llama_server_path()))
    llamacpp_model_path: str = Field(default_factory=lambda: str(get_model_path()))
    llamacpp_host: str = '127.0.0.1'
    llamacpp_port: int = 8081
    llamacpp_ctx_size: int = 4096
    llamacpp_n_gpu_layers: int = -1
    llamacpp_threads: int = 0
    llamacpp_startup_timeout: int = 60
    llamacpp_health_check_timeout: int = 5

    # Fish Audio TTS
    fish_audio_api_key: Optional[str] = None
    fish_audio_voice_model_id: str = '14129c3e320149449d6bada6862f7338'
    fish_audio_base_url: str = 'https://api.fish.audio'
    fish_audio_speed: float = 1.0
    fish_audio_sample_rate: int = 44100

    # Email - Gmail
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_redirect_uri: str = 'http://127.0.0.1:3000/auth/gmail/callback'

    # Email - Outlook
    outlook_client_id: Optional[str] = None
    outlook_client_secret: Optional[str] = None
    outlook_redirect_uri: str = 'http://127.0.0.1:3000/auth/outlook/callback'
    outlook_tenant_id: str = 'common'

    # Speech Recognition
    speech_provider: str = 'vosk'
    speech_language: str = 'en-US'
    speech_timeout: int = 5
    speech_phrase_timeout: int = 3
    vosk_model_path: str = Field(default_factory=lambda: str(get_vosk_model_path()))

    # System Monitoring
    monitor_refresh_interval: int = 2
    process_refresh_interval: int = 5
    network_refresh_interval: int = 3
    enable_gpu_monitoring: bool = False

    # Database
    database_url: str = Field(default_factory=get_database_path)

    # Security
    credentials_encryption_key: Optional[str] = None
    session_timeout: int = 3600
    max_failed_attempts: int = 5

    # Notifications
    enable_desktop_notifications: bool = True
    notification_sound: bool = True

    # File Search
    search_directories: str = 'C:\\\\Users\\\\,C:\\\\Projects\\\\'
    exclude_directories: str = 'C:\\\\Windows\\\\,C:\\\\Program Files\\\\,C:\\\\Program Files (x86)\\\\C:\\\\.Bin\\\\,C:\\\\System Volume Information\\\\'

    # Approved Applications
    approved_applications: str = 'notepad.exe,calc.exe,code.exe,chrome.exe,firefox.exe,explorer.exe'

    @property
    def search_dirs_list(self) -> List[Path]:
        return [Path(d.strip()) for d in self.search_directories.split(',') if d.strip()]

    @property
    def exclude_dirs_list(self) -> List[Path]:
        return [Path(d.strip()) for d in self.exclude_directories.split(',') if d.strip()]

    @property
    def approved_apps_list(self) -> List[str]:
        return [app.strip().lower() for app in self.approved_applications.split(',') if app.strip()]

    @field_validator('fish_audio_speed')
    @classmethod
    def validate_speed(cls, v: float) -> float:
        if not 0.5 <= v <= 2.0:
            raise ValueError('Fish Audio speed must be between 0.5 and 2.0')
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
