from fastapi import HTTPException

from ..ai.memory_api import deactivate_memory_api, delete_memory_api, list_memories_api
from ..ai.memory_service import sync_long_term_memory_from_turn
from .. import models
from ..schemas_ai_chat import AIChatMemoryBackfillResponse, AIChatMemoryBackfillScopeResult


def _legacy():
    from .. import main as legacy

    return legacy


def list_ai_memory_items_service(*, request, scope="global", scope_id=None, include_inactive=False, limit=100, db):
    legacy = _legacy()
    user = legacy.require_current_user(request, db)
    return list_memories_api(
        db,
        user_id=int(user.id),
        scope=scope,
        scope_id=scope_id,
        include_inactive=include_inactive,
        limit=limit,
    )


def deactivate_ai_memory_item_service(*, memory_id: int, request, db):
    legacy = _legacy()
    user = legacy.require_current_user(request, db)
    result = deactivate_memory_api(
        db,
        user_id=int(user.id),
        memory_id=int(memory_id),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="メモリが見つかりません。")
    return result


def delete_ai_memory_item_service(*, memory_id: int, request, db):
    legacy = _legacy()
    user = legacy.require_current_user(request, db)
    result = delete_memory_api(
        db,
        user_id=int(user.id),
        memory_id=int(memory_id),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="メモリが見つかりません。")
    return result


async def backfill_ai_memory_from_logs_service(*, payload, request, db):
    legacy = _legacy()
    if not legacy.AI_CHAT_MEMORY_ENABLED:
        raise HTTPException(status_code=400, detail="AIメモリ機能が無効です。")

    user = legacy.require_current_user(request, db)
    legacy._ensure_ai_chat_access(user, db)

    targets: list[models.AIChatCharacter] = []
    if payload.character_id is not None:
        character = legacy._find_editable_ai_chat_character(
            db=db,
            viewer=user,
            character_id=int(payload.character_id),
        )
        if character is None:
            raise HTTPException(status_code=404, detail="キャラが見つかりません。")
        targets = [character]
    else:
        targets = (
            db.query(models.AIChatCharacter)
            .filter(models.AIChatCharacter.user_id == int(user.id))
            .order_by(models.AIChatCharacter.id.asc())
            .all()
        )

    result = AIChatMemoryBackfillResponse(dry_run=bool(payload.dry_run))
    if not targets:
        return result

    max_turns = int(payload.max_turns_per_scope)
    for character in targets:
        rows = (
            db.query(models.AIChatMessage)
            .filter(
                models.AIChatMessage.user_id == int(user.id),
                models.AIChatMessage.character_id == int(character.id),
                models.AIChatMessage.is_deleted == False,
            )
            .order_by(models.AIChatMessage.created_at.desc(), models.AIChatMessage.id.desc())
            .limit(5000)
            .all()
        )
        rows.reverse()
        turns, scanned_count = legacy._collect_ai_chat_backfill_turns(
            messages=rows,
            character_name=str(character.name or "").strip()[:80],
            max_turns=max_turns,
        )
        scope_saved = 0
        scope_processed = 0
        scope_failed = 0
        if not payload.dry_run:
            for turn in turns:
                try:
                    saved = await sync_long_term_memory_from_turn(
                        db,
                        user_id=int(user.id),
                        scope="character",
                        scope_id=int(character.id),
                        history_lines=list(turn["history_lines"]),
                        user_message=str(turn["user_message"]),
                        assistant_reply=str(turn["assistant_reply"]),
                        model=payload.model,
                        provider=payload.provider,
                        source_message_id=int(turn["source_message_id"]),
                    )
                    scope_saved += int(saved or 0)
                    scope_processed += 1
                except Exception as e:
                    scope_failed += 1
                    legacy.logger.warning(
                        "memory backfill turn failed user=%s character=%s msg=%s err=%r",
                        int(user.id),
                        int(character.id),
                        int(turn["source_message_id"]),
                        e,
                    )

        scope_result = AIChatMemoryBackfillScopeResult(
            scope_id=int(character.id),
            scanned_messages=int(scanned_count),
            candidate_turns=int(len(turns)),
            processed_turns=int(scope_processed),
            saved_items=int(scope_saved),
            failed_turns=int(scope_failed),
        )
        result.scopes.append(scope_result)
        result.total_scanned_messages += int(scanned_count)
        result.total_candidate_turns += int(len(turns))
        result.total_processed_turns += int(scope_processed)
        result.total_saved_items += int(scope_saved)
        result.total_failed_turns += int(scope_failed)

    return result
