from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, AsyncGenerator
import json


@dataclass
class AIMessage:
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class AIResponse:
    message: AIMessage
    finish_reason: str
    usage: Optional[Dict[str, int]] = None
    model: str = ""
    provider: str = ""


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    requires_confirmation: bool = False


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: List[AIMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        pass

    @abstractmethod
    async def stream_complete(
        self,
        messages: List[AIMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass


class LocalAIProvider(AIProvider):
    def __init__(self, base_url: str, model: str, api_key: str = "not-required"):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._client = None

    async def _get_client(self):
        import httpx
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120.0,
            )
        return self._client

    async def complete(
        self,
        messages: List[AIMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        client = await self._get_client()

        payload = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = []
            for t in tools:
                if isinstance(t, dict):
                    name = t.get("name")
                    description = t.get("description")
                    parameters = t.get("parameters", {})
                else:
                    name = getattr(t, "name")
                    description = getattr(t, "description")
                    parameters = getattr(t, "parameters", {})
                payload["tools"].append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                })
            payload["tool_choice"] = "auto"

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message_data = choice["message"]

        tool_calls = None
        if message_data.get("tool_calls"):
            tool_calls = message_data["tool_calls"]

        return AIResponse(
            message=AIMessage(
                role=message_data["role"],
                content=message_data.get("content", ""),
                tool_calls=tool_calls,
            ),
            finish_reason=choice["finish_reason"],
            usage=data.get("usage"),
            model=data.get("model", self._model),
            provider=self.get_provider_name(),
        )

    async def stream_complete(
        self,
        messages: List[AIMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        client = await self._get_client()

        payload = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = []
            for t in tools:
                if isinstance(t, dict):
                    name = t.get("name")
                    description = t.get("description")
                    parameters = t.get("parameters", {})
                else:
                    name = getattr(t, "name")
                    description = getattr(t, "description")
                    parameters = getattr(t, "parameters", {})
                payload["tools"].append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                })
            payload["tool_choice"] = "auto"

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data["choices"][0]["delta"].get("content"):
                            yield data["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        continue

    def get_model_name(self) -> str:
        return self._model

    def get_provider_name(self) -> str:
        return "local"

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class CloudAIProvider(AIProvider):
    def __init__(self, base_url: str, model: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._client = None

    async def _get_client(self):
        import httpx
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120.0,
            )
        return self._client

    async def complete(
        self,
        messages: List[AIMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        client = await self._get_client()

        payload = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = []
            for t in tools:
                if isinstance(t, dict):
                    name = t.get("name")
                    description = t.get("description")
                    parameters = t.get("parameters", {})
                else:
                    name = getattr(t, "name")
                    description = getattr(t, "description")
                    parameters = getattr(t, "parameters", {})
                payload["tools"].append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                })
            payload["tool_choice"] = "auto"

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message_data = choice["message"]

        tool_calls = None
        if message_data.get("tool_calls"):
            tool_calls = message_data["tool_calls"]

        return AIResponse(
            message=AIMessage(
                role=message_data["role"],
                content=message_data.get("content", ""),
                tool_calls=tool_calls,
            ),
            finish_reason=choice["finish_reason"],
            usage=data.get("usage"),
            model=data.get("model", self._model),
            provider=self.get_provider_name(),
        )

    async def stream_complete(
        self,
        messages: List[AIMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        client = await self._get_client()

        payload = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = []
            for t in tools:
                if isinstance(t, dict):
                    name = t.get("name")
                    description = t.get("description")
                    parameters = t.get("parameters", {})
                else:
                    name = getattr(t, "name")
                    description = getattr(t, "description")
                    parameters = getattr(t, "parameters", {})
                payload["tools"].append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                })
            payload["tool_choice"] = "auto"

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data["choices"][0]["delta"].get("content"):
                            yield data["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        continue

    def get_model_name(self) -> str:
        return self._model

    def get_provider_name(self) -> str:
        return "cloud"

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None