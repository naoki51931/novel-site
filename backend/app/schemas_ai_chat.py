from pydantic import BaseModel


class AIChatAccessStatusResponse(BaseModel):
    is_guest: bool
    is_premium: bool
    demo_bypass: bool
    used_tokens: int
    free_tokens: int
    block_tokens: int
    block_price_yen: int
    paid_blocks: int
    allowed_tokens: int
    needs_upgrade: bool
    show_premium_prompt: bool
    show_addon_prompt: bool
    premium_included_blocks: int
