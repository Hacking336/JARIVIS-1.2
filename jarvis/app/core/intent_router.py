from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import re


class IntentType(str, Enum):
    SYSTEM_STATUS = "system_status"
    PROCESS_LIST = "process_list"
    DISK_STATUS = "disk_status"
    NETWORK_STATUS = "network_status"
    BATTERY_STATUS = "battery_status"
    EMAIL_LIST = "email_list"
    EMAIL_SEARCH = "email_search"
    EMAIL_DRAFT = "email_draft"
    EMAIL_SEND = "email_send"
    APP_LAUNCH = "app_launch"
    APP_TERMINATE = "app_terminate"
    REMINDER_CREATE = "reminder_create"
    REMINDER_LIST = "reminder_list"
    REMINDER_COMPLETE = "reminder_complete"
    NOTE_CREATE = "note_create"
    NOTE_LIST = "note_list"
    NOTE_SEARCH = "note_search"
    FILE_SEARCH = "file_search"
    SETTING_GET = "setting_get"
    SETTING_SET = "setting_set"
    HELP = "help"
    STOP_SPEAKING = "stop_speaking"
    CANCEL_ACTION = "cancel_action"
    GENERAL_QUERY = "general_query"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    type: IntentType
    confidence: float
    entities: Dict[str, Any]
    raw_text: str
    requires_confirmation: bool = False


class IntentRouter:
    def __init__(self):
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> List[tuple]:
        return [
            (IntentType.SYSTEM_STATUS, [
                r"(system|computer|pc|machine).*(status|health|report|overview)",
                r"(status|health|report|overview).*(system|computer|pc|machine)",
                r"(how is|what is|show me).*(system|computer|pc|machine)",
                r"system status",
                r"status report",
                r"health report",
            ], {"requires_confirmation": False}),

            (IntentType.PROCESS_LIST, [
                r"(process|task|program|application).*(list|show|running|using)",
                r"(top|most).*(cpu|memory|ram).*(process|task|program)",
                r"(what|which).*(process|program|app).*(using|consuming|eating)",
            ], {"requires_confirmation": False}),

            (IntentType.DISK_STATUS, [
                r"(disk|drive|storage|space).*(status|usage|free|available)",
                r"(how much|show).*(disk|drive|storage|space)",
            ], {"requires_confirmation": False}),

            (IntentType.NETWORK_STATUS, [
                r"(network|internet|connection|wifi|ethernet).*(status|working|connected|speed)",
                r"(is|check).*(internet|network|connection)",
            ], {"requires_confirmation": False}),

            (IntentType.BATTERY_STATUS, [
                r"(battery|power).*(status|level|percent|remaining|time)",
                r"(how much|show).*(battery|power)",
            ], {"requires_confirmation": False}),

            (IntentType.EMAIL_LIST, [
                r"(email|mail|inbox|message).*(list|show|unread|recent|latest)",
                r"(check|show|read).*(email|mail|inbox|message)",
            ], {"requires_confirmation": False}),

            (IntentType.EMAIL_SEARCH, [
                r"(find|search|look for).*(email|mail|message).*(from|subject|about)",
                r"(email|mail|message).*(from|by|about|regarding)",
            ], {"requires_confirmation": False}),

            (IntentType.EMAIL_DRAFT, [
                r"(draft|write|compose|create).*(email|mail|message|reply)",
                r"(reply|respond).*(to|email|mail|message)",
            ], {"requires_confirmation": True}),

            (IntentType.EMAIL_SEND, [
                r"(send|mail).*(email|mail|message)",
            ], {"requires_confirmation": True}),

            (IntentType.APP_LAUNCH, [
                r"(open|launch|start|run).*(notepad|calculator|code|chrome|firefox|explorer|app|application|program)",
                r"(open|launch|start).*(the|my)?\s*(\w+)",
            ], {"requires_confirmation": False}),

            (IntentType.APP_TERMINATE, [
                r"(close|kill|terminate|stop|end).*(process|program|app|application|task)",
            ], {"requires_confirmation": True}),

            (IntentType.REMINDER_CREATE, [
                r"(remind|reminder|alert|notify).*(me|to|about|at|in|on|for)",
                r"(create|set|add).*(reminder|alert)",
            ], {"requires_confirmation": False}),

            (IntentType.REMINDER_LIST, [
                r"(show|list|what).*(reminder|reminders)",
            ], {"requires_confirmation": False}),

            (IntentType.REMINDER_COMPLETE, [
                r"(complete|done|finish|remove|delete).*(reminder|reminders)",
            ], {"requires_confirmation": False}),

            (IntentType.NOTE_CREATE, [
                r"(note|write down|save|remember).*(that|this|note|about)",
                r"(create|make|add).*(note|memo)",
                r"write.*note",
                r"note.*about",
            ], {"requires_confirmation": False}),

            (IntentType.NOTE_LIST, [
                r"(show|list|what).*(note|notes|memo)",
            ], {"requires_confirmation": False}),

            (IntentType.NOTE_SEARCH, [
                r"(find|search).*(note|notes|memo).*(about|for|with)",
            ], {"requires_confirmation": False}),

            (IntentType.FILE_SEARCH, [
                r"(find|search|locate|look for).*(file|files|document|documents|folder|folders)",
                r"(find|search|locate|look for).*named",
                r"find.*files",
                r"search.*files",
            ], {"requires_confirmation": False}),

            (IntentType.SETTING_GET, [
                r"(what is|show|get).*(setting|config|configuration)",
            ], {"requires_confirmation": False}),

            (IntentType.SETTING_SET, [
                r"(set|change|update|configure).*(setting|config|configuration)",
            ], {"requires_confirmation": True}),

            (IntentType.STOP_SPEAKING, [
                r"(stop|halt|pause|quiet|silence).*(speak|talk|voice|audio)",
                r"(shut up|be quiet)",
            ], {"requires_confirmation": False}),

            (IntentType.CANCEL_ACTION, [
                r"(cancel|abort|stop).*(action|operation|task|that|it)",
                r"(never mind|forget it)",
            ], {"requires_confirmation": False}),

            (IntentType.HELP, [
                r"(help|what can you do|commands|capabilities|features)",
            ], {"requires_confirmation": False}),
        ]

    def classify(self, text: str) -> Intent:
        text_lower = text.lower()
        best_match = IntentType.UNKNOWN
        best_confidence = 0.0
        best_entities = {}

        for intent_type, patterns, meta in self._patterns:
            confidence = 0.0
            matched_patterns = 0

            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    matched_patterns += 1
                    confidence += 0.3

            if matched_patterns > 0:
                confidence = min(confidence + (matched_patterns * 0.1), 1.0)

                entities = self._extract_entities(intent_type, text_lower)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = intent_type
                    best_entities = entities

        return Intent(
            type=best_match,
            confidence=best_confidence,
            entities=best_entities,
            raw_text=text,
            requires_confirmation=self._get_confirmation_requirement(best_match),
        )

    def _extract_entities(self, intent_type: IntentType, text: str) -> Dict[str, Any]:
        entities = {}

        if intent_type == IntentType.APP_LAUNCH:
            apps = ["notepad", "calculator", "calc", "code", "vscode", "chrome", "firefox", "explorer", "cmd", "powershell"]
            for app in apps:
                if app in text:
                    entities["application"] = app
                    break

        elif intent_type == IntentType.EMAIL_SEARCH:
            from_match = re.search(r"from\s+(\S+)", text)
            if from_match:
                entities["sender"] = from_match.group(1)
            subject_match = re.search(r"(subject|about|regarding)\s+(.+?)(?:\s+(?:from|to|in|on|at|yesterday|today|tomorrow)|$)", text)
            if subject_match:
                entities["subject"] = subject_match.group(2).strip()

        elif intent_type == IntentType.REMINDER_CREATE:
            time_patterns = [
                r"(in|after)\s+(\d+)\s*(minute|hour|day|week)s?",
                r"(at|on)\s+(\d{1,2}:\d{2}|\d{1,2}\s*(am|pm))",
                r"(tomorrow|today|next week|next month)",
            ]
            for pattern in time_patterns:
                match = re.search(pattern, text)
                if match:
                    entities["time_expression"] = match.group(0)
                    break

        elif intent_type == IntentType.FILE_SEARCH:
            query_match = re.search(r"(find|search|locate|look for)\s+(.+?)(?:\s+(?:in|on|at|under)|$)", text)
            if query_match:
                entities["query"] = query_match.group(2).strip()

        return entities

    def _get_confirmation_requirement(self, intent_type: IntentType) -> bool:
        for it, _, meta in self._patterns:
            if it == intent_type:
                return meta.get("requires_confirmation", False)
        return False

    def get_supported_intents(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": it.value,
                "description": self._get_intent_description(it),
                "requires_confirmation": self._get_confirmation_requirement(it),
            }
            for it, _, _ in self._patterns
        ]

    def _get_intent_description(self, intent_type: IntentType) -> str:
        descriptions = {
            IntentType.SYSTEM_STATUS: "Get system health and status overview",
            IntentType.PROCESS_LIST: "List running processes and resource usage",
            IntentType.DISK_STATUS: "Check disk space and storage usage",
            IntentType.NETWORK_STATUS: "Check network connectivity and speed",
            IntentType.BATTERY_STATUS: "Check battery level and status",
            IntentType.EMAIL_LIST: "List emails from connected accounts",
            IntentType.EMAIL_SEARCH: "Search for specific emails",
            IntentType.EMAIL_DRAFT: "Create an email draft",
            IntentType.EMAIL_SEND: "Send a prepared email",
            IntentType.APP_LAUNCH: "Launch an approved application",
            IntentType.APP_TERMINATE: "Terminate a running process",
            IntentType.REMINDER_CREATE: "Create a new reminder",
            IntentType.REMINDER_LIST: "List pending reminders",
            IntentType.REMINDER_COMPLETE: "Mark reminder as complete",
            IntentType.NOTE_CREATE: "Create a new note",
            IntentType.NOTE_LIST: "List saved notes",
            IntentType.NOTE_SEARCH: "Search notes",
            IntentType.FILE_SEARCH: "Search for files in approved directories",
            IntentType.SETTING_GET: "Get a setting value",
            IntentType.SETTING_SET: "Change a setting",
            IntentType.HELP: "Show available commands",
            IntentType.STOP_SPEAKING: "Stop current speech output",
            IntentType.CANCEL_ACTION: "Cancel pending action",
            IntentType.GENERAL_QUERY: "General question for AI",
        }
        return descriptions.get(intent_type, "Unknown intent")