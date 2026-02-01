from pydantic import BaseModel, Field


class DemoPayload(BaseModel):
    message: str = Field(..., description="Demo message")
