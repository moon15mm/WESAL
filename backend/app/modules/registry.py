"""Central list of API routers (one per module)."""
from app.modules.auth.router import router as auth_router
from app.modules.public.health import router as health_router

ROUTERS = [health_router, auth_router]
