from functools import partial

from fastapi import Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext


def install_jst_json_encoder(
    *,
    fastapi_routing_module,
    fastapi_jsonable_encoder,
    datetime_cls,
    to_jst_isoformat,
):
    def _jsonable_encoder_with_jst(*args, **kwargs):
        custom = dict(kwargs.pop("custom_encoder", {}) or {})
        custom.setdefault(datetime_cls, to_jst_isoformat)
        return fastapi_jsonable_encoder(*args, custom_encoder=custom, **kwargs)

    fastapi_routing_module.jsonable_encoder = _jsonable_encoder_with_jst


def build_shared_runtime_exports(
    *,
    utcnow_impl,
    to_jst_isoformat_impl,
    display_payload_in_jst_impl,
    get_novel_char_counts_impl,
    apply_novel_daily_metric_impl,
    normalize_illust_tag_impl,
    normalize_meta_tags_impl,
    serialize_meta_tags_impl,
    deserialize_meta_tags_impl,
    normalize_language_impl,
    serialize_tag_names_impl,
    deserialize_tag_names_impl,
    normalize_translated_tags_impl,
):
    return {
        "utcnow": utcnow_impl,
        "to_jst_isoformat": to_jst_isoformat_impl,
        "display_payload_in_jst": display_payload_in_jst_impl,
        "get_novel_char_counts": get_novel_char_counts_impl,
        "apply_novel_daily_metric": apply_novel_daily_metric_impl,
        "normalize_illust_tag": normalize_illust_tag_impl,
        "normalize_meta_tags": normalize_meta_tags_impl,
        "serialize_meta_tags": serialize_meta_tags_impl,
        "deserialize_meta_tags": deserialize_meta_tags_impl,
        "normalize_language": normalize_language_impl,
        "serialize_tag_names": serialize_tag_names_impl,
        "deserialize_tag_names": deserialize_tag_names_impl,
        "normalize_translated_tags": normalize_translated_tags_impl,
    }


def build_core_runtime_exports(
    *,
    compact_text_impl,
    semantic_score_from_distance_impl,
    build_ai_novel_request_with_context_impl,
    collect_novel_feature_docs_impl,
    collect_user_preference_text_for_novels_impl,
    collect_public_chat_preference_text_impl,
    get_user_favorite_tag_weights,
    stripe_checkout_customer_kwargs_impl,
    create_checkout_session_with_customer_fallback_impl,
    stripe_module,
    normalize_site_key_impl,
    resolve_site_key_impl,
    get_novel_in_site_or_404_impl,
    get_episode_in_site_or_404_impl,
    get_or_create_tags_impl,
    normalize_tag_names_impl,
    truncate_text_impl,
    ai_weaviate_features_topk,
    ai_novel_request_cls,
    site_key_default,
    site_key_allowed,
    site_host_map,
    models,
    http_exception_cls,
    integrity_error_cls,
):
    _semantic_score_from_distance = semantic_score_from_distance_impl
    _compact_text = compact_text_impl
    _build_ai_novel_request_with_context = partial(
        build_ai_novel_request_with_context_impl,
        compact_text=_compact_text,
        ai_weaviate_features_topk=ai_weaviate_features_topk,
        ai_novel_request_cls=ai_novel_request_cls,
    )
    _collect_novel_feature_docs = partial(
        collect_novel_feature_docs_impl,
        models=models,
        compact_text=_compact_text,
    )
    _collect_user_preference_text_for_novels = partial(
        collect_user_preference_text_for_novels_impl,
        models=models,
        get_user_favorite_tag_weights=get_user_favorite_tag_weights,
        compact_text=_compact_text,
    )
    _collect_public_chat_preference_text = partial(
        collect_public_chat_preference_text_impl,
        models=models,
        compact_text=_compact_text,
    )
    _stripe_checkout_customer_kwargs = stripe_checkout_customer_kwargs_impl
    _create_checkout_session_with_customer_fallback = partial(
        create_checkout_session_with_customer_fallback_impl,
        stripe_module=stripe_module,
        checkout_customer_kwargs=_stripe_checkout_customer_kwargs,
    )
    normalize_site_key = partial(
        normalize_site_key_impl,
        site_key_default=site_key_default,
        site_key_allowed=site_key_allowed,
    )
    resolve_site_key = partial(
        resolve_site_key_impl,
        normalize_site_key=normalize_site_key,
        site_key_default=site_key_default,
        site_host_map=site_host_map,
    )
    get_novel_in_site_or_404 = partial(
        get_novel_in_site_or_404_impl,
        resolve_site_key=resolve_site_key,
        models=models,
        http_exception_cls=http_exception_cls,
    )
    get_episode_in_site_or_404 = partial(
        get_episode_in_site_or_404_impl,
        resolve_site_key=resolve_site_key,
        models=models,
        http_exception_cls=http_exception_cls,
    )
    _normalize_tag_names = normalize_tag_names_impl
    _get_or_create_tags = partial(
        get_or_create_tags_impl,
        normalize_tag_names=_normalize_tag_names,
        models=models,
        integrity_error_cls=integrity_error_cls,
    )
    _truncate_text = truncate_text_impl
    return {
        "_semantic_score_from_distance": _semantic_score_from_distance,
        "_compact_text": _compact_text,
        "_build_ai_novel_request_with_context": _build_ai_novel_request_with_context,
        "_collect_novel_feature_docs": _collect_novel_feature_docs,
        "_collect_user_preference_text_for_novels": _collect_user_preference_text_for_novels,
        "_collect_public_chat_preference_text": _collect_public_chat_preference_text,
        "_stripe_checkout_customer_kwargs": _stripe_checkout_customer_kwargs,
        "_create_checkout_session_with_customer_fallback": _create_checkout_session_with_customer_fallback,
        "normalize_site_key": normalize_site_key,
        "resolve_site_key": resolve_site_key,
        "get_novel_in_site_or_404": get_novel_in_site_or_404,
        "get_episode_in_site_or_404": get_episode_in_site_or_404,
        "_normalize_tag_names": _normalize_tag_names,
        "_get_or_create_tags": _get_or_create_tags,
        "_truncate_text": _truncate_text,
    }


def build_auth_runtime_exports(
    *,
    module_globals,
    get_db,
    jwt_module,
    stripe_module,
    html_response_cls=HTMLResponse,
    http_exception_cls=HTTPException,
    status_module=status,
    secret_key,
    algorithm,
    access_token_expire_minutes,
    password_reset_expire_minutes,
    register_email_verify_expire_minutes,
    oauth_state_expire_minutes,
    stripe_secret_key,
    platform_fee_rate,
    force_all_premium,
    force_premium_usernames,
    premium_revalidate_days,
    x_oauth_consumer_key,
    x_oauth_consumer_secret,
    backend_origin,
    frontend_origin,
    ai_chat_demo_bypass_username,
    ai_chat_premium_included_blocks,
    ai_chat_free_tokens,
    ai_chat_guest_tokens,
    ai_chat_block_tokens,
    ai_chat_block_price_yen,
    ai_novel_addon_unit_generations,
    ai_novel_addon_price_yen,
    ai_job_timeout_minutes,
    os_module,
    secrets_module,
    models,
    func,
    redis_json_get,
    cache_key_user_by_name,
    cache_user_payload,
    invalidate_user_cache,
    normalize_site_key,
    verify_password_impl,
    hash_password_impl,
    hash_reset_token_impl,
    normalize_email_impl,
    hash_register_email_code_impl,
    create_access_token_impl,
    build_pkce_pair_impl,
    build_oauth_state_impl,
    decode_oauth_state_impl,
    normalize_redirect_path_impl,
    generate_unique_username_impl,
    mark_oauth_code_used_impl,
    store_oauth1_request_token_impl,
    store_oauth1_completed_redirect_impl,
    peek_oauth1_completed_redirect_impl,
    pop_oauth1_request_token_impl,
    oauth1_build_auth_header_impl,
    oauth1_base_params_impl,
    stripe_obj_get_impl,
    stripe_subscription_is_active_impl,
    stripe_subscription_is_monthly_impl,
    find_active_monthly_subscription_by_email_impl,
    verify_premium_with_stripe_impl,
    cancel_stripe_subscription_for_admin_delete_impl,
    translation_author_is_premium_impl,
    can_translate_novel_impl,
    can_translate_episode_impl,
    revalidate_premium_on_login_impl,
    calc_platform_fee_impl,
    calc_author_share_impl,
    get_or_create_author_balance_impl,
    apply_author_balance_delta_impl,
    get_or_create_payout_profile_impl,
    parse_payout_period_impl,
    truncate_for_free_impl,
    is_jp_holiday_impl,
    is_free_reading_time_impl,
    get_episode_number_impl,
    set_episode_number_impl,
    get_user_by_username_impl,
    get_follow_counts_impl,
    is_following_user_impl,
    normalize_dm_pair_impl,
    require_current_user_impl,
    read_token_user_id_impl,
    record_user_view_history_impl,
    calc_age_impl,
    require_premium_user_impl,
    is_force_premium_username_impl,
    is_effective_premium_user_impl,
    assert_premium_user_impl,
    is_ai_chat_demo_bypass_user_impl,
    is_ai_chat_demo_bypass_username_impl,
    can_edit_ai_chat_character_impl,
    find_editable_ai_chat_character_impl,
    find_accessible_ai_chat_character_impl,
    compute_ai_chat_name_duplicate_index_impl,
    ai_chat_allowed_tokens_impl,
    current_ai_chat_month_key_utc_impl,
    sync_user_ai_chat_monthly_usage_impl,
    ensure_ai_chat_access_impl,
    ensure_ai_chat_guest_access_impl,
    record_ai_chat_tokens_impl,
    get_optional_current_user_impl,
    get_optional_current_user_soft_impl,
    get_or_set_ai_guest_id_impl,
    get_guest_ai_usage_impl,
    get_ai_chat_guest_usage_impl,
    require_guest_ai_quota_impl,
    check_ai_quota_impl,
    save_ai_log_impl,
    save_ai_novel_request_log_impl,
    request_origin_impl,
    oauth_redirect_uri_impl,
    oauth_frontend_url_impl,
    oauth_android_app_url_impl,
    oauth_result_url_impl,
    oauth_app_bridge_response_impl,
    is_android_app_oauth_start_impl,
    get_oauth_account_impl,
    get_or_create_user_from_oauth_impl,
):
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    admin_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

    verify_password = partial(verify_password_impl, pwd_context=pwd_context)
    hash_password = partial(hash_password_impl, pwd_context=pwd_context)
    _hash_reset_token = hash_reset_token_impl
    _normalize_email = normalize_email_impl
    _hash_register_email_code = partial(
        hash_register_email_code_impl,
        normalize_email=_normalize_email,
    )
    create_access_token = partial(
        create_access_token_impl,
        access_token_expire_minutes=access_token_expire_minutes,
        secret_key=secret_key,
        algorithm=algorithm,
        jwt_module=jwt_module,
    )
    _build_pkce_pair = build_pkce_pair_impl
    _build_oauth_state = partial(
        build_oauth_state_impl,
        oauth_state_expire_minutes=oauth_state_expire_minutes,
        secret_key=secret_key,
        algorithm=algorithm,
        jwt_module=jwt_module,
    )
    _decode_oauth_state = partial(
        decode_oauth_state_impl,
        secret_key=secret_key,
        algorithm=algorithm,
        jwt_module=jwt_module,
        invalid_state_error_factory=lambda: http_exception_cls(400, "OAuth state が不正です"),
    )
    _normalize_redirect_path = normalize_redirect_path_impl

    get_user_by_username = partial(
        get_user_by_username_impl,
        redis_json_get=redis_json_get,
        cache_key_user_by_name=cache_key_user_by_name,
        cache_user_payload=cache_user_payload,
        models=models,
    )

    _generate_unique_username = partial(
        generate_unique_username_impl,
        get_user_by_username=lambda db, username: get_user_by_username(db, username),
    )
    _mark_oauth_code_used = mark_oauth_code_used_impl
    _store_oauth1_request_token = store_oauth1_request_token_impl
    _store_oauth1_completed_redirect = store_oauth1_completed_redirect_impl
    _peek_oauth1_completed_redirect = peek_oauth1_completed_redirect_impl
    _pop_oauth1_request_token = pop_oauth1_request_token_impl
    _oauth1_build_auth_header = partial(
        oauth1_build_auth_header_impl,
        consumer_secret=x_oauth_consumer_secret,
    )
    _oauth1_base_params = partial(
        oauth1_base_params_impl,
        consumer_key=x_oauth_consumer_key,
    )
    _stripe_obj_get = stripe_obj_get_impl
    _stripe_subscription_is_active = stripe_subscription_is_active_impl
    _stripe_subscription_is_monthly = stripe_subscription_is_monthly_impl
    _find_active_monthly_subscription_by_email = partial(
        find_active_monthly_subscription_by_email_impl,
        stripe_module=stripe_module,
    )

    def verify_premium_with_stripe(user):
        return verify_premium_with_stripe_impl(
            user,
            stripe_secret_key=stripe_secret_key,
            stripe_module=stripe_module,
        )

    cancel_stripe_subscription_for_admin_delete = partial(
        cancel_stripe_subscription_for_admin_delete_impl,
        stripe_secret_key=stripe_secret_key,
        stripe_module=stripe_module,
        print_fn=print,
    )
    _is_force_premium_username = partial(
        is_force_premium_username_impl,
        force_premium_usernames=force_premium_usernames,
    )
    is_effective_premium_user = partial(
        is_effective_premium_user_impl,
        force_all_premium=force_all_premium,
        is_force_premium_username=_is_force_premium_username,
    )
    assert_premium_user = partial(
        assert_premium_user_impl,
        is_effective_premium_user=is_effective_premium_user,
        http_exception_cls=http_exception_cls,
    )
    _translation_author_is_premium = partial(
        translation_author_is_premium_impl,
        is_effective_premium_user=is_effective_premium_user,
        models=models,
    )
    _can_translate_novel = partial(
        can_translate_novel_impl,
        translation_author_is_premium=_translation_author_is_premium,
    )
    _can_translate_episode = partial(
        can_translate_episode_impl,
        can_translate_novel=_can_translate_novel,
        models=models,
    )

    def revalidate_premium_on_login(user, db):
        is_force_premium_username = module_globals.get(
            "_is_force_premium_username", _is_force_premium_username
        )
        verify_premium_with_stripe_fn = module_globals.get(
            "verify_premium_with_stripe", verify_premium_with_stripe
        )
        invalidate_user_cache_fn = module_globals.get(
            "invalidate_user_cache", invalidate_user_cache
        )
        cache_user_payload_fn = module_globals.get(
            "cache_user_payload", cache_user_payload
        )
        return revalidate_premium_on_login_impl(
            user,
            db,
            force_all_premium=force_all_premium,
            is_force_premium_username=is_force_premium_username,
            premium_revalidate_days=premium_revalidate_days,
            stripe_secret_key=stripe_secret_key,
            verify_premium_with_stripe=verify_premium_with_stripe_fn,
            invalidate_user_cache=invalidate_user_cache_fn,
            cache_user_payload=cache_user_payload_fn,
            print_fn=print,
        )

    calc_platform_fee = partial(calc_platform_fee_impl, platform_fee_rate=platform_fee_rate)
    calc_author_share = partial(calc_author_share_impl, calc_platform_fee=calc_platform_fee)
    get_or_create_author_balance = partial(get_or_create_author_balance_impl, models=models)
    apply_author_balance_delta = partial(
        apply_author_balance_delta_impl,
        get_or_create_author_balance=get_or_create_author_balance,
    )
    get_or_create_payout_profile = partial(get_or_create_payout_profile_impl, models=models)
    parse_payout_period = partial(parse_payout_period_impl, http_exception_cls=http_exception_cls)
    truncate_for_free = truncate_for_free_impl
    is_jp_holiday = is_jp_holiday_impl
    is_free_reading_time = partial(is_free_reading_time_impl, is_jp_holiday=is_jp_holiday)
    get_episode_number = get_episode_number_impl
    set_episode_number = set_episode_number_impl
    get_follow_counts = partial(get_follow_counts_impl, models=models, func=func)
    is_following_user = partial(is_following_user_impl, models=models)
    normalize_dm_pair = partial(normalize_dm_pair_impl, http_exception_cls=http_exception_cls)
    require_current_user = partial(
        require_current_user_impl,
        secret_key=secret_key,
        algorithm=algorithm,
        jwt_module=jwt_module,
        models=models,
        http_exception_cls=http_exception_cls,
    )
    _read_token_user_id = partial(
        read_token_user_id_impl,
        secret_key=secret_key,
        algorithm=algorithm,
        jwt_module=jwt_module,
        http_exception_cls=http_exception_cls,
    )
    record_user_view_history = partial(
        record_user_view_history_impl,
        normalize_site_key=normalize_site_key,
        models=models,
    )
    get_current_user = lambda request, db=Depends(get_db): require_current_user(request, db)
    calc_age = calc_age_impl
    require_premium_user = partial(
        require_premium_user_impl,
        require_current_user=require_current_user,
        is_effective_premium_user=is_effective_premium_user,
        http_exception_cls=http_exception_cls,
        payment_required_code=status_module.HTTP_402_PAYMENT_REQUIRED,
    )

    _is_ai_chat_demo_bypass_user = partial(
        is_ai_chat_demo_bypass_user_impl,
        ai_chat_demo_bypass_username=ai_chat_demo_bypass_username,
    )
    _is_ai_chat_demo_bypass_username = partial(
        is_ai_chat_demo_bypass_username_impl,
        ai_chat_demo_bypass_username=ai_chat_demo_bypass_username,
    )
    _can_edit_ai_chat_character = partial(
        can_edit_ai_chat_character_impl,
        is_ai_chat_demo_bypass_username=_is_ai_chat_demo_bypass_username,
        ai_chat_demo_bypass_username=ai_chat_demo_bypass_username,
        models_module=models,
        func_module=func,
    )
    _find_editable_ai_chat_character = partial(
        find_editable_ai_chat_character_impl,
        can_edit_ai_chat_character=_can_edit_ai_chat_character,
        models_module=models,
    )
    _find_accessible_ai_chat_character = partial(
        find_accessible_ai_chat_character_impl,
        can_edit_ai_chat_character=_can_edit_ai_chat_character,
        is_ai_chat_demo_bypass_user=_is_ai_chat_demo_bypass_user,
        models_module=models,
    )
    _compute_ai_chat_name_duplicate_index = partial(
        compute_ai_chat_name_duplicate_index_impl,
        models_module=models,
        func_module=func,
    )
    _ai_chat_allowed_tokens = partial(
        ai_chat_allowed_tokens_impl,
        is_effective_premium_user=is_effective_premium_user,
        ai_chat_premium_included_blocks=ai_chat_premium_included_blocks,
        ai_chat_free_tokens=ai_chat_free_tokens,
        ai_chat_block_tokens=ai_chat_block_tokens,
    )
    _current_ai_chat_month_key_utc = current_ai_chat_month_key_utc_impl
    _sync_user_ai_chat_monthly_usage = partial(
        sync_user_ai_chat_monthly_usage_impl,
        current_ai_chat_month_key_utc=_current_ai_chat_month_key_utc,
    )
    _ensure_ai_chat_access = partial(
        ensure_ai_chat_access_impl,
        is_ai_chat_demo_bypass_user=_is_ai_chat_demo_bypass_user,
        sync_user_ai_chat_monthly_usage=_sync_user_ai_chat_monthly_usage,
        is_effective_premium_user=is_effective_premium_user,
        ai_chat_allowed_tokens=_ai_chat_allowed_tokens,
        ai_chat_free_tokens=ai_chat_free_tokens,
        ai_chat_premium_included_blocks=ai_chat_premium_included_blocks,
        ai_chat_block_tokens=ai_chat_block_tokens,
        ai_chat_block_price_yen=ai_chat_block_price_yen,
        http_exception_cls=http_exception_cls,
        payment_required_code=status_module.HTTP_402_PAYMENT_REQUIRED,
    )
    _ensure_ai_chat_guest_access = partial(
        ensure_ai_chat_guest_access_impl,
        ai_chat_guest_tokens=ai_chat_guest_tokens,
        http_exception_cls=http_exception_cls,
        payment_required_code=status_module.HTTP_402_PAYMENT_REQUIRED,
    )
    _record_ai_chat_tokens = record_ai_chat_tokens_impl
    get_optional_current_user = get_optional_current_user_impl
    get_optional_current_user_soft = get_optional_current_user_soft_impl
    get_or_set_ai_guest_id = get_or_set_ai_guest_id_impl
    get_guest_ai_usage = get_guest_ai_usage_impl
    get_ai_chat_guest_usage = get_ai_chat_guest_usage_impl
    require_guest_ai_quota = require_guest_ai_quota_impl
    check_ai_quota = check_ai_quota_impl
    save_ai_log = save_ai_log_impl
    save_ai_novel_request_log = save_ai_novel_request_log_impl

    _request_origin = request_origin_impl
    _oauth_redirect_uri = partial(
        oauth_redirect_uri_impl,
        backend_origin=backend_origin,
        request_origin=_request_origin,
    )
    _oauth_frontend_url = partial(
        oauth_frontend_url_impl,
        request_origin=_request_origin,
        default_frontend_origin=frontend_origin,
    )
    _oauth_android_app_url = oauth_android_app_url_impl
    _oauth_result_url = partial(
        oauth_result_url_impl,
        oauth_android_app_url=_oauth_android_app_url,
        oauth_frontend_url=_oauth_frontend_url,
    )
    _oauth_app_bridge_response = partial(
        oauth_app_bridge_response_impl,
        oauth_android_app_url=_oauth_android_app_url,
        oauth_frontend_url=_oauth_frontend_url,
        html_response_cls=html_response_cls,
    )
    _is_android_app_oauth_start = is_android_app_oauth_start_impl
    _get_oauth_account = partial(get_oauth_account_impl, models_module=models)
    _get_or_create_user_from_oauth = partial(
        get_or_create_user_from_oauth_impl,
        get_oauth_account=_get_oauth_account,
        generate_unique_username=_generate_unique_username,
        hash_password=hash_password,
        models_module=models,
        secrets_module=secrets_module,
    )

    return {
        "pwd_context": pwd_context,
        "admin_pwd_context": admin_pwd_context,
        "oauth2_scheme": oauth2_scheme,
        "verify_password": verify_password,
        "hash_password": hash_password,
        "_hash_reset_token": _hash_reset_token,
        "_normalize_email": _normalize_email,
        "_hash_register_email_code": _hash_register_email_code,
        "create_access_token": create_access_token,
        "_build_pkce_pair": _build_pkce_pair,
        "_build_oauth_state": _build_oauth_state,
        "_decode_oauth_state": _decode_oauth_state,
        "_normalize_redirect_path": _normalize_redirect_path,
        "_generate_unique_username": _generate_unique_username,
        "_mark_oauth_code_used": _mark_oauth_code_used,
        "_store_oauth1_request_token": _store_oauth1_request_token,
        "_store_oauth1_completed_redirect": _store_oauth1_completed_redirect,
        "_peek_oauth1_completed_redirect": _peek_oauth1_completed_redirect,
        "_pop_oauth1_request_token": _pop_oauth1_request_token,
        "_oauth1_build_auth_header": _oauth1_build_auth_header,
        "_oauth1_base_params": _oauth1_base_params,
        "_stripe_obj_get": _stripe_obj_get,
        "_stripe_subscription_is_active": _stripe_subscription_is_active,
        "_stripe_subscription_is_monthly": _stripe_subscription_is_monthly,
        "_find_active_monthly_subscription_by_email": _find_active_monthly_subscription_by_email,
        "verify_premium_with_stripe": verify_premium_with_stripe,
        "cancel_stripe_subscription_for_admin_delete": cancel_stripe_subscription_for_admin_delete,
        "_is_force_premium_username": _is_force_premium_username,
        "is_effective_premium_user": is_effective_premium_user,
        "assert_premium_user": assert_premium_user,
        "_translation_author_is_premium": _translation_author_is_premium,
        "_can_translate_novel": _can_translate_novel,
        "_can_translate_episode": _can_translate_episode,
        "revalidate_premium_on_login": revalidate_premium_on_login,
        "calc_platform_fee": calc_platform_fee,
        "calc_author_share": calc_author_share,
        "get_or_create_author_balance": get_or_create_author_balance,
        "apply_author_balance_delta": apply_author_balance_delta,
        "get_or_create_payout_profile": get_or_create_payout_profile,
        "parse_payout_period": parse_payout_period,
        "truncate_for_free": truncate_for_free,
        "is_jp_holiday": is_jp_holiday,
        "is_free_reading_time": is_free_reading_time,
        "get_episode_number": get_episode_number,
        "set_episode_number": set_episode_number,
        "get_user_by_username": get_user_by_username,
        "get_follow_counts": get_follow_counts,
        "is_following_user": is_following_user,
        "normalize_dm_pair": normalize_dm_pair,
        "require_current_user": require_current_user,
        "_read_token_user_id": _read_token_user_id,
        "record_user_view_history": record_user_view_history,
        "get_current_user": get_current_user,
        "calc_age": calc_age,
        "require_premium_user": require_premium_user,
        "AI_GUEST_COOKIE_NAME": "ai_guest_id",
        "AI_GUEST_FREE_MAX": 10,
        "AI_USER_DAILY_MAX": 80,
        "AI_USER_DAILY_MAX_BY_USERNAME": {"demo02": 3000},
        "AI_USER_DAILY_MAX_BY_USERNAME_AND_DATE": {("demo02", "2026-04-19"): 1000},
        "AI_NOVEL_ADDON_UNIT_GENERATIONS": ai_novel_addon_unit_generations,
        "AI_NOVEL_ADDON_PRICE_YEN": ai_novel_addon_price_yen,
        "AI_JOB_TIMEOUT_MINUTES": ai_job_timeout_minutes,
        "_is_ai_chat_demo_bypass_user": _is_ai_chat_demo_bypass_user,
        "_is_ai_chat_demo_bypass_username": _is_ai_chat_demo_bypass_username,
        "_can_edit_ai_chat_character": _can_edit_ai_chat_character,
        "_find_editable_ai_chat_character": _find_editable_ai_chat_character,
        "_find_accessible_ai_chat_character": _find_accessible_ai_chat_character,
        "_compute_ai_chat_name_duplicate_index": _compute_ai_chat_name_duplicate_index,
        "_ai_chat_allowed_tokens": _ai_chat_allowed_tokens,
        "_current_ai_chat_month_key_utc": _current_ai_chat_month_key_utc,
        "_sync_user_ai_chat_monthly_usage": _sync_user_ai_chat_monthly_usage,
        "_ensure_ai_chat_access": _ensure_ai_chat_access,
        "_ensure_ai_chat_guest_access": _ensure_ai_chat_guest_access,
        "_record_ai_chat_tokens": _record_ai_chat_tokens,
        "get_optional_current_user": get_optional_current_user,
        "get_optional_current_user_soft": get_optional_current_user_soft,
        "get_or_set_ai_guest_id": get_or_set_ai_guest_id,
        "get_guest_ai_usage": get_guest_ai_usage,
        "get_ai_chat_guest_usage": get_ai_chat_guest_usage,
        "require_guest_ai_quota": require_guest_ai_quota,
        "check_ai_quota": check_ai_quota,
        "save_ai_log": save_ai_log,
        "save_ai_novel_request_log": save_ai_novel_request_log,
        "_request_origin": _request_origin,
        "_oauth_redirect_uri": _oauth_redirect_uri,
        "_oauth_frontend_url": _oauth_frontend_url,
        "_oauth_android_app_url": _oauth_android_app_url,
        "_oauth_result_url": _oauth_result_url,
        "_oauth_app_bridge_response": _oauth_app_bridge_response,
        "_is_android_app_oauth_start": _is_android_app_oauth_start,
        "_get_oauth_account": _get_oauth_account,
        "_get_or_create_user_from_oauth": _get_or_create_user_from_oauth,
        "PASSWORD_RESET_EXPIRE_MINUTES": password_reset_expire_minutes,
        "REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES": register_email_verify_expire_minutes,
    }


def build_ai_runtime_exports(
    *,
    re_module,
    os_module,
    httpx_module,
    urljoin_fn,
    urlparse_fn,
    image_ops,
    pil_available,
    static_dir,
    logger,
    models,
    func,
    retrieve_memories,
    resolve_memory_scope,
    format_long_term_memories,
    build_layered_context_block,
    ai_chat_memory_topk,
    ai_chat_text_timeout_seconds,
    ai_chat_temperature,
    ai_chat_top_p,
    ai_chat_image_timeout_sec,
    ai_chat_image_caption_enabled,
    ai_chat_image_caption_model,
    ai_chat_image_caption_max_output_tokens,
    ai_chat_image_message_prefix,
    provider_from_model,
    assert_openrouter_model_allowed_for_pricing,
    call_ai_json,
    ai_chat_history_item_cls,
    ai_chat_image_item_cls,
    secrets_module,
    get_novel_tag_names_impl,
    get_episode_tag_names_impl,
    format_ai_log_model_impl,
    normalize_speech_gender_impl,
    serialize_ai_response_impl,
    extract_retry_max_from_request_json_impl,
    normalize_chunked_generation_payload_impl,
    build_chunked_novel_prompt_impl,
    build_chunked_job_response_impl,
    count_ai_jobs_today_impl,
    count_ai_usage_today_impl,
    ai_novel_paid_remaining_impl,
    ai_novel_daily_max_for_user_impl,
    ai_novel_remaining_for_user_impl,
    reserve_ai_novel_generation_slot_impl,
    is_ai_job_expired_impl,
    kill_expired_ai_jobs_impl,
    should_retry_ai_error_impl,
    is_empty_ai_response_error_impl,
    call_ai_with_retry_impl,
    call_ai_with_retry_prompt_impl,
    notify_ai_job_user_impl,
    run_ai_job_impl,
    build_ai_chat_style_guide_impl,
    build_ai_chat_content_safety_rules_impl,
    build_ai_chat_system_instructions_impl,
    normalize_chat_text_for_match_impl,
    build_ai_chat_branching_instruction_impl,
    build_ai_chat_variation_instruction_impl,
    score_ai_chat_followup_latency_impl,
    clip01_impl,
    build_ai_chat_profile_key_impl,
    calc_user_personalization_weight_impl,
    update_profile_learning_stats_impl,
    normalized_keyword_score_impl,
    extract_personality_keywords_impl,
    estimate_ai_reply_scores_impl,
    estimate_user_followup_signal_scores_impl,
    record_ai_chat_followup_feedback_impl,
    build_ai_chat_engagement_learning_instruction_impl,
    build_ai_chat_recommendation_map_impl,
    build_public_profile_recommendation_map_impl,
    build_relationship_tone_rules_impl,
    build_multi_character_relationship_rules_impl,
    normalize_language_style_impl,
    build_language_style_rules_impl,
    looks_like_fictional_character_name_impl,
    long_reply_min_chars_impl,
    normalize_ai_chat_model_alias_impl,
    resolve_ai_chat_provider_impl,
    ai_chat_provider_candidates_impl,
    default_ai_chat_openrouter_model_impl,
    default_ai_chat_deepseek_model_impl,
    resolve_ai_chat_candidate_model_impl,
    call_ai_chat_json_with_fallback_impl,
    regenerate_long_reply_if_needed_impl,
    regenerate_auto_dialogue_if_needed_impl,
    build_ai_chat_history_text_impl,
    build_ai_chat_history_lines_impl,
    collect_ai_chat_backfill_turns_impl,
    build_ai_chat_prompt_impl,
    build_auto_dialogue_prompt_impl,
    build_ai_chat_next_line_suggest_prompt_impl,
    fallback_next_line_suggestions_impl,
    normalize_next_line_suggestion_impl,
    normalize_ai_chat_image_url_impl,
    extract_error_detail_from_response_impl,
    extract_session_token_from_payload_impl,
    serialize_ai_chat_image_message_impl,
    parse_ai_chat_image_message_impl,
    local_static_path_from_url_impl,
    build_data_url_from_local_image_impl,
    extract_image_field_from_payload_impl,
    read_secret_from_env_or_file_impl,
    extract_openai_responses_output_text_impl,
    describe_uploaded_chat_images_impl,
    resolve_image_to_data_url_impl,
    extract_background_place_prompt_impl,
    extract_ai_chat_images_from_generate_data_impl,
    score_ai_chat_image_quality_impl,
):
    _format_ai_log_model = format_ai_log_model_impl
    normalize_speech_gender = normalize_speech_gender_impl
    _serialize_ai_response = serialize_ai_response_impl
    _extract_retry_max_from_request_json = extract_retry_max_from_request_json_impl
    _normalize_chunked_generation_payload = normalize_chunked_generation_payload_impl
    _build_chunked_novel_prompt = build_chunked_novel_prompt_impl
    _build_chunked_job_response = build_chunked_job_response_impl
    _count_ai_jobs_today = count_ai_jobs_today_impl
    _count_ai_usage_today = count_ai_usage_today_impl
    _ai_novel_paid_remaining = ai_novel_paid_remaining_impl
    _ai_novel_daily_max_for_user = ai_novel_daily_max_for_user_impl
    _ai_novel_remaining_for_user = ai_novel_remaining_for_user_impl
    _reserve_ai_novel_generation_slot = reserve_ai_novel_generation_slot_impl
    _is_ai_job_expired = is_ai_job_expired_impl
    _kill_expired_ai_jobs = kill_expired_ai_jobs_impl
    _should_retry_ai_error = should_retry_ai_error_impl
    _is_empty_ai_response_error = is_empty_ai_response_error_impl
    _call_ai_with_retry = call_ai_with_retry_impl
    _call_ai_with_retry_prompt = call_ai_with_retry_prompt_impl
    _notify_ai_job_user = partial(notify_ai_job_user_impl, print_fn=print)
    _run_ai_job = run_ai_job_impl
    _build_ai_chat_style_guide = build_ai_chat_style_guide_impl
    _build_ai_chat_content_safety_rules = build_ai_chat_content_safety_rules_impl
    _build_ai_chat_system_instructions = partial(
        build_ai_chat_system_instructions_impl,
        build_ai_chat_content_safety_rules=_build_ai_chat_content_safety_rules,
    )
    _normalize_chat_text_for_match = partial(normalize_chat_text_for_match_impl, re_module=re_module)
    _build_ai_chat_branching_instruction = partial(
        build_ai_chat_branching_instruction_impl,
        normalize_chat_text_for_match=_normalize_chat_text_for_match,
    )
    _build_ai_chat_variation_instruction = partial(
        build_ai_chat_variation_instruction_impl,
        secrets_module=secrets_module,
    )
    _score_ai_chat_followup_latency = score_ai_chat_followup_latency_impl
    _clip01 = clip01_impl
    _build_ai_chat_profile_key = partial(
        build_ai_chat_profile_key_impl,
        normalize_speech_gender=normalize_speech_gender,
    )
    _calc_user_personalization_weight = calc_user_personalization_weight_impl
    _update_profile_learning_stats = partial(update_profile_learning_stats_impl, models=models)
    _normalized_keyword_score = partial(
        normalized_keyword_score_impl,
        clip01=_clip01,
    )
    _extract_personality_keywords = partial(extract_personality_keywords_impl, re_module=re_module)
    _estimate_ai_reply_scores = partial(
        estimate_ai_reply_scores_impl,
        clip01=_clip01,
        normalized_keyword_score=_normalized_keyword_score,
        extract_personality_keywords=_extract_personality_keywords,
        re_module=re_module,
    )
    _estimate_user_followup_signal_scores = partial(
        estimate_user_followup_signal_scores_impl,
        normalized_keyword_score=_normalized_keyword_score,
        clip01=_clip01,
    )
    _record_ai_chat_followup_feedback = partial(
        record_ai_chat_followup_feedback_impl,
        models=models,
        score_ai_chat_followup_latency=_score_ai_chat_followup_latency,
        estimate_ai_reply_scores=_estimate_ai_reply_scores,
        estimate_user_followup_signal_scores=_estimate_user_followup_signal_scores,
        clip01=_clip01,
        update_profile_learning_stats=_update_profile_learning_stats,
    )
    _build_ai_chat_engagement_learning_instruction = partial(
        build_ai_chat_engagement_learning_instruction_impl,
        models=models,
        build_ai_chat_profile_key=_build_ai_chat_profile_key,
        calc_user_personalization_weight=_calc_user_personalization_weight,
        clip01=_clip01,
        normalize_speech_gender=normalize_speech_gender,
        retrieve_memories=retrieve_memories,
        resolve_memory_scope=resolve_memory_scope,
        format_long_term_memories=format_long_term_memories,
        ai_chat_memory_topk=ai_chat_memory_topk,
        re_module=re_module,
    )
    _build_ai_chat_recommendation_map = partial(
        build_ai_chat_recommendation_map_impl,
        models=models,
        func=func,
        build_ai_chat_profile_key=_build_ai_chat_profile_key,
        calc_user_personalization_weight=_calc_user_personalization_weight,
        clip01=_clip01,
    )
    _build_public_profile_recommendation_map = partial(
        build_public_profile_recommendation_map_impl,
        models=models,
        clip01=_clip01,
    )
    _build_relationship_tone_rules = build_relationship_tone_rules_impl
    _build_multi_character_relationship_rules = build_multi_character_relationship_rules_impl
    _normalize_language_style = normalize_language_style_impl
    _build_language_style_rules = partial(
        build_language_style_rules_impl,
        normalize_language_style=_normalize_language_style,
    )
    _looks_like_fictional_character_name = partial(
        looks_like_fictional_character_name_impl,
        re_module=re_module,
    )
    _long_reply_min_chars = long_reply_min_chars_impl
    _normalize_ai_chat_model_alias = normalize_ai_chat_model_alias_impl
    _resolve_ai_chat_provider = partial(
        resolve_ai_chat_provider_impl,
        provider_from_model=provider_from_model,
    )
    _ai_chat_provider_candidates = partial(
        ai_chat_provider_candidates_impl,
        resolve_ai_chat_provider=_resolve_ai_chat_provider,
    )
    _default_ai_chat_openrouter_model = partial(
        default_ai_chat_openrouter_model_impl,
        os_module=os_module,
    )
    _default_ai_chat_deepseek_model = partial(
        default_ai_chat_deepseek_model_impl,
        os_module=os_module,
    )
    _resolve_ai_chat_candidate_model = partial(
        resolve_ai_chat_candidate_model_impl,
        default_ai_chat_openrouter_model=_default_ai_chat_openrouter_model,
        default_ai_chat_deepseek_model=_default_ai_chat_deepseek_model,
    )
    _call_ai_chat_json_with_fallback = partial(
        call_ai_chat_json_with_fallback_impl,
        normalize_ai_chat_model_alias=_normalize_ai_chat_model_alias,
        resolve_ai_chat_provider=_resolve_ai_chat_provider,
        assert_openrouter_model_allowed_for_pricing=assert_openrouter_model_allowed_for_pricing,
        ai_chat_provider_candidates=_ai_chat_provider_candidates,
        resolve_ai_chat_candidate_model=_resolve_ai_chat_candidate_model,
        call_ai_json=call_ai_json,
        ai_chat_text_timeout_seconds=ai_chat_text_timeout_seconds,
        ai_chat_temperature=ai_chat_temperature,
        ai_chat_top_p=ai_chat_top_p,
        http_exception_cls=HTTPException,
        logger=logger,
    )
    _build_ai_chat_prompt = partial(
        build_ai_chat_prompt_impl,
        build_ai_chat_style_guide=_build_ai_chat_style_guide,
        build_relationship_tone_rules=_build_relationship_tone_rules,
        build_multi_character_relationship_rules=_build_multi_character_relationship_rules,
        build_ai_chat_content_safety_rules=_build_ai_chat_content_safety_rules,
        build_layered_context_block=build_layered_context_block,
    )
    _build_auto_dialogue_prompt = partial(
        build_auto_dialogue_prompt_impl,
        build_ai_chat_content_safety_rules=_build_ai_chat_content_safety_rules,
        build_layered_context_block=build_layered_context_block,
    )
    _regenerate_long_reply_if_needed = partial(
        regenerate_long_reply_if_needed_impl,
        long_reply_min_chars=_long_reply_min_chars,
        build_ai_chat_prompt=lambda **kwargs: _build_ai_chat_prompt(**kwargs),
        call_ai_chat_json_with_fallback=_call_ai_chat_json_with_fallback,
        build_ai_chat_system_instructions=_build_ai_chat_system_instructions,
    )
    _regenerate_auto_dialogue_if_needed = partial(
        regenerate_auto_dialogue_if_needed_impl,
        long_reply_min_chars=_long_reply_min_chars,
        build_auto_dialogue_prompt=lambda **kwargs: _build_auto_dialogue_prompt(**kwargs),
        call_ai_chat_json_with_fallback=_call_ai_chat_json_with_fallback,
        build_ai_chat_content_safety_rules=_build_ai_chat_content_safety_rules,
    )
    _build_ai_chat_history_text = build_ai_chat_history_text_impl
    _build_ai_chat_history_lines = build_ai_chat_history_lines_impl
    _build_ai_chat_next_line_suggest_prompt = partial(
        build_ai_chat_next_line_suggest_prompt_impl,
        build_ai_chat_content_safety_rules=_build_ai_chat_content_safety_rules,
        build_layered_context_block=build_layered_context_block,
    )
    _fallback_next_line_suggestions = fallback_next_line_suggestions_impl
    _normalize_next_line_suggestion = partial(normalize_next_line_suggestion_impl, re_module=re_module)
    _normalize_ai_chat_image_url = normalize_ai_chat_image_url_impl
    _extract_error_detail_from_response = extract_error_detail_from_response_impl
    _extract_session_token_from_payload = extract_session_token_from_payload_impl
    _serialize_ai_chat_image_message = partial(
        serialize_ai_chat_image_message_impl,
        ai_chat_image_message_prefix=ai_chat_image_message_prefix,
    )
    _parse_ai_chat_image_message = partial(
        parse_ai_chat_image_message_impl,
        ai_chat_image_message_prefix=ai_chat_image_message_prefix,
    )
    _local_static_path_from_url = partial(
        local_static_path_from_url_impl,
        static_dir=static_dir,
        os_module=os_module,
    )
    _build_data_url_from_local_image = build_data_url_from_local_image_impl
    _extract_image_field_from_payload = extract_image_field_from_payload_impl
    _read_secret_from_env_or_file = partial(
        read_secret_from_env_or_file_impl,
        os_module=os_module,
    )
    _extract_openai_responses_output_text = extract_openai_responses_output_text_impl
    _describe_uploaded_chat_images = partial(
        describe_uploaded_chat_images_impl,
        ai_chat_image_caption_enabled=ai_chat_image_caption_enabled,
        read_secret_from_env_or_file=_read_secret_from_env_or_file,
        local_static_path_from_url=_local_static_path_from_url,
        build_data_url_from_local_image=_build_data_url_from_local_image,
        extract_openai_responses_output_text=_extract_openai_responses_output_text,
        ai_chat_image_caption_model=ai_chat_image_caption_model,
        ai_chat_image_caption_max_output_tokens=ai_chat_image_caption_max_output_tokens,
        httpx_module=httpx_module,
    )
    _resolve_image_to_data_url = partial(resolve_image_to_data_url_impl, urljoin_fn=urljoin_fn)
    _extract_background_place_prompt = partial(extract_background_place_prompt_impl, re_module=re_module)
    _extract_ai_chat_images_from_generate_data = partial(
        extract_ai_chat_images_from_generate_data_impl,
        normalize_ai_chat_image_url=_normalize_ai_chat_image_url,
        image_item_cls=ai_chat_image_item_cls,
        urlparse_fn=urlparse_fn,
    )
    _score_ai_chat_image_quality = partial(
        score_ai_chat_image_quality_impl,
        pil_available=pil_available,
        ai_chat_image_timeout_sec=ai_chat_image_timeout_sec,
        httpx_module=httpx_module,
        image_ops=image_ops,
    )
    _collect_ai_chat_backfill_turns = lambda *, messages, character_name, max_turns: collect_ai_chat_backfill_turns_impl(
        messages=messages,
        character_name=character_name,
        max_turns=max_turns,
        parse_ai_chat_image_message=_parse_ai_chat_image_message,
        history_item_cls=ai_chat_history_item_cls,
        build_ai_chat_history_lines=_build_ai_chat_history_lines,
    )

    return {
        "_format_ai_log_model": _format_ai_log_model,
        "normalize_speech_gender": normalize_speech_gender,
        "_serialize_ai_response": _serialize_ai_response,
        "_extract_retry_max_from_request_json": _extract_retry_max_from_request_json,
        "_normalize_chunked_generation_payload": _normalize_chunked_generation_payload,
        "_build_chunked_novel_prompt": _build_chunked_novel_prompt,
        "_build_chunked_job_response": _build_chunked_job_response,
        "_count_ai_jobs_today": _count_ai_jobs_today,
        "_count_ai_usage_today": _count_ai_usage_today,
        "_ai_novel_paid_remaining": _ai_novel_paid_remaining,
        "_ai_novel_daily_max_for_user": _ai_novel_daily_max_for_user,
        "_ai_novel_remaining_for_user": _ai_novel_remaining_for_user,
        "_reserve_ai_novel_generation_slot": _reserve_ai_novel_generation_slot,
        "_is_ai_job_expired": _is_ai_job_expired,
        "_kill_expired_ai_jobs": _kill_expired_ai_jobs,
        "_should_retry_ai_error": _should_retry_ai_error,
        "_is_empty_ai_response_error": _is_empty_ai_response_error,
        "_call_ai_with_retry": _call_ai_with_retry,
        "_call_ai_with_retry_prompt": _call_ai_with_retry_prompt,
        "_notify_ai_job_user": _notify_ai_job_user,
        "_run_ai_job": _run_ai_job,
        "_build_ai_chat_style_guide": _build_ai_chat_style_guide,
        "_build_ai_chat_content_safety_rules": _build_ai_chat_content_safety_rules,
        "_build_ai_chat_system_instructions": _build_ai_chat_system_instructions,
        "_normalize_chat_text_for_match": _normalize_chat_text_for_match,
        "_build_ai_chat_branching_instruction": _build_ai_chat_branching_instruction,
        "_build_ai_chat_variation_instruction": _build_ai_chat_variation_instruction,
        "_score_ai_chat_followup_latency": _score_ai_chat_followup_latency,
        "_clip01": _clip01,
        "_build_ai_chat_profile_key": _build_ai_chat_profile_key,
        "_calc_user_personalization_weight": _calc_user_personalization_weight,
        "_update_profile_learning_stats": _update_profile_learning_stats,
        "_normalized_keyword_score": _normalized_keyword_score,
        "_extract_personality_keywords": _extract_personality_keywords,
        "_estimate_ai_reply_scores": _estimate_ai_reply_scores,
        "_estimate_user_followup_signal_scores": _estimate_user_followup_signal_scores,
        "_record_ai_chat_followup_feedback": _record_ai_chat_followup_feedback,
        "_build_ai_chat_engagement_learning_instruction": _build_ai_chat_engagement_learning_instruction,
        "_build_ai_chat_recommendation_map": _build_ai_chat_recommendation_map,
        "_build_public_profile_recommendation_map": _build_public_profile_recommendation_map,
        "_build_relationship_tone_rules": _build_relationship_tone_rules,
        "_build_multi_character_relationship_rules": _build_multi_character_relationship_rules,
        "_normalize_language_style": _normalize_language_style,
        "_build_language_style_rules": _build_language_style_rules,
        "_looks_like_fictional_character_name": _looks_like_fictional_character_name,
        "_long_reply_min_chars": _long_reply_min_chars,
        "_normalize_ai_chat_model_alias": _normalize_ai_chat_model_alias,
        "_resolve_ai_chat_provider": _resolve_ai_chat_provider,
        "_ai_chat_provider_candidates": _ai_chat_provider_candidates,
        "_default_ai_chat_openrouter_model": _default_ai_chat_openrouter_model,
        "_default_ai_chat_deepseek_model": _default_ai_chat_deepseek_model,
        "_resolve_ai_chat_candidate_model": _resolve_ai_chat_candidate_model,
        "_call_ai_chat_json_with_fallback": _call_ai_chat_json_with_fallback,
        "_regenerate_long_reply_if_needed": _regenerate_long_reply_if_needed,
        "_regenerate_auto_dialogue_if_needed": _regenerate_auto_dialogue_if_needed,
        "_build_ai_chat_history_text": _build_ai_chat_history_text,
        "_build_ai_chat_history_lines": _build_ai_chat_history_lines,
        "_collect_ai_chat_backfill_turns": _collect_ai_chat_backfill_turns,
        "_build_ai_chat_prompt": _build_ai_chat_prompt,
        "_build_auto_dialogue_prompt": _build_auto_dialogue_prompt,
        "_build_ai_chat_next_line_suggest_prompt": _build_ai_chat_next_line_suggest_prompt,
        "_fallback_next_line_suggestions": _fallback_next_line_suggestions,
        "_normalize_next_line_suggestion": _normalize_next_line_suggestion,
        "_normalize_ai_chat_image_url": _normalize_ai_chat_image_url,
        "_extract_error_detail_from_response": _extract_error_detail_from_response,
        "_extract_session_token_from_payload": _extract_session_token_from_payload,
        "_serialize_ai_chat_image_message": _serialize_ai_chat_image_message,
        "_parse_ai_chat_image_message": _parse_ai_chat_image_message,
        "_local_static_path_from_url": _local_static_path_from_url,
        "_build_data_url_from_local_image": _build_data_url_from_local_image,
        "_extract_image_field_from_payload": _extract_image_field_from_payload,
        "_read_secret_from_env_or_file": _read_secret_from_env_or_file,
        "_extract_openai_responses_output_text": _extract_openai_responses_output_text,
        "_describe_uploaded_chat_images": _describe_uploaded_chat_images,
        "_resolve_image_to_data_url": _resolve_image_to_data_url,
        "_extract_background_place_prompt": _extract_background_place_prompt,
        "_extract_ai_chat_images_from_generate_data": _extract_ai_chat_images_from_generate_data,
        "_score_ai_chat_image_quality": _score_ai_chat_image_quality,
        "get_novel_tag_names": get_novel_tag_names_impl,
        "get_episode_tag_names": get_episode_tag_names_impl,
    }


def build_translation_runtime_exports(
    *,
    translation_target_languages_impl,
    novel_translation_original_only,
    novel_translation_ja_en_only,
    novel_translation_all_languages,
    has_recent_multilingual_ready_notification_impl,
    is_novel_translation_complete_impl,
    is_episode_translation_complete_impl,
    notify_multilingual_ready_for_novel_impl,
    notify_multilingual_ready_for_episode_impl,
    run_daily_translation_bot_once_impl,
    daily_translation_bot_loop_impl,
    start_daily_translation_bot_if_enabled_impl,
    run_monthly_stripe_premium_sync_once_impl,
    monthly_stripe_premium_sync_loop_impl,
    start_monthly_stripe_premium_sync_if_enabled_impl,
    background_upsert_episode_translation_impl,
    background_upsert_episode_and_novel_translation_impl,
    background_upsert_novel_translation_impl,
    should_enqueue_feed_novel_translation_impl,
    resolve_public_novel_card_translations_impl,
    background_notify_episode_published_impl,
    session_local,
    models,
    logger,
    deserialize_tag_names,
    get_episode_tag_names_impl,
    create_notification,
    daily_translation_bot_only_public,
    daily_translation_bot_site_key,
    daily_translation_bot_max_novels,
    daily_translation_bot_max_episodes,
    can_translate_novel,
    can_translate_episode,
    normalize_language,
    get_novel_tag_names_impl,
    upsert_novel_translation,
    upsert_episode_translation,
    is_episode_draft,
    daily_translation_bot_interval_seconds,
    time_module,
    threading_module,
    daily_translation_bot_enabled,
    stripe_secret_key,
    find_active_monthly_subscription_by_email,
    is_ai_chat_demo_bypass_user,
    is_force_premium_username,
    func,
    monthly_stripe_premium_sync_day,
    monthly_stripe_premium_sync_hour_utc,
    monthly_stripe_premium_sync_interval_seconds,
    datetime_module,
    monthly_stripe_premium_sync_enabled,
):
    def translation_target_languages(source_language: str) -> list[str]:
        return translation_target_languages_impl(
            source_language,
            novel_translation_original_only=novel_translation_original_only,
            novel_translation_ja_en_only=novel_translation_ja_en_only,
            novel_translation_all_languages=novel_translation_all_languages,
        )

    _has_recent_multilingual_ready_notification = partial(
        has_recent_multilingual_ready_notification_impl,
        models=models,
    )
    _is_novel_translation_complete = partial(
        is_novel_translation_complete_impl,
        translation_target_languages=translation_target_languages,
        models=models,
    )
    _is_episode_translation_complete = partial(
        is_episode_translation_complete_impl,
        translation_target_languages=translation_target_languages,
        deserialize_tag_names=deserialize_tag_names,
        get_episode_tag_names=lambda db, episode_id: get_episode_tag_names_impl(db, episode_id),
        models=models,
    )
    _notify_multilingual_ready_for_novel = partial(
        notify_multilingual_ready_for_novel_impl,
        is_novel_translation_complete=_is_novel_translation_complete,
        has_recent_multilingual_ready_notification=_has_recent_multilingual_ready_notification,
        create_notification=create_notification,
    )
    _notify_multilingual_ready_for_episode = partial(
        notify_multilingual_ready_for_episode_impl,
        is_episode_translation_complete=_is_episode_translation_complete,
        has_recent_multilingual_ready_notification=_has_recent_multilingual_ready_notification,
        create_notification=create_notification,
        models=models,
    )
    _run_daily_translation_bot_once = partial(
        run_daily_translation_bot_once_impl,
        session_local=session_local,
        models=models,
        daily_translation_bot_only_public=daily_translation_bot_only_public,
        daily_translation_bot_site_key=daily_translation_bot_site_key,
        daily_translation_bot_max_novels=daily_translation_bot_max_novels,
        daily_translation_bot_max_episodes=daily_translation_bot_max_episodes,
        can_translate_novel=lambda db, *, novel: can_translate_novel(db, novel=novel),
        can_translate_episode=lambda db, *, episode: can_translate_episode(db, episode=episode),
        is_novel_translation_complete=_is_novel_translation_complete,
        is_episode_translation_complete=_is_episode_translation_complete,
        normalize_language=normalize_language,
        get_novel_tag_names=lambda db, novel_id: get_novel_tag_names_impl(db, novel_id),
        upsert_novel_translation=upsert_novel_translation,
        upsert_episode_translation=upsert_episode_translation,
        is_episode_draft=is_episode_draft,
        logger=logger,
    )
    _daily_translation_bot_loop = partial(
        daily_translation_bot_loop_impl,
        run_daily_translation_bot_once=_run_daily_translation_bot_once,
        logger=logger,
        interval_seconds=daily_translation_bot_interval_seconds,
        time_module=time_module,
    )
    _start_daily_translation_bot_if_enabled = partial(
        start_daily_translation_bot_if_enabled_impl,
        enabled=daily_translation_bot_enabled,
        threading_module=threading_module,
        target=_daily_translation_bot_loop,
        logger=logger,
        interval_seconds=daily_translation_bot_interval_seconds,
        max_novels=daily_translation_bot_max_novels,
        max_episodes=daily_translation_bot_max_episodes,
    )
    _run_monthly_stripe_premium_sync_once = partial(
        run_monthly_stripe_premium_sync_once_impl,
        stripe_secret_key=stripe_secret_key,
        session_local=session_local,
        models=models,
        find_active_monthly_subscription_by_email=lambda email: find_active_monthly_subscription_by_email(email),
        is_ai_chat_demo_bypass_user=lambda user: is_ai_chat_demo_bypass_user(user),
        is_force_premium_username=lambda username: is_force_premium_username(username),
        logger=logger,
        user_email_query_filter=lambda q: q.filter(func.length(func.trim(models.User.email)) > 0),
    )
    _monthly_stripe_premium_sync_loop = partial(
        monthly_stripe_premium_sync_loop_impl,
        run_monthly_stripe_premium_sync_once=_run_monthly_stripe_premium_sync_once,
        logger=logger,
        sync_day=monthly_stripe_premium_sync_day,
        sync_hour_utc=monthly_stripe_premium_sync_hour_utc,
        interval_seconds=monthly_stripe_premium_sync_interval_seconds,
        time_module=time_module,
        datetime_module=datetime_module,
    )
    _start_monthly_stripe_premium_sync_if_enabled = partial(
        start_monthly_stripe_premium_sync_if_enabled_impl,
        enabled=monthly_stripe_premium_sync_enabled,
        threading_module=threading_module,
        target=_monthly_stripe_premium_sync_loop,
        logger=logger,
        interval_seconds=monthly_stripe_premium_sync_interval_seconds,
        sync_day=monthly_stripe_premium_sync_day,
        sync_hour_utc=monthly_stripe_premium_sync_hour_utc,
    )
    _background_upsert_episode_translation = partial(
        background_upsert_episode_translation_impl,
        session_local=session_local,
        models=models,
        normalize_language=normalize_language,
        upsert_episode_translation=upsert_episode_translation,
        logger=logger,
    )
    _background_upsert_episode_and_novel_translation = partial(
        background_upsert_episode_and_novel_translation_impl,
        session_local=session_local,
        models=models,
        normalize_language=normalize_language,
        upsert_episode_translation=upsert_episode_translation,
        upsert_novel_translation=upsert_novel_translation,
        get_novel_tag_names=lambda db, novel_id: get_novel_tag_names_impl(db, novel_id),
        logger=logger,
    )
    _background_upsert_novel_translation = partial(
        background_upsert_novel_translation_impl,
        session_local=session_local,
        models=models,
        normalize_language=normalize_language,
        get_novel_tag_names=lambda db, novel_id: get_novel_tag_names_impl(db, novel_id),
        upsert_novel_translation=upsert_novel_translation,
        logger=logger,
    )
    _should_enqueue_feed_novel_translation = should_enqueue_feed_novel_translation_impl
    _resolve_public_novel_card_translations = partial(
        resolve_public_novel_card_translations_impl,
        normalize_language=normalize_language,
        translation_target_languages=translation_target_languages,
        deserialize_tag_names=deserialize_tag_names,
        can_translate_novel=lambda db, *, novel: can_translate_novel(db, novel=novel),
        should_enqueue_feed_novel_translation=_should_enqueue_feed_novel_translation,
        background_upsert_novel_translation=_background_upsert_novel_translation,
        models=models,
    )
    _background_notify_episode_published = partial(
        background_notify_episode_published_impl,
        session_local=session_local,
        logger=logger,
    )
    return {
        "translation_target_languages": translation_target_languages,
        "_has_recent_multilingual_ready_notification": _has_recent_multilingual_ready_notification,
        "_is_novel_translation_complete": _is_novel_translation_complete,
        "_is_episode_translation_complete": _is_episode_translation_complete,
        "_notify_multilingual_ready_for_novel": _notify_multilingual_ready_for_novel,
        "_notify_multilingual_ready_for_episode": _notify_multilingual_ready_for_episode,
        "_run_daily_translation_bot_once": _run_daily_translation_bot_once,
        "_daily_translation_bot_loop": _daily_translation_bot_loop,
        "_start_daily_translation_bot_if_enabled": _start_daily_translation_bot_if_enabled,
        "_run_monthly_stripe_premium_sync_once": _run_monthly_stripe_premium_sync_once,
        "_monthly_stripe_premium_sync_loop": _monthly_stripe_premium_sync_loop,
        "_start_monthly_stripe_premium_sync_if_enabled": _start_monthly_stripe_premium_sync_if_enabled,
        "_background_upsert_episode_translation": _background_upsert_episode_translation,
        "_background_upsert_episode_and_novel_translation": _background_upsert_episode_and_novel_translation,
        "_background_upsert_novel_translation": _background_upsert_novel_translation,
        "_should_enqueue_feed_novel_translation": _should_enqueue_feed_novel_translation,
        "_resolve_public_novel_card_translations": _resolve_public_novel_card_translations,
        "_background_notify_episode_published": _background_notify_episode_published,
    }
