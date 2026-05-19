import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import uuid
from logger.logging_manager import LoggingManager
from logger.logging_manager import correlation_id_ctx


logger = logging.getLogger("fastapi.app")


# Lifespan context manager perfectly handles the QueueListener lifecycle natively without external packages
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_manager = LoggingManager()
    log_manager.setup()
    logger.info("Application startup: logging configured.")
    yield
    logger.info("Application shutdown: stopping log listener.")
    log_manager.shutdown()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Extract correlation ID from headers or generate a new one
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    token = correlation_id_ctx.set(correlation_id)

    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Outgoing response: {response.status_code}")

    # Return the correlation ID in the response for client-side tracing
    response.headers["X-Correlation-ID"] = correlation_id
    correlation_id_ctx.reset(token)
    return response


@app.get("/")
def main():
    return {"message": "Hello World"}
