from dataclasses import dataclass
from typing import Optional, Dict, Any, List, AsyncGenerator
import json
import asyncio

from app.config import get_settings
from app.integrations.ai.providers import (
    AIProvider,
    LocalAIProvider,
    CloudAIProvider,
    AIMessage,
    AIResponse,
    ToolDefinition,
)
from app.core.conversation import ConversationManager, AIProviderFactory
from app.core.intent_router import IntentRouter, Intent, IntentType
from app.core.permissions import PermissionManager
from app.core.action_executor import ActionExecutor, ActionResult
from app.voice.speech_input import SpeechInput, SpeechResult
from app.voice.speech_output import VoiceOutput
from app.monitoring.system_monitor import SystemMonitor
from app.integrations.ai.llamacpp_server import LlamaCppServerManager
from app.storage.repositories import (
    ConversationRepository,
    ActionLogRepository,
    EmailAccountRepository,
    EmailMessageRepository,
    EmailDraftRepository,
    ReminderRepository,
    NoteRepository,
    ApplicationShortcutRepository,
    SettingRepository,
    SystemAlertRepository,
)
from app.storage.database import get_database_manager, init_database_async
from app.models import AIProviderType


@dataclass
class OrchestratorResponse:
    text: str
    intent: Intent
    action_result: Optional[ActionResult] = None
    spoken: bool = False
    provider: str = ''
    model: str = ''


class JARVISOrchestrator:
    def __init__(self):
        self._settings = get_settings()
        self._db_manager = None
        self._conversation_manager = None
        self._ai_factory = AIProviderFactory()
        self._intent_router = IntentRouter()
        self._permissions = PermissionManager()
        self._system_monitor = None
        self._voice_input = SpeechInput()
        self._voice_output = VoiceOutput()
        self._action_executor = None
        self._running = False
        self._status = 'idle'
        self._current_session_id = None
        self._llamacpp_server: Optional[LlamaCppServerManager] = None

    async def initialize(self):
        # Start llama.cpp server if enabled
        settings = get_settings()
        if settings.ai_provider == 'llamacpp' or settings.llamacpp_enabled:
            self._llamacpp_server = LlamaCppServerManager()
            await self._llamacpp_server.start()

        await init_database_async()
        self._db_manager = get_database_manager()

        session = self._db_manager.async_session_factory()
        try:
            conversation_repo = ConversationRepository(session)
            action_repo = ActionLogRepository(session)
            email_account_repo = EmailAccountRepository(session)
            email_message_repo = EmailMessageRepository(session)
            email_draft_repo = EmailDraftRepository(session)
            reminder_repo = ReminderRepository(session)
            note_repo = NoteRepository(session)
            app_shortcut_repo = ApplicationShortcutRepository(session)
            setting_repo = SettingRepository(session)
            alert_repo = SystemAlertRepository(session)

            self._conversation_manager = ConversationManager(conversation_repo, action_repo)
            self._system_monitor = SystemMonitor(
                refresh_interval=self._settings.monitor_refresh_interval,
                process_interval=self._settings.process_refresh_interval,
                network_interval=self._settings.network_refresh_interval,
            )
            self._action_executor = ActionExecutor(
                system_monitor=self._system_monitor,
                permission_manager=self._permissions,
                voice_output=self._voice_output,
                email_account_repo=email_account_repo,
                email_message_repo=email_message_repo,
                email_draft_repo=email_draft_repo,
                reminder_repo=reminder_repo,
                note_repo=note_repo,
                app_shortcut_repo=app_shortcut_repo,
                setting_repo=setting_repo,
                alert_repo=alert_repo,
            )

            await self._system_monitor.take_snapshot()
            self._running = True
        finally:
            await session.close()

    @property
    def status(self) -> str:
        return self._status

    @property
    def system_monitor(self) -> SystemMonitor:
        return self._system_monitor

    @property
    def voice_input(self) -> SpeechInput:
        return self._voice_input

    @property
    def voice_output(self) -> VoiceOutput:
        return self._voice_output

    @property
    def permissions(self) -> PermissionManager:
        return self._permissions

    async def process_text(self, text: str, speak_response: bool = True) -> OrchestratorResponse:
        self._status = 'thinking'

        intent = self._intent_router.classify(text)

        provider_type = self._settings.ai_provider
        provider = self._ai_factory.get_provider(provider_type)

        context_messages = await self._conversation_manager.get_context_messages(limit=10)

        system_prompt = self._build_system_prompt()
        messages = [{'role': 'system', 'content': system_prompt}] + context_messages + [{'role': 'user', 'content': text}]

        response = await provider.complete(
            messages=[AIMessage(role=m['role'] if isinstance(m, dict) else m.role, content=m['content'] if isinstance(m, dict) else m.content) for m in messages],
            tools=self._get_tool_definitions(),
        )

        assistant_text = response.message.content or ''

        if response.message.tool_calls:
            for tool_call in response.message.tool_calls:
                action_result = await self._execute_tool_call(tool_call)
                if action_result:
                    assistant_text += f'\n\n[Action Result: {action_result.result}]'

        await self._conversation_manager.add_exchange(
            user_message=text,
            assistant_response=assistant_text,
            ai_provider=AIProviderType(provider_type),
            model_used=response.model,
            tokens_used=response.usage.get('total_tokens') if response.usage else None,
        )

        spoken = False
        if speak_response and assistant_text:
            self._status = 'speaking'
            spoken = await self._voice_output.speak(assistant_text)

        self._status = 'idle'
        return OrchestratorResponse(
            text=assistant_text,
            intent=intent,
            spoken=spoken,
            provider=response.provider,
            model=response.model,
        )

    async def process_voice(self, speak_response: bool = True) -> Optional[OrchestratorResponse]:
        self._status = 'listening'
        speech_result = await self._voice_input.listen_once()

        if not speech_result.text:
            self._status = 'idle'
            return None

        self._status = 'thinking'
        return await self.process_text(speech_result.text, speak_response)

    def _build_system_prompt(self) -> str:
        return '''You are JARVIS, a personal AI assistant for a Windows computer. You help the user with system monitoring, email, reminders, notes, file search, and application control.

You have access to tools for:
- Getting system status (CPU, memory, disk, battery, network)
- Listing running processes
- Managing emails (list, search, draft, send)
- Launching approved applications
- Creating and managing reminders
- Creating and searching notes
- Searching files in approved directories
- Getting and setting configuration

Always be helpful, concise, and professional. Use tools when appropriate. Ask for confirmation before taking sensitive actions.'''

    def _get_tool_definitions(self) -> List[Dict]:
        return [
            {
                'name': 'get_system_status',
                'description': 'Get overall system health and status',
                'parameters': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'list_processes',
                'description': 'List running processes by CPU/memory usage',
                'parameters': {'type': 'object', 'properties': {'limit': {'type': 'integer', 'default': 20}}},
            },
            {
                'name': 'get_disk_status',
                'description': 'Get disk usage for all drives',
                'parameters': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'get_network_status',
                'description': 'Get network connectivity and interface info',
                'parameters': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'get_battery_status',
                'description': 'Get battery level and status',
                'parameters': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'list_emails',
                'description': 'List recent emails',
                'parameters': {'type': 'object', 'properties': {'limit': {'type': 'integer', 'default': 20}, 'unread_only': {'type': 'boolean', 'default': False}}},
            },
            {
                'name': 'search_emails',
                'description': 'Search emails by query or sender',
                'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}, 'sender': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 20}}},
            },
            {
                'name': 'draft_email',
                'description': 'Create an email draft',
                'parameters': {'type': 'object', 'properties': {'account_id': {'type': 'integer'}, 'to': {'type': 'string'}, 'subject': {'type': 'string'}, 'body': {'type': 'string'}, 'cc': {'type': 'string'}, 'bcc': {'type': 'string'}}, 'required': ['account_id', 'to', 'subject', 'body']},
            },
            {
                'name': 'send_email',
                'description': 'Send a prepared email draft',
                'parameters': {'type': 'object', 'properties': {'draft_id': {'type': 'integer'}}, 'required': ['draft_id']},
            },
            {
                'name': 'launch_application',
                'description': 'Launch an approved application',
                'parameters': {'type': 'object', 'properties': {'application': {'type': 'string'}}, 'required': ['application']},
            },
            {
                'name': 'terminate_process',
                'description': 'Terminate a process by PID or name',
                'parameters': {'type': 'object', 'properties': {'pid': {'type': 'integer'}, 'name': {'type': 'string'}}},
            },
            {
                'name': 'create_reminder',
                'description': 'Create a new reminder',
                'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'due_at': {'type': 'string'}, 'description': {'type': 'string'}}, 'required': ['title', 'due_at']},
            },
            {
                'name': 'list_reminders',
                'description': 'List reminders',
                'parameters': {'type': 'object', 'properties': {'include_completed': {'type': 'boolean', 'default': False}}},
            },
            {
                'name': 'complete_reminder',
                'description': 'Mark reminder as complete',
                'parameters': {'type': 'object', 'properties': {'id': {'type': 'integer'}}, 'required': ['id']},
            },
            {
                'name': 'create_note',
                'description': 'Create a new note',
                'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'content': {'type': 'string'}, 'tags': {'type': 'string'}}, 'required': ['title', 'content']},
            },
            {
                'name': 'list_notes',
                'description': 'List notes',
                'parameters': {'type': 'object', 'properties': {'search': {'type': 'string'}}},
            },
            {
                'name': 'search_files',
                'description': 'Search for files in approved directories',
                'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
            },
        ]

    async def _execute_tool_call(self, tool_call: Dict) -> Optional[ActionResult]:
        try:
            function_name = tool_call['function']['name']
            arguments = json.loads(tool_call['function']['arguments'])

            action_map = {
                'get_system_status': 'system_status',
                'list_processes': 'process_list',
                'get_disk_status': 'disk_status',
                'get_network_status': 'network_status',
                'get_battery_status': 'battery_status',
                'list_emails': 'email_list',
                'search_emails': 'email_search',
                'draft_email': 'email_draft',
                'send_email': 'email_send',
                'launch_application': 'app_launch',
                'terminate_process': 'app_terminate',
                'create_reminder': 'reminder_create',
                'list_reminders': 'reminder_list',
                'complete_reminder': 'reminder_complete',
                'create_note': 'note_create',
                'list_notes': 'note_list',
                'search_files': 'file_search',
            }

            action_type = action_map.get(function_name)
            if not action_type:
                return None

            return await self._action_executor.execute(action_type, arguments)
        except Exception as e:
            return ActionResult(success=False, error=str(e))

    async def stop_speaking(self):
        self._voice_output.stop_speaking()

    async def shutdown(self):
        self._running = False
        if self._system_monitor:
            await self._system_monitor.stop()
        self._voice_output.cleanup()
        await self._ai_factory.close_all()
        if self._llamacpp_server:
            self._llamacpp_server.stop()
        if self._db_manager:
            self._db_manager.close()

    async def start_monitoring(self):
        if self._system_monitor:
            asyncio.create_task(self._system_monitor.start())
