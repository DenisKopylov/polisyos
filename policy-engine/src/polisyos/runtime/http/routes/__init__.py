"""Exports the runtime API routers mounted on the FastAPI application."""
from polisyos.runtime.http.routes.artifacts import router as artifacts_router
from polisyos.runtime.http.routes.debug import router as debug_router
from polisyos.runtime.http.routes.health import router as health_router
from polisyos.runtime.http.routes.mobility import router as mobility_router
from polisyos.runtime.http.routes.runs import router as runs_router

__all__ = ["artifacts_router", "debug_router", "health_router", "mobility_router", "runs_router"]
