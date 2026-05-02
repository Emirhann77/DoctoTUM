import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import (
    ai_assistant,
    appointments,
    emergency,
    prescriptions,
    specialists,
    users,
)


def create_app() -> FastAPI:
    # Load local env vars from .env when present (safe in dev; ignored in prod).
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
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
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    # Allow overriding via env without changing code.
    extra_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if extra_origins:
        allowed_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(specialists.router, prefix="/api", tags=["Specialists"])
    app.include_router(appointments.router, prefix="/api", tags=["Appointments"])
    app.include_router(emergency.router, prefix="/api", tags=["Emergency"])
    app.include_router(ai_assistant.router, prefix="/api", tags=["AI Assistant"])
    app.include_router(prescriptions.router, prefix="/api", tags=["Prescriptions"])
    app.include_router(users.router, prefix="/api", tags=["Users"])

    return app


app = create_app()

