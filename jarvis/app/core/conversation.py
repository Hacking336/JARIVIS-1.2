from datetime import datetime
from typing import List, Optional, Dict, Any

from app.models import Conversation, ActionLog, AIProviderType
from app.storage.repositories import ConversationRepository, ActionLogRepository
from app.integrations.ai.providers import (
    AIProvider,
    LocalAIProvider,
    CloudAIProvider,
    AIMessage,
    AIResponse,
    ToolDefinition,
)


class ConversationManager:
    def __init__(self, conversation_repo: ConversationRepository, action_repo: ActionLogRepository):
        self._conversation_repo = conversation_repo
        self._action_repo = action_repo
        self._session_id = self._generate_session_id()
        self._max_history = 20

    def _generate_session_id(self) -> str:
        import uuid
        return str(uuid.uuid4())[:8]

    @property
    def session_id(self) -> str:
        return self._session_id

    async def add_exchange(
        self,
        user_message: str,
        assistant_response: str,
        ai_provider: AIProviderType,
        model_used: str,
        tokens_used: Optional[int] = None,
    ) -> Conversation:
        return await self._conversation_repo.create(
            session_id=self._session_id,
            user_message=user_message,
            assistant_response=assistant_response,
            ai_provider=ai_provider,
            model_used=model_used,
            tokens_used=tokens_used,
        )

    async def get_history(self, limit: int = 20) -> List[Conversation]:
        return await self._conversation_repo.get_by_session(self._session_id, limit)

    async def get_context_messages(self, limit: int = 10) -> List[AIMessage]:
        conversations = await self.get_history(limit)
        messages = []
        for conv in reversed(conversations):
            messages.append(AIMessage(role='user', content=conv.user_message))
            messages.append(AIMessage(role='assistant', content=conv.assistant_response))
        return messages

    async def log_action(
        self,
        action_type: str,
        action_params: Dict[str, Any],
        requires_confirmation: bool = False,
    ) -> ActionLog:
        import json
        return await self._action_repo.create(
            action_type=action_type,
            action_params=json.dumps(action_params),
            conversation_id=None,
            requires_confirmation=requires_confirmation,
        )

    async def update_action(
        self,
        action_id: int,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        confirmed: bool = False,
    ):
        from app.models import ActionStatus
        await self._action_repo.update_status(
            action_id=action_id,
            status=ActionStatus(status),
            result=result,
            error=error,
            confirmed=confirmed,
        )

    def new_session(self):
        self._session_id = self._generate_session_id()


class AIProviderFactory:
    def __init__(self):
        self._local_provider: Optional[LocalAIProvider] = None
        self._cloud_provider: Optional[CloudAIProvider] = None

    def get_provider(self, provider_type: str):
        from app.config import get_settings
        settings = get_settings()

        if provider_type == 'local':
            if self._local_provider is None:
                self._local_provider = LocalAIProvider(
                    base_url=settings.local_ai_base_url,
                    model=settings.local_ai_model,
                    api_key=settings.local_ai_api_key,
                )
            return self._local_provider

        elif provider_type == 'cloud':
            if self._cloud_provider is None:
                if not settings.cloud_ai_api_key:
                    raise ValueError('Cloud AI API key not configured')
                self._cloud_provider = CloudAIProvider(
                    base_url=settings.cloud_ai_base_url or 'https://api.openai.com/v1',
                    model=settings.cloud_ai_model,
                    api_key=settings.cloud_ai_api_key,
                )
            return self._cloud_provider

        elif provider_type == 'llamacpp':
            if not settings.llamacpp_enabled:
                raise ValueError('llamacpp provider requested but llamacpp_enabled is False')
            # llamacpp uses the same OpenAI-compatible API as LocalAIProvider
            # The base URL points to the local llama.cpp server
            base_url = f'http://{settings.llamacpp_host}:{settings.llamacpp_port}/v1'
            # Use the GGUF model filename as the model name for llama.cpp server
            model_name = Path(settings.llamacpp_model_path).name
            return LocalAIProvider(
                base_url=base_url,
                model=model_name,
                api_key='not-required',
            )

        else:
            raise ValueError(f'Unknown provider type: {provider_type}')

    async def close_all(self):
        if self._local_provider:
            await self._local_provider.close()
        if self._cloud_provider:
            await self._cloud_provider.close()
