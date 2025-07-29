from pydantic import BaseModel, Field

class CommandInput(BaseModel):
    command: str = Field(..., min_length=5, max_length=500, regex=r"^[a-zA-Z0-9\s.,?!@#&()\-_=+]+$")
