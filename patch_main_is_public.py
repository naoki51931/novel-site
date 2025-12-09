import pathlib

path = pathlib.Path("backend/app/main.py")
src = path.read_text(encoding="utf-8")
changed = False

# ---------- create_novel: is_public を Novel に渡す ----------
if 'is_public=getattr(payload, "is_public", True)' not in src:
    needle = '        is_ai_generated=getattr(payload, "is_ai_generated", False),\n        age_limit=getattr(payload, "age_limit", "all"),\n        like_count=0,\n'
    if needle in src:
        repl = '        is_ai_generated=getattr(payload, "is_ai_generated", False),\n        age_limit=getattr(payload, "age_limit", "all"),\n        like_count=0,\n        is_public=getattr(payload, "is_public", True),\n'
        src = src.replace(needle, repl, 1)
        print("[OK] wired Novel.is_public in create_novel")
        changed = True
    else:
        print("[WARN] create_novel block not found for is_public")

# ---------- update_novel: is_public 更新 ----------
if "payload.is_public is not None" not in src:
    needle = "    # ★ タグ差し替え\n"
    if needle in src:
        insert = (
            "    if payload.is_public is not None:\n"
            "        novel.is_public = payload.is_public\n"
            "\n"
            "    # ★ タグ差し替え\n"
        )
        src = src.replace(needle, insert, 1)
        print("[OK] added is_public update to update_novel")
        changed = True
    else:
        print("[WARN] tag replace comment not found in update_novel")

# ---------- create_episode: is_public を Episode に渡す ----------
if 'is_public=getattr(payload, "is_public", True)' not in src:
    needle = "        episode_number=payload.episode_number,\n"
    if needle in src:
        repl = "        episode_number=payload.episode_number,\n        is_public=getattr(payload, \"is_public\", True),\n"
        src = src.replace(needle, repl, 1)
        print("[OK] wired Episode.is_public in create_episode")
        changed = True
    else:
        print("[WARN] episode_number line not found in create_episode")

# ---------- update_episode: is_public 更新 ----------
if 'ep.is_public =' not in src:
    needle = '    if "body" in payload and payload["body"] is not None:\n        ep.body = payload["body"]\n'
    if needle in src:
        repl = (
            '    if "body" in payload and payload["body"] is not None:\n'
            '        ep.body = payload["body"]\n'
            '\n'
            '    if "is_public" in payload and payload["is_public"] is not None:\n'
            '        ep.is_public = bool(payload["is_public"])\n'
        )
        src = src.replace(needle, repl, 1)
        print("[OK] added is_public update in update_episode")
        changed = True
    else:
        print("[WARN] update_episode body update block not found")

# ---------- /api/public/novels: is_public = True だけ ----------
if "models.Novel.is_public == True" not in src:
    needle = (
        "    query = (\n"
        "        db.query(models.Novel)\n"
        "        .options(\n"
        "            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag)\n"
        "        )\n"
        "        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)\n"
        "    )\n"
    )
    if needle in src:
        repl = needle + "    query = query.filter(models.Novel.is_public == True)\n"
        src = src.replace(needle, repl, 1)
        print("[OK] filtered public novels by is_public == True")
        changed = True
    else:
        print("[WARN] public novels query block not found")

# ---------- get_novel_detail: 下書きは作者以外 404 ----------
if "下書きの場合は作者以外は 404" not in src:
    needle = (
        '    if not novel:\n'
        '        raise HTTPException(404, "小説が存在しません")\n'
        '\n'
        '    # 閲覧数カウント\n'
    )
    if needle in src:
        insert = (
            '    if not novel:\n'
            '        raise HTTPException(404, "小説が存在しません")\n'
            '\n'
            '    # 下書きの場合は作者以外は 404\n'
            '    if not novel.is_public:\n'
            '        if not user or novel.author_id != user.id:\n'
            '            raise HTTPException(404, "小説が存在しません")\n'
            '\n'
            '    # 閲覧数カウント\n'
        )
        src = src.replace(needle, insert, 1)
        print("[OK] added draft gate to get_novel_detail")
        changed = True
    else:
        print("[WARN] get_novel_detail header block not found")

# ---------- list_episodes: 作者以外には is_public=True のみ ----------
if "base_q = (\n        db.query(models.Episode)" not in src:
    needle = (
        "    episodes = (\n"
        "        db.query(models.Episode)\n"
        "        .filter(models.Episode.novel_id == novel_id)\n"
        "        .order_by(models.Episode.episode_number)\n"
        "        .all()\n"
        "    )\n"
    )
    if needle in src:
        repl = (
            "    base_q = (\n"
            "        db.query(models.Episode)\n"
            "        .filter(models.Episode.novel_id == novel_id)\n"
            "    )\n"
            "\n"
            "    if user and novel.author_id == user.id:\n"
            "        episodes = base_q.order_by(models.Episode.episode_number).all()\n"
            "    else:\n"
            "        episodes = (\n"
            "            base_q.filter(models.Episode.is_public == True)\n"
            "            .order_by(models.Episode.episode_number)\n"
            "            .all()\n"
            "        )\n"
        )
        src = src.replace(needle, repl, 1)
        print("[OK] added draft filter to list_episodes")
        changed = True
    else:
        print("[WARN] episodes query block not found in list_episodes")
else:
    print("[INFO] list_episodes base_q block already present (maybe already patched)")

# ---------- get_episode: 下書きエピソードは作者だけ ----------
if "下書きエピソードは作者だけ" not in src:
    needle = (
        "    # novel を取得（年齢制限のため）\n"
        "    novel = db.query(models.Novel).get(ep.novel_id)\n"
        "\n"
        "    # 年齢チェック\n"
    )
    if needle in src:
        repl = (
            "    # novel を取得（年齢制限のため）\n"
            "    novel = db.query(models.Novel).get(ep.novel_id)\n"
            "\n"
            "    # 下書きエピソードは作者だけ\n"
            "    try:\n"
            "        user = require_current_user(request, db)\n"
            "    except Exception:\n"
            "        user = None\n"
            "    if not ep.is_public:\n"
            "        if not user or (novel and novel.author_id != user.id):\n"
            "            raise HTTPException(404, \"エピソードが存在しません\")\n"
            "\n"
            "    # 年齢チェック\n"
        )
        src = src.replace(needle, repl, 1)
        print("[OK] added draft gate to get_episode")
        changed = True
    else:
        print("[WARN] get_episode novel/age block not found")

if changed:
    path.write_text(src, encoding="utf-8")
    print("[DONE] main.py patched")
else:
    print("[INFO] no changes applied (maybe already patched)")
