import asyncio
import os
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from app.core.permissions import PermissionManager, PermissionLevel, ResourceType, PermissionResult
from app.monitoring.system_monitor import SystemMonitor
from app.storage.repositories import (
    EmailAccountRepository,
    EmailMessageRepository,
    EmailDraftRepository,
    ReminderRepository,
    NoteRepository,
    ApplicationShortcutRepository,
    SettingRepository,
    SystemAlertRepository,
)
from app.models import EmailAccount, EmailMessage, EmailDraft, Reminder, Note, ApplicationShortcut
from app.voice.speech_output import VoiceOutput


@dataclass
class ActionResult:
    success: bool
    result: Any = None
    error: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None


class ActionExecutor:
    def __init__(
        self,
        system_monitor: SystemMonitor,
        permission_manager: PermissionManager,
        voice_output: VoiceOutput,
        email_account_repo: EmailAccountRepository,
        email_message_repo: EmailMessageRepository,
        email_draft_repo: EmailDraftRepository,
        reminder_repo: ReminderRepository,
        note_repo: NoteRepository,
        app_shortcut_repo: ApplicationShortcutRepository,
        setting_repo: SettingRepository,
        alert_repo: SystemAlertRepository,
    ):
        self._system_monitor = system_monitor
        self._permissions = permission_manager
        self._voice = voice_output
        self._email_account_repo = email_account_repo
        self._email_message_repo = email_message_repo
        self._email_draft_repo = email_draft_repo
        self._reminder_repo = reminder_repo
        self._note_repo = note_repo
        self._app_shortcut_repo = app_shortcut_repo
        self._setting_repo = setting_repo
        self._alert_repo = alert_repo

        self._confirmation_callback: Optional[Callable] = None
        self._pending_confirmations: Dict[int, asyncio.Future] = {}

    def set_confirmation_callback(self, callback: Callable[[str, dict], asyncio.Future]):
        self._confirmation_callback = callback

    async def execute(self, action_type: str, params: Dict[str, Any]) -> ActionResult:
        method_name = f"_execute_{action_type}"
        if not hasattr(self, method_name):
            return ActionResult(success=False, error=f"Unknown action: {action_type}")

        method = getattr(self, method_name)
        return await method(params)

    async def _execute_system_status(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SYSTEM, "read_status")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        snapshot = self._system_monitor.get_latest()
        if not snapshot:
            return ActionResult(success=False, error="No system data available")

        result = {
            "cpu": {"percent": snapshot.cpu.percent, "cores": snapshot.cpu.count_logical},
            "memory": {"percent": snapshot.memory.percent, "used_gb": snapshot.memory.used / (1024**3), "total_gb": snapshot.memory.total / (1024**3)},
            "disks": [{"mount": d.mountpoint, "percent": d.percent, "free_gb": d.free / (1024**3)} for d in snapshot.disks],
            "battery": {"percent": snapshot.battery.percent, "plugged": snapshot.battery.power_plugged} if snapshot.battery else None,
            "network": {"connected": snapshot.network.internet_connected, "interfaces": len(snapshot.network.interfaces)},
            "uptime_hours": snapshot.system.uptime_seconds / 3600,
            "alerts": snapshot.alerts,
        }
        return ActionResult(success=True, result=result)

    async def _execute_process_list(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SYSTEM, "read_processes")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        snapshot = self._system_monitor.get_latest()
        if not snapshot:
            return ActionResult(success=False, error="No process data available")

        limit = params.get("limit", 20)
        processes = snapshot.processes[:limit]
        result = [
            {
                "pid": p.pid,
                "name": p.name,
                "cpu_percent": p.cpu_percent,
                "memory_percent": p.memory_percent,
                "memory_mb": p.memory_rss / (1024**2),
                "status": p.status,
            }
            for p in processes
        ]
        return ActionResult(success=True, result=result)

    async def _execute_disk_status(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SYSTEM, "read_status")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        snapshot = self._system_monitor.get_latest()
        if not snapshot:
            return ActionResult(success=False, error="No disk data available")

        result = [
            {
                "device": d.device,
                "mountpoint": d.mountpoint,
                "total_gb": d.total / (1024**3),
                "used_gb": d.used / (1024**3),
                "free_gb": d.free / (1024**3),
                "percent": d.percent,
            }
            for d in snapshot.disks
        ]
        return ActionResult(success=True, result=result)

    async def _execute_network_status(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SYSTEM, "read_status")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        snapshot = self._system_monitor.get_latest()
        if not snapshot:
            return ActionResult(success=False, error="No network data available")

        result = {
            "internet_connected": snapshot.network.internet_connected,
            "interfaces": [
                {
                    "name": i.name,
                    "up": i.is_up,
                    "ipv4": i.ipv4_address,
                    "bytes_sent_mb": i.bytes_sent / (1024**2),
                    "bytes_recv_mb": i.bytes_recv / (1024**2),
                }
                for i in snapshot.network.interfaces
            ],
        }
        return ActionResult(success=True, result=result)

    async def _execute_battery_status(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SYSTEM, "read_status")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        snapshot = self._system_monitor.get_latest()
        if not snapshot or not snapshot.battery:
            return ActionResult(success=False, error="No battery information available")

        battery = snapshot.battery
        result = {
            "percent": battery.percent,
            "power_plugged": battery.power_plugged,
            "status": battery.status,
            "time_left_minutes": battery.time_left // 60 if battery.time_left else None,
        }
        return ActionResult(success=True, result=result)

    async def _execute_email_list(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.EMAIL, "read")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        accounts = await self._email_account_repo.get_active()
        if not accounts:
            return ActionResult(success=False, error="No email accounts connected")

        account_id = params.get("account_id")
        limit = params.get("limit", 20)
        unread_only = params.get("unread_only", False)

        all_messages = []
        for account in accounts:
            if account_id and account.id != account_id:
                continue
            messages = await self._email_message_repo.get_by_account(
                account.id, limit=limit, unread_only=unread_only
            )
            for msg in messages:
                all_messages.append({
                    "id": msg.id,
                    "account": account.email_address,
                    "sender": msg.sender,
                    "sender_email": msg.sender_email,
                    "subject": msg.subject,
                    "snippet": msg.snippet,
                    "is_read": msg.is_read,
                    "has_attachments": msg.has_attachments,
                    "received_at": msg.received_at.isoformat(),
                })

        all_messages.sort(key=lambda m: m["received_at"], reverse=True)
        return ActionResult(success=True, result=all_messages[:limit])

    async def _execute_email_search(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.EMAIL, "search")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        accounts = await self._email_account_repo.get_active()
        query = params.get("query", "")
        sender = params.get("sender", "")
        limit = params.get("limit", 20)

        all_messages = []
        for account in accounts:
            messages = await self._email_message_repo.get_by_account(
                account.id, limit=limit, search_query=query
            )
            if sender:
                messages = [m for m in messages if sender.lower() in m.sender_email.lower()]

            for msg in messages:
                all_messages.append({
                    "id": msg.id,
                    "account": account.email_address,
                    "sender": msg.sender,
                    "sender_email": msg.sender_email,
                    "subject": msg.subject,
                    "snippet": msg.snippet,
                    "is_read": msg.is_read,
                    "has_attachments": msg.has_attachments,
                    "received_at": msg.received_at.isoformat(),
                })

        all_messages.sort(key=lambda m: m["received_at"], reverse=True)
        return ActionResult(success=True, result=all_messages[:limit])

    async def _execute_email_draft(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.EMAIL, "draft")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        account_id = params.get("account_id")
        to_recipients = params.get("to", "")
        subject = params.get("subject", "")
        body = params.get("body", "")
        cc = params.get("cc")
        bcc = params.get("bcc")

        if not account_id or not to_recipients or not subject:
            return ActionResult(success=False, error="Missing required fields: account_id, to, subject")

        draft = await self._email_draft_repo.create(
            account_id=account_id,
            to_recipients=to_recipients,
            subject=subject,
            body_text=body,
            cc_recipients=cc,
            bcc_recipients=bcc,
        )
        return ActionResult(success=True, result={"draft_id": draft.id, "message": "Draft created"})

    async def _execute_email_send(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.EMAIL, "send")
        if not perm.allowed:
            return ActionResult(
                success=False,
                error=perm.reason,
                requires_confirmation=perm.requires_confirmation,
                confirmation_prompt="Send this email?",
            )

        draft_id = params.get("draft_id")
        if not draft_id:
            return ActionResult(success=False, error="Draft ID required")

        draft = await self._email_draft_repo.mark_sent(draft_id)
        if not draft:
            return ActionResult(success=False, error="Draft not found")

        return ActionResult(success=True, result={"message": "Email queued for sending"})

    async def _execute_app_launch(self, params: Dict) -> ActionResult:
        app_name = params.get("application", "").lower()
        if not app_name:
            return ActionResult(success=False, error="Application name required")

        perm = self._permissions.check_permission(
            ResourceType.APPLICATION, "launch", {"application": app_name}
        )
        if not perm.allowed:
            return ActionResult(
                success=False,
                error=perm.reason,
                requires_confirmation=perm.requires_confirmation,
                confirmation_prompt=f"Launch {app_name}?",
            )

        shortcuts = await self._app_shortcut_repo.get_approved()
        shortcut = next((s for s in shortcuts if s.name.lower() == app_name), None)

        if not shortcut:
            from app.config import get_settings
            settings = get_settings()
            if app_name in settings.approved_apps_list:
                try:
                    subprocess.Popen([app_name], shell=True)
                    return ActionResult(success=True, result={"message": f"Launched {app_name}"})
                except Exception as e:
                    return ActionResult(success=False, error=f"Failed to launch: {e}")
            return ActionResult(success=False, error=f"Application not approved: {app_name}")

        try:
            cmd = [shortcut.executable_path]
            if shortcut.arguments:
                cmd.extend(shortcut.arguments.split())
            cwd = shortcut.working_directory or None
            subprocess.Popen(cmd, cwd=cwd, shell=False)

            await self._app_shortcut_repo.record_launch(shortcut.id)
            return ActionResult(success=True, result={"message": f"Launched {shortcut.name}"})
        except Exception as e:
            return ActionResult(success=False, error=f"Failed to launch: {e}")

    async def _execute_app_terminate(self, params: Dict) -> ActionResult:
        pid = params.get("pid")
        name = params.get("name", "")

        if not pid and not name:
            return ActionResult(success=False, error="PID or process name required")

        perm = self._permissions.check_permission(
            ResourceType.APPLICATION, "terminate", {"process": name}
        )
        if not perm.allowed:
            return ActionResult(
                success=False,
                error=perm.reason,
                requires_confirmation=perm.requires_confirmation,
                confirmation_prompt=f"Terminate process {name or pid}?",
            )

        try:
            if pid:
                proc = psutil.Process(pid)
                proc_name = proc.name()
                proc.terminate()
                proc.wait(timeout=5)
            else:
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'] and proc.info['name'].lower() == name.lower():
                        proc.terminate()
                        proc.wait(timeout=5)
                        break
            return ActionResult(success=True, result={"message": f"Terminated {name or pid}"})
        except psutil.NoSuchProcess:
            return ActionResult(success=False, error="Process not found")
        except psutil.AccessDenied:
            return ActionResult(success=False, error="Access denied - insufficient permissions")
        except Exception as e:
            return ActionResult(success=False, error=f"Failed to terminate: {e}")

    async def _execute_reminder_create(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.REMINDER, "create")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        title = params.get("title", "")
        due_at_str = params.get("due_at", "")
        description = params.get("description")

        if not title or not due_at_str:
            return ActionResult(success=False, error="Title and due_at required")

        try:
            due_at = datetime.fromisoformat(due_at_str)
        except ValueError:
            return ActionResult(success=False, error="Invalid due_at format (use ISO format)")

        reminder = await self._reminder_repo.create(
            title=title,
            due_at=due_at,
            description=description,
        )
        return ActionResult(success=True, result={"id": reminder.id, "message": "Reminder created"})

    async def _execute_reminder_list(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.REMINDER, "read")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        include_completed = params.get("include_completed", False)
        reminders = await self._reminder_repo.get_all(include_completed=include_completed)
        result = [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "due_at": r.due_at.isoformat(),
                "completed": r.is_completed,
            }
            for r in reminders
        ]
        return ActionResult(success=True, result=result)

    async def _execute_reminder_complete(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.REMINDER, "update")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        reminder_id = params.get("id")
        if not reminder_id:
            return ActionResult(success=False, error="Reminder ID required")

        reminder = await self._reminder_repo.complete(reminder_id)
        if not reminder:
            return ActionResult(success=False, error="Reminder not found")

        return ActionResult(success=True, result={"message": "Reminder completed"})

    async def _execute_note_create(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.NOTE, "create")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        title = params.get("title", "")
        content = params.get("content", "")
        tags = params.get("tags")

        if not title or not content:
            return ActionResult(success=False, error="Title and content required")

        note = await self._note_repo.create(title=title, content=content, tags=tags)
        return ActionResult(success=True, result={"id": note.id, "message": "Note created"})

    async def _execute_note_list(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.NOTE, "read")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        search = params.get("search")
        notes = await self._note_repo.get_all(search_query=search)
        result = [
            {
                "id": n.id,
                "title": n.title,
                "content": n.content[:200] + "..." if len(n.content) > 200 else n.content,
                "tags": n.tags,
                "pinned": n.is_pinned,
                "updated_at": n.updated_at.isoformat(),
            }
            for n in notes
        ]
        return ActionResult(success=True, result=result)

    async def _execute_file_search(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(
            ResourceType.FILE, "search", {"path": params.get("path", "")}
        )
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        query = params.get("query", "")
        if not query:
            return ActionResult(success=False, error="Search query required")

        from app.config import get_settings
        settings = get_settings()
        search_dirs = settings.search_dirs_list
        exclude_dirs = settings.exclude_dirs_list

        results = []
        for search_dir in search_dirs:
            try:
                for file_path in search_dir.rglob("*"):
                    if file_path.is_file():
                        if any(str(file_path).startswith(str(d)) for d in exclude_dirs):
                            continue
                        if query.lower() in file_path.name.lower():
                            stat = file_path.stat()
                            results.append({
                                "path": str(file_path),
                                "name": file_path.name,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            })
                            if len(results) >= 50:
                                break
            except (PermissionError, OSError):
                continue

        return ActionResult(success=True, result=results)

    async def _execute_setting_get(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SETTING, "read")
        if not perm.allowed:
            return ActionResult(success=False, error=perm.reason)

        key = params.get("key")
        if not key:
            return ActionResult(success=False, error="Setting key required")

        value = await self._setting_repo.get(key)
        if value is None:
            return ActionResult(success=False, error="Setting not found")

        return ActionResult(success=True, result={"key": key, "value": value})

    async def _execute_setting_set(self, params: Dict) -> ActionResult:
        perm = self._permissions.check_permission(ResourceType.SETTING, "write")
        if not perm.allowed:
            return ActionResult(
                success=False,
                error=perm.reason,
                requires_confirmation=perm.requires_confirmation,
                confirmation_prompt=f"Change setting {params.get('key')}?",
            )

        key = params.get("key")
        value = params.get("value")
        if not key:
            return ActionResult(success=False, error="Setting key required")

        await self._setting_repo.set(key, str(value))
        return ActionResult(success=True, result={"message": f"Setting {key} updated"})

    async def _execute_stop_speaking(self, params: Dict) -> ActionResult:
        self._voice.stop_speaking()
        return ActionResult(success=True, result={"message": "Speech stopped"})

    async def _execute_cancel_action(self, params: Dict) -> ActionResult:
        return ActionResult(success=True, result={"message": "Action cancelled"})

    async def _execute_help(self, params: Dict) -> ActionResult:
        from app.core.intent_router import IntentRouter
        router = IntentRouter()
        intents = router.get_supported_intents()
        return ActionResult(success=True, result={"intents": intents})


import psutil