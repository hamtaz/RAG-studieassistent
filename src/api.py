"""FastAPI wrapper around the RAG pipeline: one endpoint, question in, answer out."""

import logging

from azure.core.exceptions import AzureError
from fastapi import FastAPI, HTTPException
from openai import OpenAIError
from pydantic import BaseModel

from src.cosmos_client import get_container
from src.generation import answer_question

logger = logging.getLogger(__name__)

app = FastAPI(title="Studieassistent")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    try:
        return answer_question(request.question, get_container())
    except (OpenAIError, AzureError) as e:
        logger.warning("Chat completion failed for question %r: %s", request.question, e)
        raise HTTPException(status_code=502, detail="Upstream AI service failed") from e
