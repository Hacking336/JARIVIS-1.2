from app.api import routes
app = routes.app
app.include_router(routes.api_router)
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=3000)