from fastapi import APIRouter

from muster.api.schemas import ChatIn, ChatOut, CitationOut
from muster.copilot.chat import answer
from muster.deps import LLMDep, PlaybookDep, ScoringConfigDep, SessionDep
from muster.llm.schemas import ChatTurn

router = APIRouter(prefix="/copilot")


@router.post("/chat", response_model=ChatOut)
def chat(
    body: ChatIn, session: SessionDep, playbook: PlaybookDep, llm: LLMDep, config: ScoringConfigDep
) -> ChatOut:
    """A follow-up question, answered from read-only tools with cited asset and clause IDs."""
    history = [ChatTurn(t.role, t.content) for t in body.history]
    result = answer(session, playbook, llm, body.message, history, config)
    return ChatOut(
        answer=result.text,
        citations=[CitationOut(id=c.id, kind=c.kind) for c in result.citations],
        provider=result.provider,
        fallback=result.fallback,
        tools_used=result.tools_used,
    )
