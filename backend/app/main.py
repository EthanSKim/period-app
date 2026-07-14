from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.cycles import router as cycles_router
from app.api.predictions import router as predictions_router
from app.database import Base, engine
from app.models import User  # noqa: F401

# Create database tables at startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Period App API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global validation exception handler to return 400 Bad Request instead of 422
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": jsonable_encoder(exc.errors())},
    )


# Include routers
app.include_router(auth_router)
app.include_router(cycles_router)
app.include_router(predictions_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Period App API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
