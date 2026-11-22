from app.api.routes import app, api_router
app.include_router(api_router)

# Add health routes
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/health")
async def api_health():
    return {"status": "ok"}

def get_settings():
    from app.config import get_settings as gs
    return gs()