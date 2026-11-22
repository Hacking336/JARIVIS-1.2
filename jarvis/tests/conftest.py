import pytest
import asyncio
from unittest.mock import Mock, patch
import os

# Set required environment variables before any imports
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-testing-only-12345")
os.environ.setdefault("FISH_AUDIO_API_KEY", "")
os.environ.setdefault("CLOUD_AI_API_KEY", "")


@pytest.fixture(autouse=True)
def mock_settings():
    from app.config import get_settings
    get_settings.cache_clear()
    with patch('app.config.get_settings') as mock_config, \
         patch('app.voice.fish_audio.get_settings') as mock_fish, \
         patch('app.core.orchestrator.get_settings') as mock_orchestrator, \
         patch('app.api.routes.get_settings') as mock_routes, \
         patch('app.main.get_settings') as mock_main, \
         patch('app.storage.database.get_settings') as mock_db:
        settings = Mock()
        settings.app_host = "127.0.0.1"
        settings.app_port = 8080
        settings.app_debug = False
        settings.app_secret_key = "test-secret-key-for-testing-only-12345"
        settings.ai_provider = "local"
        settings.local_ai_base_url = "http://localhost:11434/v1"
        settings.local_ai_model = "llama3.2:3b"
        settings.local_ai_api_key = "not-required"
        settings.cloud_ai_api_key = None
        settings.cloud_ai_model = "gpt-4o-mini"
        settings.cloud_ai_base_url = None
        settings.fish_audio_api_key = None
        settings.fish_audio_voice_model_id = "14129c3e320149449d6bada6862f7338"
        settings.fish_audio_base_url = "https://api.fish.audio"
        settings.fish_audio_speed = 1.0
        settings.fish_audio_sample_rate = 44100
        settings.gmail_client_id = None
        settings.gmail_client_secret = None
        settings.gmail_redirect_uri = "http://localhost:8080/auth/gmail/callback"
        settings.outlook_client_id = None
        settings.outlook_client_secret = None
        settings.outlook_redirect_uri = "http://localhost:8080/auth/outlook/callback"
        settings.outlook_tenant_id = "common"
        settings.speech_provider = "local"
        settings.speech_language = "en-US"
        settings.speech_timeout = 5
        settings.speech_phrase_timeout = 3
        settings.vosk_model_path = None
        settings.monitor_refresh_interval = 2
        settings.process_refresh_interval = 5
        settings.network_refresh_interval = 3
        settings.enable_gpu_monitoring = False
        settings.database_url = "sqlite:///./data/test_jarvis.db"
        settings.credentials_encryption_key = None
        settings.session_timeout = 3600
        settings.max_failed_attempts = 5
        settings.enable_desktop_notifications = True
        settings.notification_sound = True
        settings.search_directories = "C:\\Users\\,C:\\Projects\\"
        settings.exclude_directories = "C:\\Windows\\,C:\\Program Files\\"
        settings.approved_applications = "notepad.exe,calc.exe,code.exe"
        settings.search_dirs_list = []
        settings.exclude_dirs_list = []
        settings.approved_apps_list = ["notepad.exe", "calc.exe", "code.exe"]
        mock_config.return_value = settings
        mock_fish.return_value = settings
        mock_orchestrator.return_value = settings
        mock_routes.return_value = settings
        mock_main.return_value = settings
        mock_db.return_value = settings
        yield settings
        get_settings.cache_clear()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_system_snapshot():
    from app.monitoring.system_monitor import (
        SystemSnapshot, CPUMetrics, MemoryMetrics, DiskMetrics,
        BatteryMetrics, NetworkMetrics, NetworkInterface, ProcessInfo, SystemInfo
    )
    from datetime import datetime

    return SystemSnapshot(
        timestamp=datetime.now(),
        cpu=CPUMetrics(
            percent=50.0,
            per_cpu=[50.0, 50.0, 50.0, 50.0],
            count_logical=4,
            count_physical=2,
            freq_current=3500.0,
            freq_min=800.0,
            freq_max=4000.0,
            load_avg_1m=1.5,
            load_avg_5m=2.0,
            load_avg_15m=1.8,
        ),
        memory=MemoryMetrics(
            total=16 * 1024**3,
            available=8 * 1024**3,
            used=8 * 1024**3,
            percent=50.0,
            swap_total=8 * 1024**3,
            swap_used=0,
            swap_percent=0.0,
        ),
        disks=[
            DiskMetrics(
                device="C:",
                mountpoint="C:\\",
                fstype="NTFS",
                total=500 * 1024**3,
                used=250 * 1024**3,
                free=250 * 1024**3,
                percent=50.0,
            )
        ],
        battery=BatteryMetrics(
            percent=75.0,
            power_plugged=False,
            time_left=7200,
            status="discharging",
        ),
        network=NetworkMetrics(
            interfaces=[
                NetworkInterface(
                    name="Ethernet",
                    is_up=True,
                    speed=1000,
                    mtu=1500,
                    ipv4_address="192.168.1.100",
                    ipv6_address=None,
                    mac_address="AA:BB:CC:DD:EE:FF",
                    bytes_sent=1000000,
                    bytes_recv=5000000,
                    packets_sent=1000,
                    packets_recv=5000,
                    errin=0,
                    errout=0,
                    dropin=0,
                    dropout=0,
                )
            ],
            total_bytes_sent=1000000,
            total_bytes_recv=5000000,
            internet_connected=True,
        ),
        processes=[
            ProcessInfo(
                pid=1234,
                name="notepad.exe",
                username="user",
                cpu_percent=5.5,
                memory_percent=2.0,
                memory_rss=50 * 1024**2,
                memory_vms=100 * 1024**2,
                status="running",
                create_time=datetime.now(),
                exe="C:\\Windows\\notepad.exe",
                cmdline=["notepad.exe"],
                num_threads=2,
            )
        ],
        system=SystemInfo(
            hostname="TEST-PC",
            platform="Windows",
            platform_version="10.0",
            architecture="AMD64",
            processor="Intel",
            boot_time=datetime.now(),
            uptime_seconds=3600,
            python_version="3.11.0",
        ),
        alerts=[],
    )


@pytest.fixture
def mock_email_account():
    from app.models import EmailAccount, EmailProvider
    from datetime import datetime

    return EmailAccount(
        id=1,
        provider=EmailProvider.GMAIL,
        email_address="test@example.com",
        display_name="Test User",
        access_token_encrypted="encrypted-token",
        refresh_token_encrypted="encrypted-refresh",
        token_expires_at=datetime.now(),
        scopes="https://www.googleapis.com/auth/gmail.readonly",
        is_active=True,
        last_sync_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_email_message():
    from app.models import EmailMessage
    from datetime import datetime

    return EmailMessage(
        id=1,
        account_id=1,
        message_id="msg-123",
        thread_id="thread-123",
        sender="John Doe",
        sender_email="john@example.com",
        recipients="test@example.com",
        subject="Test Email",
        snippet="This is a test email",
        body_text="This is the full body of the test email",
        body_html="<p>This is the full body of the test email</p>",
        is_read=False,
        is_starred=False,
        has_attachments=False,
        received_at=datetime.now(),
        created_at=datetime.now(),
    )


@pytest.fixture
def mock_reminder():
    from app.models import Reminder
    from datetime import datetime, timedelta

    return Reminder(
        id=1,
        title="Test Reminder",
        description="Test description",
        due_at=datetime.now() + timedelta(hours=1),
        is_completed=False,
        is_recurring=False,
        recurrence_rule=None,
        notify_before_minutes=15,
        notified=False,
        created_at=datetime.now(),
        completed_at=None,
    )


@pytest.fixture
def mock_note():
    from app.models import Note
    from datetime import datetime

    return Note(
        id=1,
        title="Test Note",
        content="Test content",
        tags="test,example",
        is_pinned=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_application_shortcut():
    from app.models import ApplicationShortcut
    from datetime import datetime

    return ApplicationShortcut(
        id=1,
        name="Notepad",
        executable_path="C:\\Windows\\notepad.exe",
        arguments=None,
        working_directory=None,
        icon_path=None,
        is_approved=True,
        launch_count=5,
        last_launched_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_system_alert():
    from app.models import SystemAlert
    from datetime import datetime

    return SystemAlert(
        id=1,
        alert_type="cpu",
        severity="warning",
        title="High CPU Usage",
        message="CPU usage is above 80%",
        source="system_monitor",
        metric_value=85.0,
        threshold_value=80.0,
        is_acknowledged=False,
        is_resolved=False,
        created_at=datetime.now(),
        acknowledged_at=None,
        resolved_at=None,
    )


@pytest.fixture
def mock_conversation():
    from app.models import Conversation, AIProviderType
    from datetime import datetime

    return Conversation(
        id=1,
        session_id="test-session",
        user_message="Hello",
        assistant_response="Hi there",
        ai_provider=AIProviderType.LOCAL,
        model_used="llama3.2:3b",
        tokens_used=100,
        created_at=datetime.now(),
    )


@pytest.fixture
def mock_action_log():
    from app.models import ActionLog, ActionStatus
    from datetime import datetime

    return ActionLog(
        id=1,
        conversation_id=1,
        action_type="system_status",
        action_params="{}",
        status=ActionStatus.COMPLETED,
        result="Success",
        error=None,
        requires_confirmation=False,
        confirmed_by_user=False,
        created_at=datetime.now(),
        completed_at=datetime.now(),
    )