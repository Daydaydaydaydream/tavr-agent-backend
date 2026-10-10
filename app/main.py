"""FastAPI entry point: fastapi dev app/main.py."""

from fastapi import FastAPI

from app.models.schemas import GuideRequest, GuideResponse
from app.services.guidance import generate_guidance

app = FastAPI(
    title="TAVR Agent Backend",
    version="0.1.0",
    description="用于学习的软件操作引导服务，不代表完整或经过临床验证的 TAVR 工作流程。",
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/guide", response_model=GuideResponse, tags=["agent"])
def guide(request: GuideRequest) -> GuideResponse:
    return generate_guidance(request.state)
