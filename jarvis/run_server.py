from app.api.routes import app, api_router
app.include_router(api_router)
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=3000)