"""Natural language query endpoint.

Accepts questions in plain English and uses AI to convert them
into database queries, then formats the results as human-readable answers.
"""

from fastapi import APIRouter

from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    """Ask a natural language question about CMDB data.

    Examples:
        - "Which users don't have MFA?"
        - "Show me all active devices in London"
        - "How many SaaS apps have SSO enabled?"
    """
    # Stub — will be implemented in Phase 4
    return AskResponse(
        answer="Natural language queries will be available after AI integration.",
        results=[],
        query_interpretation="not_implemented",
    )
