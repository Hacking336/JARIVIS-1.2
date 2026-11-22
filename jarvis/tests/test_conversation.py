import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.core.conversation import ConversationManager, AIProviderFactory
from app.integrations.ai.providers import (
    LocalAIProvider,
    CloudAIProvider,
    AIMessage,
    AIResponse,
    ToolDefinition,
)
from app.models import Conversation, ActionLog, AIProviderType, ActionStatus


class TestConversationManager:
    @pytest.fixture
    def repos(self):
        conversation_repo = Mock()
        conversation_repo.create = AsyncMock()
        conversation_repo.get_by_session = AsyncMock(return_value=[])

        action_repo = Mock()
        action_repo.create = AsyncMock()
        action_repo.update_status = AsyncMock()

        return conversation_repo, action_repo

    @pytest.fixture
    def manager(self, repos):
        return ConversationManager(repos[0], repos[1])

    def test_initialization(self, manager):
        assert manager.session_id is not None
        assert len(manager.session_id) == 8

    def test_session_id_generation(self, manager):
        old_id = manager.session_id
        manager.new_session()
        assert manager.session_id != old_id
        assert len(manager.session_id) == 8

    @pytest.mark.asyncio
    async def test_add_exchange(self, manager, repos):
        mock_conversation = Mock(spec=Conversation)
        repos[0].create = AsyncMock(return_value=mock_conversation)

        result = await manager.add_exchange(
            user_message="Hello",
            assistant_response="Hi there",
            ai_provider=AIProviderType.LOCAL,
            model_used="llama3.2:3b",
            tokens_used=100,
        )

        repos[0].create.assert_called_once()
        assert result is mock_conversation

    @pytest.mark.asyncio
    async def test_get_history(self, manager, repos):
        mock_conversations = [Mock(spec=Conversation)]
        repos[0].get_by_session = AsyncMock(return_value=mock_conversations)

        result = await manager.get_history(limit=20)
        assert result == mock_conversations

    @pytest.mark.asyncio
    async def test_get_context_messages(self, manager, repos):
        mock_conv = Mock(spec=Conversation)
        mock_conv.user_message = "Hello"
        mock_conv.assistant_response = "Hi"
        repos[0].get_by_session = AsyncMock(return_value=[mock_conv])

        messages = await manager.get_context_messages(limit=10)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Hi"

    @pytest.mark.asyncio
    async def test_log_action(self, manager, repos):
        mock_action = Mock(spec=ActionLog)
        repos[1].create = AsyncMock(return_value=mock_action)

        result = await manager.log_action(
            action_type="test_action",
            action_params={"key": "value"},
            requires_confirmation=True,
        )

        repos[1].create.assert_called_once()
        assert result is mock_action

    @pytest.mark.asyncio
    async def test_update_action(self, manager, repos):
        from app.models import ActionStatus
        repos[1].update_status = AsyncMock()

        await manager.update_action(
            action_id=1,
            status=ActionStatus.COMPLETED,
            result="Success",
            confirmed=True,
        )

        repos[1].update_status.assert_called_once()


class TestAIProviderFactory:
    @pytest.fixture
    def factory(self):
        return AIProviderFactory()

    def test_get_local_provider(self, factory):
        with patch('app.config.get_settings') as mock_settings:
            settings = Mock()
            settings.ai_provider = "local"
            settings.local_ai_base_url = "http://localhost:11434/v1"
            settings.local_ai_model = "llama3.2:3b"
            settings.local_ai_api_key = "not-required"
            mock_settings.return_value = settings

            provider = factory.get_provider("local")
            assert isinstance(provider, LocalAIProvider)
            assert provider.get_provider_name() == "local"
            assert provider.get_model_name() == "llama3.2:3b"

    def test_get_cloud_provider_no_key(self, factory):
        with patch('app.config.get_settings') as mock_settings:
            settings = Mock()
            settings.cloud_ai_api_key = None
            mock_settings.return_value = settings

            with pytest.raises(ValueError, match="Cloud AI API key not configured"):
                factory.get_provider("cloud")

    def test_get_cloud_provider_with_key(self, factory):
        with patch('app.config.get_settings') as mock_settings:
            settings = Mock()
            settings.cloud_ai_api_key = "test-key"
            settings.cloud_ai_base_url = "https://api.openai.com/v1"
            settings.cloud_ai_model = "gpt-4o-mini"
            mock_settings.return_value = settings

            provider = factory.get_provider("cloud")
            assert isinstance(provider, CloudAIProvider)
            assert provider.get_provider_name() == "cloud"
            assert provider.get_model_name() == "gpt-4o-mini"

    def test_get_unknown_provider(self, factory):
        with pytest.raises(ValueError, match="Unknown provider type"):
            factory.get_provider("unknown")

    @pytest.mark.asyncio
    async def test_close_all(self, factory):
        provider = factory.get_provider("local")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        provider._client = mock_client
        factory._local_provider = provider

        await factory.close_all()

        mock_client.aclose.assert_called_once()


class TestLocalAIProvider:
    @pytest.fixture
    def provider(self):
        return LocalAIProvider(
            base_url="http://localhost:11434/v1",
            model="llama3.2:3b",
            api_key="not-required",
        )

    def test_initialization(self, provider):
        assert provider._base_url == "http://localhost:11434/v1"
        assert provider._model == "llama3.2:3b"
        assert provider._api_key == "not-required"
        assert provider._client is None

    def test_get_model_name(self, provider):
        assert provider.get_model_name() == "llama3.2:3b"

    def test_get_provider_name(self, provider):
        assert provider.get_provider_name() == "local"

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        mock_response = Mock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        provider._client = mock_client

        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_complete(self, provider):
        mock_response = Mock()
        mock_response.json = Mock(return_value={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Test response",
                },
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 100},
            "model": "llama3.2:3b",
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        messages = [AIMessage(role="user", content="Hello")]
        response = await provider.complete(messages=messages)

        assert isinstance(response, AIResponse)
        assert response.message.content == "Test response"
        assert response.finish_reason == "stop"
        assert response.usage == {"total_tokens": 100}
        assert response.model == "llama3.2:3b"
        assert response.provider == "local"

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, provider):
        mock_response = Mock()
        mock_response.json = Mock(return_value={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "get_system_status",
                            "arguments": "{}",
                        }
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"total_tokens": 50},
            "model": "llama3.2:3b",
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        messages = [AIMessage(role="user", content="System status")]
        tools = [ToolDefinition(
            name="get_system_status",
            description="Get system status",
            parameters={"type": "object", "properties": {}},
        )]

        response = await provider.complete(messages=messages, tools=tools)

        assert response.message.tool_calls is not None
        assert len(response.message.tool_calls) == 1
        assert response.message.tool_calls[0]["function"]["name"] == "get_system_status"

    @pytest.mark.asyncio
    async def test_complete_http_error(self, provider):
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=Exception("HTTP Error"))

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        messages = [AIMessage(role="user", content="Hello")]

        with pytest.raises(Exception, match="HTTP Error"):
            await provider.complete(messages=messages)

    @pytest.mark.asyncio
    async def test_stream_complete(self, provider):
        async def aiter_lines():
            yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
            yield 'data: {"choices": [{"delta": {"content": " world"}}]}'
            yield 'data: [DONE]'

        mock_response = Mock()
        mock_response.aiter_lines = aiter_lines
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()

        # Create an async context manager for stream
        class MockStream:
            async def __aenter__(self):
                return mock_response
            async def __aexit__(self, *args):
                pass

        mock_client.stream = Mock(return_value=MockStream())
        provider._client = mock_client

        messages = [AIMessage(role="user", content="Hello")]
        chunks = []
        async for chunk in provider.stream_complete(messages=messages):
            chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_close(self, provider):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        provider._client = mock_client

        await provider.close()

        mock_client.aclose.assert_called_once()
        assert provider._client is None


class TestCloudAIProvider:
    @pytest.fixture
    def provider(self):
        return CloudAIProvider(
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            api_key="test-key",
        )

    def test_initialization(self, provider):
        assert provider._base_url == "https://api.openai.com/v1"
        assert provider._model == "gpt-4o-mini"
        assert provider._api_key == "test-key"

    def test_get_model_name(self, provider):
        assert provider.get_model_name() == "gpt-4o-mini"

    def test_get_provider_name(self, provider):
        assert provider.get_provider_name() == "cloud"

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        mock_response = Mock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        provider._client = mock_client

        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_complete(self, provider):
        mock_response = Mock()
        mock_response.json = Mock(return_value={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Cloud response",
                },
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 200},
            "model": "gpt-4o-mini",
        })
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        messages = [AIMessage(role="user", content="Hello")]
        response = await provider.complete(messages=messages)

        assert isinstance(response, AIResponse)
        assert response.message.content == "Cloud response"
        assert response.provider == "cloud"
        assert response.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_complete_timeout(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=TimeoutError("Request timeout"))
        provider._client = mock_client

        messages = [AIMessage(role="user", content="Hello")]

        with pytest.raises(TimeoutError, match="Request timeout"):
            await provider.complete(messages=messages)

    @pytest.mark.asyncio
    async def test_close(self, provider):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        provider._client = mock_client

        await provider.close()

        mock_client.aclose.assert_called_once()
        assert provider._client is None


class TestAIMessage:
    def test_message_creation(self):
        message = AIMessage(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.tool_calls is None
        assert message.tool_call_id is None
        assert message.name is None

    def test_message_with_tool_calls(self):
        message = AIMessage(
            role="assistant",
            content="",
            tool_calls=[{"function": {"name": "test", "arguments": "{}"}}],
        )
        assert message.tool_calls is not None
        assert len(message.tool_calls) == 1


class TestAIResponse:
    def test_response_creation(self):
        message = AIMessage(role="assistant", content="Test")
        response = AIResponse(
            message=message,
            finish_reason="stop",
            usage={"total_tokens": 100},
            model="test-model",
            provider="test-provider",
        )
        assert response.message == message
        assert response.finish_reason == "stop"
        assert response.usage == {"total_tokens": 100}
        assert response.model == "test-model"
        assert response.provider == "test-provider"


class TestToolDefinition:
    def test_tool_creation(self):
        tool = ToolDefinition(
            name="get_system_status",
            description="Get system status",
            parameters={"type": "object", "properties": {}},
            requires_confirmation=False,
        )
        assert tool.name == "get_system_status"
        assert tool.description == "Get system status"
        assert tool.parameters == {"type": "object", "properties": {}}
        assert tool.requires_confirmation is False

    def test_tool_with_confirmation(self):
        tool = ToolDefinition(
            name="send_email",
            description="Send email",
            parameters={"type": "object", "properties": {}},
            requires_confirmation=True,
        )
        assert tool.requires_confirmation is True