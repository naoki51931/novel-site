from pydantic import BaseModel


class EpisodeAssistCandidatesRequest(BaseModel):
    title: str | None = None
    text: str
    tags: list[str] = []
    suggestions_count: int = 4
    model: str | None = None
    provider: str | None = None
