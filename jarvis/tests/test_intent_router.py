import pytest
from datetime import datetime

from app.core.intent_router import IntentRouter, Intent, IntentType


class TestIntentRouter:
    @pytest.fixture
    def router(self):
        return IntentRouter()

    def test_router_initialization(self, router):
        assert router._patterns is not None
        assert len(router._patterns) > 0

    def test_classify_system_status(self, router):
        intent = router.classify("Give me a system status report")
        assert intent.type == IntentType.SYSTEM_STATUS
        assert intent.confidence > 0

    def test_classify_process_list(self, router):
        intent = router.classify("Which applications are consuming the most memory?")
        assert intent.type == IntentType.PROCESS_LIST

    def test_classify_disk_status(self, router):
        intent = router.classify("How much disk space is available?")
        assert intent.type == IntentType.DISK_STATUS

    def test_classify_network_status(self, router):
        intent = router.classify("Check whether my internet connection is working")
        assert intent.type == IntentType.NETWORK_STATUS

    def test_classify_battery_status(self, router):
        intent = router.classify("What is my battery level?")
        assert intent.type == IntentType.BATTERY_STATUS

    def test_classify_email_list(self, router):
        intent = router.classify("Show my unread emails")
        assert intent.type == IntentType.EMAIL_LIST

    def test_classify_email_search(self, router):
        intent = router.classify("Find the latest email from John")
        assert intent.type == IntentType.EMAIL_SEARCH

    def test_classify_email_draft(self, router):
        intent = router.classify("Draft a reply to this email")
        assert intent.type == IntentType.EMAIL_DRAFT
        assert intent.requires_confirmation is True

    def test_classify_email_send(self, router):
        intent = router.classify("Send this email")
        assert intent.type == IntentType.EMAIL_SEND
        assert intent.requires_confirmation is True

    def test_classify_app_launch(self, router):
        intent = router.classify("Open Notepad")
        assert intent.type == IntentType.APP_LAUNCH

    def test_classify_app_terminate(self, router):
        intent = router.classify("Terminate the chrome process")
        assert intent.type == IntentType.APP_TERMINATE
        assert intent.requires_confirmation is True

    def test_classify_reminder_create(self, router):
        intent = router.classify("Create a reminder for tomorrow")
        assert intent.type == IntentType.REMINDER_CREATE

    def test_classify_reminder_list(self, router):
        intent = router.classify("Show my reminders")
        assert intent.type == IntentType.REMINDER_LIST

    def test_classify_note_create(self, router):
        intent = router.classify("Write a note about the meeting")
        assert intent.type == IntentType.NOTE_CREATE

    def test_classify_file_search(self, router):
        intent = router.classify("Find files named report.pdf")
        assert intent.type == IntentType.FILE_SEARCH

    def test_classify_stop_speaking(self, router):
        intent = router.classify("Stop speaking")
        assert intent.type == IntentType.STOP_SPEAKING

    def test_classify_cancel_action(self, router):
        intent = router.classify("Cancel that operation")
        assert intent.type == IntentType.CANCEL_ACTION

    def test_classify_help(self, router):
        intent = router.classify("What can you do?")
        assert intent.type == IntentType.HELP

    def test_classify_unknown(self, router):
        intent = router.classify("xyzzy gibberish unknown")
        assert intent.type == IntentType.UNKNOWN
        assert intent.confidence == 0.0

    def test_classify_case_insensitive(self, router):
        intent = router.classify("OPEN NOTEPAD")
        assert intent.type == IntentType.APP_LAUNCH

    def test_classify_with_entities(self, router):
        intent = router.classify("Find the latest email from john@example.com")
        assert intent.type == IntentType.EMAIL_SEARCH
        assert "sender" in intent.entities

    def test_classify_app_launch_with_entity(self, router):
        intent = router.classify("Open chrome")
        assert intent.type == IntentType.APP_LAUNCH
        assert intent.entities.get("application") == "chrome"

    def test_classify_reminder_with_time(self, router):
        intent = router.classify("Remind me in 30 minutes")
        assert intent.type == IntentType.REMINDER_CREATE
        assert "time_expression" in intent.entities

    def test_classify_file_search_with_query(self, router):
        intent = router.classify("Find files named document.docx")
        assert intent.type == IntentType.FILE_SEARCH
        assert "query" in intent.entities

    def test_get_supported_intents(self, router):
        intents = router.get_supported_intents()
        assert isinstance(intents, list)
        assert len(intents) > 0
        for intent in intents:
            assert "type" in intent
            assert "description" in intent
            assert "requires_confirmation" in intent

    def test_intent_dataclass(self):
        intent = Intent(
            type=IntentType.SYSTEM_STATUS,
            confidence=0.95,
            entities={"key": "value"},
            raw_text="test",
            requires_confirmation=False,
        )
        assert intent.type == IntentType.SYSTEM_STATUS
        assert intent.confidence == 0.95
        assert intent.entities == {"key": "value"}
        assert intent.raw_text == "test"
        assert intent.requires_confirmation is False

    def test_confirmation_requirements(self, router):
        # Email send requires confirmation
        intent = router.classify("Send email to boss")
        assert intent.requires_confirmation is True

        # App terminate requires confirmation
        intent = router.classify("Kill the process")
        assert intent.requires_confirmation is True

        # System status does not require confirmation
        intent = router.classify("System status")
        assert intent.requires_confirmation is False

    def test_multiple_intents_priority(self, router):
        # When multiple patterns match, highest confidence wins
        intent = router.classify("Show my unread emails from John about the project")
        # Should match email search or email list
        assert intent.type in (IntentType.EMAIL_LIST, IntentType.EMAIL_SEARCH)

    def test_intent_type_values(self):
        assert IntentType.SYSTEM_STATUS.value == "system_status"
        assert IntentType.PROCESS_LIST.value == "process_list"
        assert IntentType.EMAIL_SEND.value == "email_send"
        assert IntentType.STOP_SPEAKING.value == "stop_speaking"
        assert IntentType.UNKNOWN.value == "unknown"