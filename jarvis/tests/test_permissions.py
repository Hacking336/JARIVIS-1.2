import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.core.permissions import (
    PermissionManager,
    PermissionLevel,
    ResourceType,
    PermissionResult,
    PermissionRule,
)
from app.core.action_executor import ActionExecutor, ActionResult


class TestPermissionManager:
    @pytest.fixture
    def manager(self):
        return PermissionManager()

    def test_initialization(self, manager):
        assert len(manager._rules) > 0
        assert len(manager._blocked_processes) > 0

    def test_system_read_status_allowed(self, manager):
        result = manager.check_permission(ResourceType.SYSTEM, "read_status")
        assert result.allowed is True
        assert result.level == PermissionLevel.ALLOW
        assert result.requires_confirmation is False

    def test_system_read_processes_allowed(self, manager):
        result = manager.check_permission(ResourceType.SYSTEM, "read_processes")
        assert result.allowed is True
        assert result.level == PermissionLevel.ALLOW

    def test_system_terminate_process_requires_confirmation(self, manager):
        result = manager.check_permission(
            ResourceType.SYSTEM, "terminate_process",
            {"process": "notepad.exe"}
        )
        assert result.allowed is True
        assert result.level == PermissionLevel.CONFIRM
        assert result.requires_confirmation is True

    def test_system_terminate_blocked_process_denied(self, manager):
        result = manager.check_permission(
            ResourceType.SYSTEM, "terminate_process",
            {"process": "lsass"}
        )
        assert result.allowed is False
        assert result.level == PermissionLevel.DENY

    def test_email_read_allowed(self, manager):
        result = manager.check_permission(ResourceType.EMAIL, "read")
        assert result.allowed is True

    def test_email_search_allowed(self, manager):
        result = manager.check_permission(ResourceType.EMAIL, "search")
        assert result.allowed is True

    def test_email_draft_allowed(self, manager):
        result = manager.check_permission(ResourceType.EMAIL, "draft")
        assert result.allowed is True

    def test_email_send_requires_confirmation(self, manager):
        result = manager.check_permission(ResourceType.EMAIL, "send")
        assert result.allowed is True
        assert result.requires_confirmation is True

    def test_application_launch_approved(self, manager):
        manager.add_approved_app("notepad.exe")
        result = manager.check_permission(
            ResourceType.APPLICATION, "launch",
            {"application": "notepad.exe"}
        )
        assert result.allowed is True

    def test_application_launch_unapproved_denied(self, manager):
        result = manager.check_permission(
            ResourceType.APPLICATION, "launch",
            {"application": "malware.exe"}
        )
        assert result.allowed is False

    def test_application_terminate_requires_confirmation(self, manager):
        result = manager.check_permission(ResourceType.APPLICATION, "terminate")
        assert result.allowed is True
        assert result.requires_confirmation is True

    def test_file_search_allowed(self, manager):
        manager.add_approved_directory("C:\\Users\\test")
        result = manager.check_permission(
            ResourceType.FILE, "search",
            {"path": "C:\\Users\\test\\documents"}
        )
        assert result.allowed is True

    def test_file_search_unapproved_denied(self, manager):
        result = manager.check_permission(
            ResourceType.FILE, "search",
            {"path": "C:\\Windows\\System32"}
        )
        assert result.allowed is False

    def test_file_delete_denied(self, manager):
        result = manager.check_permission(ResourceType.FILE, "delete")
        assert result.allowed is False
        assert result.level == PermissionLevel.DENY

    def test_setting_read_allowed(self, manager):
        result = manager.check_permission(ResourceType.SETTING, "read")
        assert result.allowed is True

    def test_setting_write_requires_confirmation(self, manager):
        result = manager.check_permission(ResourceType.SETTING, "write")
        assert result.allowed is True
        assert result.requires_confirmation is True

    def test_reminder_create_allowed(self, manager):
        result = manager.check_permission(ResourceType.REMINDER, "create")
        assert result.allowed is True

    def test_reminder_read_allowed(self, manager):
        result = manager.check_permission(ResourceType.REMINDER, "read")
        assert result.allowed is True

    def test_reminder_update_allowed(self, manager):
        result = manager.check_permission(ResourceType.REMINDER, "update")
        assert result.allowed is True

    def test_reminder_delete_allowed(self, manager):
        result = manager.check_permission(ResourceType.REMINDER, "delete")
        assert result.allowed is True

    def test_note_create_allowed(self, manager):
        result = manager.check_permission(ResourceType.NOTE, "create")
        assert result.allowed is True

    def test_note_read_allowed(self, manager):
        result = manager.check_permission(ResourceType.NOTE, "read")
        assert result.allowed is True

    def test_note_update_allowed(self, manager):
        result = manager.check_permission(ResourceType.NOTE, "update")
        assert result.allowed is True

    def test_note_delete_allowed(self, manager):
        result = manager.check_permission(ResourceType.NOTE, "delete")
        assert result.allowed is True

    def test_unknown_action_denied(self, manager):
        result = manager.check_permission(ResourceType.SYSTEM, "unknown_action")
        assert result.allowed is False
        assert result.level == PermissionLevel.DENY

    def test_add_approved_app(self, manager):
        manager.add_approved_app("test.exe")
        assert "test.exe" in manager.get_approved_apps()

    def test_remove_approved_app(self, manager):
        manager.add_approved_app("test.exe")
        manager.remove_approved_app("test.exe")
        assert "test.exe" not in manager.get_approved_apps()

    def test_add_approved_directory(self, manager):
        manager.add_approved_directory("C:\\Test")
        assert "C:\\Test" in manager.get_approved_directories()

    def test_remove_approved_directory(self, manager):
        manager.add_approved_directory("C:\\Test")
        manager.remove_approved_directory("C:\\Test")
        assert "C:\\Test" not in manager.get_approved_directories()

    def test_add_blocked_process(self, manager):
        manager.add_blocked_process("test.exe")
        assert "test.exe" in manager.get_blocked_processes()

    def test_add_custom_rule(self, manager):
        rule = PermissionRule(
            resource_type=ResourceType.SYSTEM,
            action="custom_action",
            level=PermissionLevel.ALLOW,
        )
        manager.add_custom_rule(rule)
        result = manager.check_permission(ResourceType.SYSTEM, "custom_action")
        assert result.allowed is True

    def test_remove_rule(self, manager):
        manager.remove_rule(ResourceType.SYSTEM, "read_status")
        result = manager.check_permission(ResourceType.SYSTEM, "read_status")
        assert result.allowed is False

    def test_export_policy(self, manager):
        policy = manager.export_policy()
        assert isinstance(policy, str)
        import json
        data = json.loads(policy)
        assert "approved_apps" in data
        assert "approved_directories" in data
        assert "blocked_processes" in data
        assert "rules" in data

    def test_import_policy(self, manager):
        policy = manager.export_policy()
        new_manager = PermissionManager()
        new_manager.import_policy(policy)
        assert new_manager.get_approved_apps() == manager.get_approved_apps()
        assert new_manager.get_blocked_processes() == manager.get_blocked_processes()

    def test_permission_result_dataclass(self):
        result = PermissionResult(
            allowed=True,
            level=PermissionLevel.ALLOW,
            reason="Test reason",
            requires_confirmation=False,
        )
        assert result.allowed is True
        assert result.level == PermissionLevel.ALLOW
        assert result.reason == "Test reason"
        assert result.requires_confirmation is False

    def test_permission_rule_dataclass(self):
        rule = PermissionRule(
            resource_type=ResourceType.SYSTEM,
            action="test_action",
            level=PermissionLevel.CONFIRM,
            conditions={"key": "value"},
        )
        assert rule.resource_type == ResourceType.SYSTEM
        assert rule.action == "test_action"
        assert rule.level == PermissionLevel.CONFIRM
        assert rule.conditions == {"key": "value"}


class TestActionExecutor:
    @pytest.fixture
    def executor(self):
        system_monitor = Mock()
        system_monitor.get_latest = Mock(return_value=None)

        permission_manager = PermissionManager()
        voice_output = Mock()
        voice_output.stop_speaking = Mock()

        email_account_repo = Mock()
        email_message_repo = Mock()
        email_draft_repo = Mock()
        reminder_repo = Mock()
        note_repo = Mock()
        app_shortcut_repo = Mock()
        setting_repo = Mock()
        alert_repo = Mock()

        return ActionExecutor(
            system_monitor=system_monitor,
            permission_manager=permission_manager,
            voice_output=voice_output,
            email_account_repo=email_account_repo,
            email_message_repo=email_message_repo,
            email_draft_repo=email_draft_repo,
            reminder_repo=reminder_repo,
            note_repo=note_repo,
            app_shortcut_repo=app_shortcut_repo,
            setting_repo=setting_repo,
            alert_repo=alert_repo,
        )

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, executor):
        result = await executor.execute("unknown_action", {})
        assert result.success is False
        assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_execute_system_status_no_data(self, executor):
        result = await executor.execute("system_status", {})
        assert result.success is False
        assert "No system data available" in result.error

    @pytest.mark.asyncio
    async def test_execute_process_list_no_data(self, executor):
        result = await executor.execute("process_list", {})
        assert result.success is False
        assert "No process data available" in result.error

    @pytest.mark.asyncio
    async def test_execute_disk_status_no_data(self, executor):
        result = await executor.execute("disk_status", {})
        assert result.success is False
        assert "No disk data available" in result.error

    @pytest.mark.asyncio
    async def test_execute_network_status_no_data(self, executor):
        result = await executor.execute("network_status", {})
        assert result.success is False
        assert "No network data available" in result.error

    @pytest.mark.asyncio
    async def test_execute_battery_status_no_data(self, executor):
        result = await executor.execute("battery_status", {})
        assert result.success is False
        assert "No battery information available" in result.error

    @pytest.mark.asyncio
    async def test_execute_email_list_no_accounts(self, executor):
        executor._email_account_repo.get_active = AsyncMock(return_value=[])
        result = await executor.execute("email_list", {})
        assert result.success is False
        assert "No email accounts connected" in result.error

    @pytest.mark.asyncio
    async def test_execute_email_draft_missing_fields(self, executor):
        result = await executor.execute("email_draft", {})
        assert result.success is False
        assert "Missing required fields" in result.error

    @pytest.mark.asyncio
    async def test_execute_email_send_missing_draft_id(self, executor):
        result = await executor.execute("email_send", {})
        assert result.success is False
        assert "Draft ID required" in result.error

    @pytest.mark.asyncio
    async def test_execute_app_launch_missing_name(self, executor):
        result = await executor.execute("app_launch", {})
        assert result.success is False
        assert "Application name required" in result.error

    @pytest.mark.asyncio
    async def test_execute_app_launch_unapproved(self, executor):
        result = await executor.execute("app_launch", {"application": "malware.exe"})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_app_terminate_missing_params(self, executor):
        result = await executor.execute("app_terminate", {})
        assert result.success is False
        assert "PID or process name required" in result.error

    @pytest.mark.asyncio
    async def test_execute_reminder_create_missing_fields(self, executor):
        result = await executor.execute("reminder_create", {})
        assert result.success is False
        assert "Title and due_at required" in result.error

    @pytest.mark.asyncio
    async def test_execute_reminder_create_invalid_date(self, executor):
        result = await executor.execute("reminder_create", {
            "title": "Test",
            "due_at": "invalid-date"
        })
        assert result.success is False
        assert "Invalid due_at format" in result.error

    @pytest.mark.asyncio
    async def test_execute_reminder_complete_missing_id(self, executor):
        result = await executor.execute("reminder_complete", {})
        assert result.success is False
        assert "Reminder ID required" in result.error

    @pytest.mark.asyncio
    async def test_execute_note_create_missing_fields(self, executor):
        result = await executor.execute("note_create", {})
        assert result.success is False
        assert "Title and content required" in result.error

    @pytest.mark.asyncio
    async def test_execute_file_search_missing_query(self, executor):
        result = await executor.execute("file_search", {})
        assert result.success is False
        assert "Search query required" in result.error

    @pytest.mark.asyncio
    async def test_execute_setting_get_missing_key(self, executor):
        result = await executor.execute("setting_get", {})
        assert result.success is False
        assert "Setting key required" in result.error

    @pytest.mark.asyncio
    async def test_execute_setting_set_missing_key(self, executor):
        result = await executor.execute("setting_set", {})
        assert result.success is False
        assert "Setting key required" in result.error

    @pytest.mark.asyncio
    async def test_execute_stop_speaking(self, executor):
        result = await executor.execute("stop_speaking", {})
        assert result.success is True
        executor._voice.stop_speaking.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_cancel_action(self, executor):
        result = await executor.execute("cancel_action", {})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_help(self, executor):
        result = await executor.execute("help", {})
        assert result.success is True
        assert "intents" in result.result

    @pytest.mark.asyncio
    async def test_execute_system_status_with_data(self, executor):
        from app.monitoring.system_monitor import SystemSnapshot, CPUMetrics, MemoryMetrics, NetworkMetrics, SystemInfo
        from datetime import datetime

        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=CPUMetrics(percent=50.0, per_cpu=[50.0], count_logical=4, count_physical=2),
            memory=MemoryMetrics(total=16*1024**3, available=8*1024**3, used=8*1024**3, percent=50.0, swap_total=0, swap_used=0, swap_percent=0.0),
            disks=[],
            battery=None,
            network=NetworkMetrics(interfaces=[], internet_connected=True),
            processes=[],
            system=SystemInfo(
                hostname="TEST", platform="Windows", platform_version="10",
                architecture="AMD64", processor="Intel",
                boot_time=datetime.now(), uptime_seconds=3600, python_version="3.11"
            ),
        )
        executor._system_monitor.get_latest = Mock(return_value=snapshot)

        result = await executor.execute("system_status", {})
        assert result.success is True
        assert result.result["cpu"]["percent"] == 50.0
        assert result.result["memory"]["percent"] == 50.0

    @pytest.mark.asyncio
    async def test_execute_process_list_with_data(self, executor):
        from app.monitoring.system_monitor import SystemSnapshot, CPUMetrics, MemoryMetrics, NetworkMetrics, SystemInfo, ProcessInfo
        from datetime import datetime

        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=CPUMetrics(percent=50.0, per_cpu=[50.0], count_logical=4, count_physical=2),
            memory=MemoryMetrics(total=16*1024**3, available=8*1024**3, used=8*1024**3, percent=50.0, swap_total=0, swap_used=0, swap_percent=0.0),
            disks=[],
            battery=None,
            network=NetworkMetrics(interfaces=[], internet_connected=True),
            processes=[
                ProcessInfo(
                    pid=1234, name="notepad.exe", username="user",
                    cpu_percent=5.5, memory_percent=2.0,
                    memory_rss=50*1024**2, memory_vms=100*1024**2,
                    status="running", create_time=datetime.now(),
                    exe="C:\\Windows\\notepad.exe", cmdline=["notepad.exe"], num_threads=2
                )
            ],
            system=SystemInfo(
                hostname="TEST", platform="Windows", platform_version="10",
                architecture="AMD64", processor="Intel",
                boot_time=datetime.now(), uptime_seconds=3600, python_version="3.11"
            ),
        )
        executor._system_monitor.get_latest = Mock(return_value=snapshot)

        result = await executor.execute("process_list", {"limit": 10})
        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["name"] == "notepad.exe"

    @pytest.mark.asyncio
    async def test_execute_email_list_with_accounts(self, executor):
        from app.models import EmailAccount, EmailProvider
        from datetime import datetime

        account = EmailAccount(
            id=1, provider=EmailProvider.GMAIL,
            email_address="test@example.com",
            display_name="Test User",
            access_token_encrypted="encrypted",
            refresh_token_encrypted=None,
            token_expires_at=None,
            scopes="read",
            is_active=True,
            last_sync_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        executor._email_account_repo.get_active = AsyncMock(return_value=[account])
        executor._email_message_repo.get_by_account = AsyncMock(return_value=[])

        result = await executor.execute("email_list", {})
        assert result.success is True
        assert result.result == []

    @pytest.mark.asyncio
    async def test_execute_reminder_list(self, executor):
        from app.models import Reminder
        from datetime import datetime

        reminder = Reminder(
            id=1, title="Test Reminder", description=None,
            due_at=datetime.now(), is_completed=False,
            is_recurring=False, recurrence_rule=None,
            notify_before_minutes=0, notified=False,
            created_at=datetime.now(), completed_at=None,
        )
        executor._reminder_repo.get_all = AsyncMock(return_value=[reminder])

        result = await executor.execute("reminder_list", {})
        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["title"] == "Test Reminder"

    @pytest.mark.asyncio
    async def test_execute_note_list(self, executor):
        from app.models import Note
        from datetime import datetime

        note = Note(
            id=1, title="Test Note", content="Test content",
            tags=None, is_pinned=False,
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        executor._note_repo.get_all = AsyncMock(return_value=[note])

        result = await executor.execute("note_list", {})
        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["title"] == "Test Note"

    @pytest.mark.asyncio
    async def test_execute_setting_get(self, executor):
        executor._setting_repo.get = AsyncMock(return_value="test-value")

        result = await executor.execute("setting_get", {"key": "test_key"})
        assert result.success is True
        assert result.result["value"] == "test-value"

    @pytest.mark.asyncio
    async def test_execute_setting_get_not_found(self, executor):
        executor._setting_repo.get = AsyncMock(return_value=None)

        result = await executor.execute("setting_get", {"key": "nonexistent"})
        assert result.success is False
        assert "Setting not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_setting_set(self, executor):
        executor._setting_repo.set = AsyncMock(return_value=Mock())

        result = await executor.execute("setting_set", {"key": "test_key", "value": "test_value"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_app_launch_approved(self, executor):
        executor._permissions.add_approved_app("notepad.exe")
        executor._app_shortcut_repo.get_approved = AsyncMock(return_value=[])
        from app.config import get_settings
        with patch('app.config.get_settings') as mock_settings:
            settings = Mock()
            settings.approved_apps_list = ["notepad.exe"]
            mock_settings.return_value = settings

            with patch('subprocess.Popen') as mock_popen:
                result = await executor.execute("app_launch", {"application": "notepad.exe"})
                assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_app_terminate_by_pid(self, executor):
        mock_proc = Mock()
        mock_proc.name = Mock(return_value="notepad.exe")
        mock_proc.terminate = Mock()
        mock_proc.wait = Mock()

        with patch('psutil.Process', return_value=mock_proc):
            result = await executor.execute("app_terminate", {"pid": 1234})
            assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_app_terminate_process_not_found(self, executor):
        with patch('psutil.Process', side_effect=Exception("Process not found")):
            result = await executor.execute("app_terminate", {"pid": 99999})
            assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_app_terminate_access_denied(self, executor):
        with patch('psutil.Process', side_effect=PermissionError("Access denied")):
            result = await executor.execute("app_terminate", {"pid": 1234})
            assert result.success is False
            assert "Access denied" in result.error

    @pytest.mark.asyncio
    async def test_execute_email_draft_success(self, executor):
        from app.models import EmailDraft
        from datetime import datetime

        draft = EmailDraft(
            id=1, account_id=1, to_recipients="test@example.com",
            cc_recipients=None, bcc_recipients=None,
            subject="Test Subject", body_text="Test body",
            body_html=None, reply_to_message_id=None,
            is_sent=False, sent_at=None,
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        executor._email_draft_repo.create = AsyncMock(return_value=draft)

        result = await executor.execute("email_draft", {
            "account_id": 1,
            "to": "test@example.com",
            "subject": "Test Subject",
            "body": "Test body",
        })
        assert result.success is True
        assert result.result["draft_id"] == 1

    @pytest.mark.asyncio
    async def test_execute_reminder_create_success(self, executor):
        from app.models import Reminder
        from datetime import datetime

        reminder = Reminder(
            id=1, title="Test Reminder", description=None,
            due_at=datetime.now(), is_completed=False,
            is_recurring=False, recurrence_rule=None,
            notify_before_minutes=0, notified=False,
            created_at=datetime.now(), completed_at=None,
        )
        executor._reminder_repo.create = AsyncMock(return_value=reminder)

        result = await executor.execute("reminder_create", {
            "title": "Test Reminder",
            "due_at": datetime.now().isoformat(),
        })
        assert result.success is True
        assert result.result["id"] == 1

    @pytest.mark.asyncio
    async def test_execute_note_create_success(self, executor):
        from app.models import Note
        from datetime import datetime

        note = Note(
            id=1, title="Test Note", content="Test content",
            tags=None, is_pinned=False,
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        executor._note_repo.create = AsyncMock(return_value=note)

        result = await executor.execute("note_create", {
            "title": "Test Note",
            "content": "Test content",
        })
        assert result.success is True
        assert result.result["id"] == 1

    @pytest.mark.asyncio
    async def test_execute_reminder_complete_success(self, executor):
        from app.models import Reminder
        from datetime import datetime

        reminder = Reminder(
            id=1, title="Test Reminder", description=None,
            due_at=datetime.now(), is_completed=False,
            is_recurring=False, recurrence_rule=None,
            notify_before_minutes=0, notified=False,
            created_at=datetime.now(), completed_at=None,
        )
        executor._reminder_repo.complete = AsyncMock(return_value=reminder)

        result = await executor.execute("reminder_complete", {"id": 1})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_reminder_complete_not_found(self, executor):
        executor._reminder_repo.complete = AsyncMock(return_value=None)

        result = await executor.execute("reminder_complete", {"id": 999})
        assert result.success is False
        assert "Reminder not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_email_send_success(self, executor):
        from app.models import EmailDraft
        from datetime import datetime

        draft = EmailDraft(
            id=1, account_id=1, to_recipients="test@example.com",
            cc_recipients=None, bcc_recipients=None,
            subject="Test Subject", body_text="Test body",
            body_html=None, reply_to_message_id=None,
            is_sent=True, sent_at=datetime.now(),
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        executor._email_draft_repo.mark_sent = AsyncMock(return_value=draft)

        result = await executor.execute("email_send", {"draft_id": 1})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_email_send_not_found(self, executor):
        executor._email_draft_repo.mark_sent = AsyncMock(return_value=None)

        result = await executor.execute("email_send", {"draft_id": 999})
        assert result.success is False
        assert "Draft not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_file_search(self, executor):
        with patch('app.config.get_settings') as mock_settings:
            settings = Mock()
            settings.search_dirs_list = []
            settings.exclude_dirs_list = []
            mock_settings.return_value = settings

            result = await executor.execute("file_search", {"query": "test"})
            assert result.success is True
            assert result.result == []

    @pytest.mark.asyncio
    async def test_execute_email_search(self, executor):
        from app.models import EmailAccount, EmailProvider
        from datetime import datetime

        account = EmailAccount(
            id=1, provider=EmailProvider.GMAIL,
            email_address="test@example.com",
            display_name="Test User",
            access_token_encrypted="encrypted",
            refresh_token_encrypted=None,
            token_expires_at=None,
            scopes="read",
            is_active=True,
            last_sync_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        executor._email_account_repo.get_active = AsyncMock(return_value=[account])
        executor._email_message_repo.get_by_account = AsyncMock(return_value=[])

        result = await executor.execute("email_search", {"query": "test"})
        assert result.success is True
        assert result.result == []

    @pytest.mark.asyncio
    async def test_execute_disk_status_with_data(self, executor):
        from app.monitoring.system_monitor import SystemSnapshot, CPUMetrics, MemoryMetrics, NetworkMetrics, SystemInfo, DiskMetrics
        from datetime import datetime

        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=CPUMetrics(percent=50.0, per_cpu=[50.0], count_logical=4, count_physical=2),
            memory=MemoryMetrics(total=16*1024**3, available=8*1024**3, used=8*1024**3, percent=50.0, swap_total=0, swap_used=0, swap_percent=0.0),
            disks=[
                DiskMetrics(
                    device="C:", mountpoint="C:\\", fstype="NTFS",
                    total=500*1024**3, used=250*1024**3, free=250*1024**3, percent=50.0
                )
            ],
            battery=None,
            network=NetworkMetrics(interfaces=[], internet_connected=True),
            processes=[],
            system=SystemInfo(
                hostname="TEST", platform="Windows", platform_version="10",
                architecture="AMD64", processor="Intel",
                boot_time=datetime.now(), uptime_seconds=3600, python_version="3.11"
            ),
        )
        executor._system_monitor.get_latest = Mock(return_value=snapshot)

        result = await executor.execute("disk_status", {})
        assert result.success is True
        assert len(result.result) == 1
        assert result.result[0]["device"] == "C:"

    @pytest.mark.asyncio
    async def test_execute_network_status_with_data(self, executor):
        from app.monitoring.system_monitor import SystemSnapshot, CPUMetrics, MemoryMetrics, NetworkMetrics, SystemInfo, NetworkInterface
        from datetime import datetime

        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=CPUMetrics(percent=50.0, per_cpu=[50.0], count_logical=4, count_physical=2),
            memory=MemoryMetrics(total=16*1024**3, available=8*1024**3, used=8*1024**3, percent=50.0, swap_total=0, swap_used=0, swap_percent=0.0),
            disks=[],
            battery=None,
            network=NetworkMetrics(
                interfaces=[
                    NetworkInterface(
                        name="Ethernet", is_up=True, speed=1000, mtu=1500,
                        ipv4_address="192.168.1.100", mac_address="AA:BB:CC:DD:EE:FF",
                        bytes_sent=1000000, bytes_recv=5000000
                    )
                ],
                internet_connected=True
            ),
            processes=[],
            system=SystemInfo(
                hostname="TEST", platform="Windows", platform_version="10",
                architecture="AMD64", processor="Intel",
                boot_time=datetime.now(), uptime_seconds=3600, python_version="3.11"
            ),
        )
        executor._system_monitor.get_latest = Mock(return_value=snapshot)

        result = await executor.execute("network_status", {})
        assert result.success is True
        assert result.result["internet_connected"] is True
        assert len(result.result["interfaces"]) == 1

    @pytest.mark.asyncio
    async def test_execute_battery_status_with_data(self, executor):
        from app.monitoring.system_monitor import SystemSnapshot, CPUMetrics, MemoryMetrics, NetworkMetrics, SystemInfo, BatteryMetrics
        from datetime import datetime

        snapshot = SystemSnapshot(
            timestamp=datetime.now(),
            cpu=CPUMetrics(percent=50.0, per_cpu=[50.0], count_logical=4, count_physical=2),
            memory=MemoryMetrics(total=16*1024**3, available=8*1024**3, used=8*1024**3, percent=50.0, swap_total=0, swap_used=0, swap_percent=0.0),
            disks=[],
            battery=BatteryMetrics(
                percent=75.0, power_plugged=False, time_left=7200, status="discharging"
            ),
            network=NetworkMetrics(interfaces=[], internet_connected=True),
            processes=[],
            system=SystemInfo(
                hostname="TEST", platform="Windows", platform_version="10",
                architecture="AMD64", processor="Intel",
                boot_time=datetime.now(), uptime_seconds=3600, python_version="3.11"
            ),
        )
        executor._system_monitor.get_latest = Mock(return_value=snapshot)

        result = await executor.execute("battery_status", {})
        assert result.success is True
        assert result.result["percent"] == 75.0
        assert result.result["power_plugged"] is False
        assert result.result["status"] == "discharging"


class TestActionResult:
    def test_result_creation(self):
        result = ActionResult(success=True, result={"data": "test"})
        assert result.success is True
        assert result.result == {"data": "test"}
        assert result.error is None
        assert result.requires_confirmation is False

    def test_result_failure(self):
        result = ActionResult(success=False, error="Test error")
        assert result.success is False
        assert result.error == "Test error"
        assert result.result is None

    def test_result_with_confirmation(self):
        result = ActionResult(
            success=False,
            error="Requires confirmation",
            requires_confirmation=True,
            confirmation_prompt="Are you sure?",
        )
        assert result.requires_confirmation is True
        assert result.confirmation_prompt == "Are you sure?"