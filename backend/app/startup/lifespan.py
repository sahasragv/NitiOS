"""Application lifespan composition for the NitiOS backend."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle placeholders."""
    del app
    # Startup resource initialization will be composed here.
    yield
    # Shutdown resource cleanup will be composed here.


def get_lifespan() -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Return the lifespan context manager used by the application factory."""
    return lifespan
