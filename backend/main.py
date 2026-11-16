import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routes import (
    ai_assistant,
    appointments,
    care,
    emergency,
    integrations,
    pharmacy,
    prescriptions,
    specialists,
    users,
)
from backend.store import StoreError


def create_app() -> FastAPI:
    # Load local env vars from .env when present (safe in dev; ignored in prod).
    # Tests set CARECONNECT_SKIP_DOTENV so a developer's real keys never leak into them.
    if not os.getenv("CARECONNECT_SKIP_DOTENV"):
        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv()
            load_dotenv(".env.local", override=True)
        except Exception:
            # python-dotenv is optional; environment variables can still be set externally.
            pass

    app = FastAPI(
        title="DoctoTUM / CareConnect Backend",
        version="0.1.0",
        description="Backend API + AI integration for DoctoTUM / CareConnect.",
    )

    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8080",
    ]
    # Allow overriding via env without changing code.
    extra_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if extra_origins:
        allowed_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,  # auth is a bearer token, not a cookie
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(StoreError)
    async def store_error_handler(_: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(specialists.router, prefix="/api", tags=["Specialists"])
    app.include_router(appointments.router, prefix="/api", tags=["Appointments"])
    app.include_router(emergency.router, prefix="/api", tags=["Emergency"])
    app.include_router(ai_assistant.router, prefix="/api", tags=["AI Assistant"])
    app.include_router(care.router, prefix="/api", tags=["Care Navigator"])
    app.include_router(prescriptions.router, prefix="/api", tags=["Prescriptions"])
    app.include_router(pharmacy.router, prefix="/api", tags=["Pharmacy"])
    app.include_router(users.router, prefix="/api", tags=["Users"])
    app.include_router(integrations.router, prefix="/api", tags=["Integrations"])

    return app


app = create_app()

