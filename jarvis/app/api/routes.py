from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import json

from app.config import get_settings
from app.core.orchestrator import JARVISOrchestrator, OrchestratorResponse
from app.monitoring.system_monitor import SystemMonitor
from app.storage.database import get_database_manager, init_database_async


orchestrator: Optional[JARVISOrchestrator] = None
system_monitor: Optional[SystemMonitor] = None
active_websockets: list = []


class TextInput(BaseModel):
    text: str
    speak: bool = True


class VoiceInput(BaseModel):
    speak: bool = True


class SettingsUpdate(BaseModel):
    key: str
    value: str


class EmailAccountCreate(BaseModel):
    provider: str
    email: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    scopes: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, system_monitor
    orchestrator = JARVISOrchestrator()
    await orchestrator.initialize()
    system_monitor = orchestrator.system_monitor
    await orchestrator.start_monitoring()
    yield
    if orchestrator:
        await orchestrator.shutdown()


app = FastAPI(
    title="JARVIS",
    description="Personal AI Control Center",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.mount("/static", StaticFiles(directory="app/dashboard/static"), name="static")
templates = Jinja2Templates(directory="app/dashboard/templates")

# API Router with /api prefix
api_router = APIRouter(prefix="/api")

app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@api_router.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@api_router.get("/status")
async def get_status():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return {
        "assistant_status": orchestrator.status,
        "monitoring_active": system_monitor is not None,
        "ai_provider": settings.ai_provider,
        "fish_audio_configured": bool(settings.fish_audio_api_key),
    }


@api_router.post("/chat")
async def chat(input: TextInput):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    response = await orchestrator.process_text(input.text, input.speak)
    return {
        "text": response.text,
        "intent": response.intent.type.value,
        "confidence": response.intent.confidence,
        "entities": response.intent.entities,
        "spoken": response.spoken,
        "provider": response.provider,
        "model": response.model,
    }


@api_router.post("/voice")
async def voice(input: VoiceInput):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    response = await orchestrator.process_voice(input.speak)
    if not response:
        return {"text": "", "error": "No speech detected"}

    return {
        "text": response.text,
        "intent": response.intent.type.value,
        "confidence": response.intent.confidence,
        "entities": response.intent.entities,
        "spoken": response.spoken,
        "provider": response.provider,
        "model": response.model,
    }


@api_router.post("/voice/stop")
async def stop_speaking():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    await orchestrator.stop_speaking()
    return {"success": True}


@api_router.get("/system/snapshot")
async def get_system_snapshot():
    if not system_monitor:
        raise HTTPException(status_code=503, detail="System monitor not initialized")

    snapshot = system_monitor.get_latest()
    if not snapshot:
        return {"error": "No snapshot available"}

    return {
        "timestamp": snapshot.timestamp.isoformat(),
        "cpu": {
            "percent": snapshot.cpu.percent,
            "per_cpu": snapshot.cpu.per_cpu,
            "cores_logical": snapshot.cpu.count_logical,
            "cores_physical": snapshot.cpu.count_physical,
            "freq_mhz": snapshot.cpu.freq_current,
        },
        "memory": {
            "total_gb": round(snapshot.memory.total / (1024**3), 2),
            "used_gb": round(snapshot.memory.used / (1024**3), 2),
            "available_gb": round(snapshot.memory.available / (1024**3), 2),
            "percent": snapshot.memory.percent,
        },
        "disks": [
            {
                "device": d.device,
                "mountpoint": d.mountpoint,
                "total_gb": round(d.total / (1024**3), 2),
                "used_gb": round(d.used / (1024**3), 2),
                "free_gb": round(d.free / (1024**3), 2),
                "percent": d.percent,
            }
            for d in snapshot.disks
        ],
        "battery": {
            "percent": snapshot.battery.percent,
            "power_plugged": snapshot.battery.power_plugged,
            "time_left_minutes": snapshot.battery.time_left // 60 if snapshot.battery.time_left else None,
            "status": snapshot.battery.status,
        } if snapshot.battery else None,
        "network": {
            "internet_connected": snapshot.network.internet_connected,
            "interfaces": [
                {
                    "name": i.name,
                    "up": i.is_up,
                    "ipv4": i.ipv4_address,
                    "bytes_sent_mb": round(i.bytes_sent / (1024**2), 2),
                    "bytes_recv_mb": round(i.bytes_recv / (1024**2), 2),
                }
                for i in snapshot.network.interfaces
            ],
        },
        "system": {
            "hostname": snapshot.system.hostname,
            "platform": snapshot.system.platform,
            "platform_version": snapshot.system.platform_version,
            "architecture": snapshot.system.architecture,
            "uptime_hours": round(snapshot.system.uptime_seconds / 3600, 1),
        },
        "alerts": snapshot.alerts,
    }


@api_router.get("/system/history")
async def get_system_history(minutes: int = 5):
    if not system_monitor:
        raise HTTPException(status_code=503, detail="System monitor not initialized")

    history = system_monitor.get_history(minutes)
    return {
        "cpu": [{"timestamp": s.timestamp.isoformat(), "percent": s.cpu.percent} for s in history],
        "memory": [{"timestamp": s.timestamp.isoformat(), "percent": s.memory.percent} for s in history],
    }


@api_router.get("/system/processes")
async def get_processes(limit: int = 50):
    if not system_monitor:
        raise HTTPException(status_code=503, detail="System monitor not initialized")

    snapshot = system_monitor.get_latest()
    if not snapshot:
        return {"processes": []}

    processes = snapshot.processes[:limit]
    return {
        "processes": [
            {
                "pid": p.pid,
                "name": p.name,
                "username": p.username,
                "cpu_percent": p.cpu_percent,
                "memory_percent": p.memory_percent,
                "memory_mb": round(p.memory_rss / (1024**2), 1),
                "status": p.status,
                "exe": p.exe,
            }
            for p in processes
        ]
    }


@api_router.get("/email/accounts")
async def get_email_accounts():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import EmailAccountRepository
        repo = EmailAccountRepository(session)
        accounts = await repo.get_active()
        return {
            "accounts": [
                {
                    "id": a.id,
                    "provider": a.provider.value,
                    "email": a.email_address,
                    "display_name": a.display_name,
                    "last_sync": a.last_sync_at.isoformat() if a.last_sync_at else None,
                }
                for a in accounts
            ]
        }
    finally:
        await session.close()


@api_router.get("/email/messages")
async def get_email_messages(account_id: int = None, limit: int = 20, unread_only: bool = False, search: str = None):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import EmailAccountRepository, EmailMessageRepository
        account_repo = EmailAccountRepository(session)
        message_repo = EmailMessageRepository(session)

        accounts = await account_repo.get_active()
        if account_id:
            accounts = [a for a in accounts if a.id == account_id]

        all_messages = []
        for account in accounts:
            messages = await message_repo.get_by_account(account.id, limit=limit, unread_only=unread_only, search_query=search)
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

        return {"messages": all_messages[:limit]}
    finally:
        await session.close()


@api_router.get("/reminders")
async def get_reminders(include_completed: bool = False):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import ReminderRepository
        repo = ReminderRepository(session)
        reminders = await repo.get_all(include_completed=include_completed)
        return {
            "reminders": [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "due_at": r.due_at.isoformat(),
                    "completed": r.is_completed,
                }
                for r in reminders
            ]
        }
    finally:
        await session.close()


@api_router.get("/notes")
async def get_notes(search: str = None):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import NoteRepository
        repo = NoteRepository(session)
        notes = await repo.get_all(search_query=search)
        return {
            "notes": [
                {
                    "id": n.id,
                    "title": n.title,
                    "content": n.content,
                    "tags": n.tags,
                    "pinned": n.is_pinned,
                    "updated_at": n.updated_at.isoformat(),
                }
                for n in notes
            ]
        }
    finally:
        await session.close()


@api_router.get("/applications")
async def get_applications():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import ApplicationShortcutRepository
        repo = ApplicationShortcutRepository(session)
        shortcuts = await repo.get_all()
        return {
            "applications": [
                {
                    "id": s.id,
                    "name": s.name,
                    "executable": s.executable_path,
                    "approved": s.is_approved,
                    "launch_count": s.launch_count,
                }
                for s in shortcuts
            ]
        }
    finally:
        await session.close()


@api_router.get("/alerts")
async def get_alerts():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import SystemAlertRepository
        repo = SystemAlertRepository(session)
        alerts = await repo.get_unacknowledged()
        return {
            "alerts": [
                {
                    "id": a.id,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "source": a.source,
                    "created_at": a.created_at.isoformat(),
                }
                for a in alerts
            ]
        }
    finally:
        await session.close()


@api_router.get("/settings")
async def get_settings_api():
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import SettingRepository
        repo = SettingRepository(session)
        settings_list = await repo.get_all(include_sensitive=False)
        return {
            "settings": [
                {"key": s.key, "value": s.value, "description": s.description}
                for s in settings_list
            ]
        }
    finally:
        await session.close()


@api_router.post("/settings")
async def set_setting(update: SettingsUpdate):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    db = get_database_manager()
    session = db.async_session_factory()
    try:
        from app.storage.repositories import SettingRepository
        repo = SettingRepository(session)
        await repo.set(update.key, update.value)
        return {"success": True}
    finally:
        await session.close()


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "chat":
                response = await orchestrator.process_text(message.get("text", ""), message.get("speak", True))
                await websocket.send_json({
                    "type": "response",
                    "text": response.text,
                    "intent": response.intent.type.value,
                    "spoken": response.spoken,
                })
            elif message.get("type") == "voice":
                response = await orchestrator.process_voice(message.get("speak", True))
                if response:
                    await websocket.send_json({
                        "type": "response",
                        "text": response.text,
                        "intent": response.intent.type.value,
                        "spoken": response.spoken,
                    })
                else:
                    await websocket.send_json({"type": "error", "message": "No speech detected"})
            elif message.get("type") == "stop_speaking":
                await orchestrator.stop_speaking()
                await websocket.send_json({"type": "stopped"})
            elif message.get("type") == "system_snapshot":
                snapshot = system_monitor.get_latest()
                if snapshot:
                    await websocket.send_json({"type": "system_snapshot", "data": snapshot})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


async def broadcast_system_update(data: dict):
    for ws in active_websockets[:]:
        try:
            await ws.send_json({"type": "system_update", "data": data})
        except Exception:
            pass
        except Exception:
            active_websockets.remove(ws)