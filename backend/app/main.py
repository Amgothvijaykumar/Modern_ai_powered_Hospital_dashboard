from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent import router as agent_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.bills import router as bills_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.operations import router as operations_router
from app.api.routes.permissions import router as permissions_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Permission-Aware Multi-Tenant Hospital Operations AI Agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(permissions_router)
app.include_router(agent_router)
app.include_router(operations_router)
app.include_router(inventory_router)
app.include_router(bills_router)
app.include_router(users_router)
app.include_router(audit_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "environment": settings.ENVIRONMENT}
