"""Natural language query endpoint.

Accepts questions in plain English and uses AI to convert them
into database queries, then formats the results as human-readable answers.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ask import AskRequest, AskResponse
from app.services.query_service import handle_question

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
) -> AskResponse:
    """Ask a natural language question about CMDB data.

    Examples:
        - "Which users don't have MFA?"
        - "Show me all active devices in London"
        - "How many SaaS apps have SSO enabled?"
    """
    result = await handle_question(request.question, db)
    return AskResponse(
        answer=result["answer"],
        results=result["results"],
        query_interpretation=result["query_interpretation"],
    )
