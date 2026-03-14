import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import TagChipLink from "../components/TagChipLink.jsx";
import SupportPanel from "../components/SupportPanel.jsx";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { filterR18Novels, useShowR18ByDisplaySetting } from "../lib/r18Display";

const API_BASE = getApiBase();
const FAVORITE_SUMMARY_MAX_CHARS = 500;

export default function UserPage() {
  const { username: usernameParam } = useParams();
  const username = useMemo(() => (usernameParam ?? "").trim(), [usernameParam]);
  const { t } = useI18n();
  const showR18 = useShowR18ByDisplaySetting();

  const [profile, setProfile] = useState(null);
  const [novels, setNovels] = useState([]);
  const [popularNovels, setPopularNovels] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [authorStats, setAuthorStats] = useState(null);
  const [favoriteTags, setFavoriteTags] = useState([]);
  const [activeTab, setActiveTab] = useState("works");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dmError, setDmError] = useState("");
  const [dmLoading, setDmLoading] = useState(false);
  const [meUserId, setMeUserId] = useState(null);
  const [followState, setFollowState] = useState({
    isFollowing: false,
    followerCount: 0,
    followingCount: 0,
  });
  const [followLoading, setFollowLoading] = useState(false);
  const [followError, setFollowError] = useState("");
  const [followListKind, setFollowListKind] = useState("");
  const [followListLoading, setFollowListLoading] = useState(false);
  const [followListError, setFollowListError] = useState("");
  const [followListItems, setFollowListItems] = useState([]);
  const [followListActionUserId, setFollowListActionUserId] = useState(null);
  const [followListPage, setFollowListPage] = useState(0);
  const [followListPageSize, setFollowListPageSize] = useState(50);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchAll = async () => {
      try {
        setLoading(true);
        setError("");

        const token =
          typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const headers = token ? { Authorization: `Bearer ${token}` } : {};

        const safeUsername = encodeURIComponent(username);
        const resProfile = await fetch(`${API_BASE}/api/public/users/${safeUsername}`, { headers });
        const profileData = await resProfile.json().catch(() => ({}));

        if (!resProfile.ok) {
          throw new Error(
            profileData.detail || t({ ja: "ユーザー情報の取得に失敗しました", en: "Failed to load user info." })
          );
        }

        const [resNovels, resPopularNovels, resFavorites] = await Promise.all([
          fetch(`${API_BASE}/api/public/users/${safeUsername}/novels`, { headers }),
          fetch(`${API_BASE}/api/public/users/${safeUsername}/novels?sort=popular`, { headers }),
          fetch(`${API_BASE}/api/public/users/${safeUsername}/favorites`, { headers }),
        ]);

        const novelsData = await resNovels.json().catch(() => []);
        const popularNovelsData = await resPopularNovels.json().catch(() => []);
        const favoritesData = await resFavorites.json().catch(() => []);
        if (!resNovels.ok) {
          throw new Error(
            novelsData.detail || t({ ja: "小説一覧の取得に失敗しました", en: "Failed to load novels." })
          );
        }
        if (!resPopularNovels.ok) {
          throw new Error(
            popularNovelsData.detail ||
              t({ ja: "人気作品の取得に失敗しました", en: "Failed to load popular novels." })
          );
        }
        if (!resFavorites.ok) {
          throw new Error(
            favoritesData.detail || t({ ja: "お気に入りの取得に失敗しました", en: "Failed to load favorites." })
          );
        }

        setProfile(profileData);
        setNovels(Array.isArray(novelsData) ? novelsData : []);
        setPopularNovels(Array.isArray(popularNovelsData) ? popularNovelsData : []);
        setFavorites(Array.isArray(favoritesData) ? favoritesData : []);
        setActiveTab("works");
        if (profileData?.id) {
          const [resStats, resTags] = await Promise.all([
            fetch(`${API_BASE}/api/authors/${profileData.id}/stats`, { headers }),
            fetch(`${API_BASE}/api/authors/${profileData.id}/favorite-tags`, { headers }),
          ]);
          const statsData = await resStats.json().catch(() => ({}));
          const tagsData = await resTags.json().catch(() => []);
          if (resStats.ok) setAuthorStats(statsData || null);
          else setAuthorStats(null);
          if (resTags.ok) setFavoriteTags(Array.isArray(tagsData) ? tagsData : []);
          else setFavoriteTags([]);
        } else {
          setAuthorStats(null);
          setFavoriteTags([]);
        }
        setFollowListKind("");
        setFollowListItems([]);
        setFollowListError("");
        setFollowState((prev) => ({
          ...prev,
          followerCount: Number(profileData?.follower_count || 0),
          followingCount: Number(profileData?.following_count || 0),
        }));

        if (token) {
          const resMe = await fetch(`${API_BASE}/api/users/me`, { headers });
          if (resMe.ok) {
            const me = await resMe.json().catch(() => ({}));
            const myUserId = Number(me?.id || 0) || null;
            setMeUserId(myUserId);
            const targetUserId = Number(profileData?.id || 0);
            if (myUserId && targetUserId && myUserId !== targetUserId) {
              const resStatus = await fetch(
                `${API_BASE}/api/users/${targetUserId}/follow-status`,
                { headers }
              );
              if (resStatus.ok) {
                const statusData = await resStatus.json().catch(() => ({}));
                setFollowState({
                  isFollowing: statusData?.is_following === true,
                  followerCount:
                    typeof statusData?.follower_count === "number"
                      ? statusData.follower_count
                      : Number(profileData?.follower_count || 0),
                  followingCount:
                    typeof statusData?.following_count === "number"
                      ? statusData.following_count
                      : Number(profileData?.following_count || 0),
                });
              }
            }
          } else {
            setMeUserId(null);
          }
        } else {
          setMeUserId(null);
        }
      } catch (e) {
        console.error(e);
        setError(e.message || t({ ja: "エラーが発生しました", en: "An error occurred." }));
      } finally {
        setLoading(false);
      }
    };

    if (!username) {
      setError(t({ ja: "ユーザー名が指定されていません", en: "No username specified." }));
      setLoading(false);
      return;
    }

    fetchAll();
  }, [username]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;

  if (error) {
    return (
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <div style={{ marginBottom: 12 }}>
          <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
        </div>
        <p style={{ color: "red" }}>{error}</p>
      </div>
    );
  }

  const displayName = profile?.username || username;
  const isPremium = !!profile?.is_premium;
  const currentUsername =
    typeof window !== "undefined" ? localStorage.getItem("username") : null;
  const trimmedCurrentUsername = (currentUsername ?? "").trim();
  const trimmedDisplayName = (displayName ?? "").trim();
  const canStartDm =
    trimmedCurrentUsername !== "" && trimmedCurrentUsername !== trimmedDisplayName;
  const canShowFollowButton =
    !!meUserId && !!profile?.id && Number(meUserId) !== Number(profile.id);
  const isOwnPage = !!meUserId && !!profile?.id && Number(meUserId) === Number(profile.id);
  const canViewFavorites = isOwnPage || (profile?.favorite_visibility || "public") === "public";
  const truncateFavoriteSummary = (text) => {
    const value = String(text || "");
    if (value.length <= FAVORITE_SUMMARY_MAX_CHARS) return value;
    return `${value.slice(0, FAVORITE_SUMMARY_MAX_CHARS)}...`;
  };

  const handleCreateDm = async () => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setDmError(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    if (!trimmedDisplayName) {
      setDmError(t({ ja: "送信先ユーザーが見つかりません", en: "Recipient user not found." }));
      return;
    }

    try {
      setDmLoading(true);
      setDmError("");
      const res = await fetch(`${API_BASE}/api/dms`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ target_username: trimmedDisplayName }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || t({ ja: "DMの作成に失敗しました", en: "Failed to create DM." }));
      }
      navigate(`/dms/${data.id}`);
    } catch (e) {
      console.error(e);
      setDmError(e.message || t({ ja: "エラーが発生しました", en: "An error occurred." }));
    } finally {
      setDmLoading(false);
    }
  };

  const handleToggleFollow = async () => {
    if (!profile?.id) return;
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setFollowError(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    try {
      setFollowLoading(true);
      setFollowError("");
      const shouldUnfollow = !!followState.isFollowing;
      const res = await fetch(`${API_BASE}/api/users/${profile.id}/follow`, {
        method: shouldUnfollow ? "DELETE" : "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data.detail ||
            t({ ja: "フォロー操作に失敗しました。", en: "Failed to update follow state." })
        );
      }
      const nextFollowerCount =
        typeof data?.follower_count === "number"
          ? data.follower_count
          : followState.followerCount;
      const nextFollowingCount =
        typeof data?.following_count === "number"
          ? data.following_count
          : followState.followingCount;
      setFollowState({
        isFollowing: data?.is_following === true,
        followerCount: nextFollowerCount,
        followingCount: nextFollowingCount,
      });
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              follower_count: nextFollowerCount,
              following_count: nextFollowingCount,
            }
          : prev
      );
    } catch (e) {
      console.error(e);
      setFollowError(
        e.message ||
          t({ ja: "フォロー操作に失敗しました。", en: "Failed to update follow state." })
      );
    } finally {
      setFollowLoading(false);
    }
  };

  const fetchFollowList = async (targetKind, page = 0, pageSize = followListPageSize) => {
    if (!profile?.id) return;
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    try {
      setFollowListLoading(true);
      setFollowListError("");
      const res = await fetch(
        `${API_BASE}/api/users/${profile.id}/${targetKind}?limit=${Math.max(1, Number(pageSize || 50))}&offset=${Math.max(0, Number(page || 0)) * Math.max(1, Number(pageSize || 50))}`,
        token
          ? {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            }
          : undefined
      );
      const data = await res.json().catch(() => []);
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "フォロー一覧の取得に失敗しました。", en: "Failed to load follow list." })
        );
      }
      setFollowListItems(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setFollowListItems([]);
      setFollowListError(
        e.message ||
          t({ ja: "フォロー一覧の取得に失敗しました。", en: "Failed to load follow list." })
      );
    } finally {
      setFollowListLoading(false);
    }
  };

  const handleLoadFollowList = async (kind) => {
    const targetKind = kind === "followers" ? "followers" : "following";
    if (followListKind === targetKind) {
      setFollowListKind("");
      setFollowListItems([]);
      setFollowListError("");
      setFollowListPage(0);
      return;
    }
    setFollowListKind(targetKind);
    setFollowListPage(0);
    await fetchFollowList(targetKind, 0, followListPageSize);
  };

  const handleToggleFollowInList = async (item) => {
    const targetId = Number(item?.user_id || 0);
    if (!targetId) return;
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      setFollowListError(t({ ja: "ログインが必要です", en: "Login required." }));
      return;
    }
    try {
      setFollowListActionUserId(targetId);
      setFollowListError("");
      const shouldUnfollow = item?.is_following === true;
      const res = await fetch(`${API_BASE}/api/users/${targetId}/follow`, {
        method: shouldUnfollow ? "DELETE" : "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          data?.detail ||
            t({ ja: "フォロー操作に失敗しました。", en: "Failed to update follow state." })
        );
      }
      const nextIsFollowing = data?.is_following === true;
      setFollowListItems((prev) =>
        prev.map((row) =>
          Number(row?.user_id || 0) === targetId
            ? {
                ...row,
                is_following: nextIsFollowing,
              }
            : row
        )
      );
    } catch (e) {
      console.error(e);
      setFollowListError(
        e.message ||
          t({ ja: "フォロー操作に失敗しました。", en: "Failed to update follow state." })
      );
    } finally {
      setFollowListActionUserId(null);
    }
  };

  const renderNovelList = ({ items, emptyText, truncateDescription = true }) => {
    const visibleItems = filterR18Novels(items, showR18);
    if (visibleItems.length === 0) {
      return <p style={{ marginTop: 10 }}>{emptyText}</p>;
    }
    return (
      <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
        {visibleItems.map((novel) => (
          <div
            key={novel.id}
            style={{
              border: "1px solid var(--novel-card-border)",
              borderRadius: 8,
              padding: 12,
              boxShadow: "0 2px 4px var(--shadow)",
              backgroundColor: "var(--novel-card-bg)",
              color: "var(--text)",
            }}
          >
            {novel.cover_image_url && (
              <img
                src={
                  novel.cover_image_url.startsWith("http")
                    ? novel.cover_image_url
                    : API_BASE + novel.cover_image_url
                }
                alt={t({ ja: "表紙画像", en: "Cover image" })}
                style={{
                  width: "100%",
                  maxHeight: 220,
                  objectFit: "cover",
                  borderRadius: 6,
                  boxShadow: "0 1px 4px var(--shadow)",
                  marginBottom: 10,
                }}
              />
            )}
            <h4 style={{ marginBottom: 6 }}>
              <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
            </h4>
            <div style={{ fontSize: 12, color: "var(--novel-card-meta)", marginBottom: 8 }}>
              <span style={{ marginRight: 8 }}>
                {novel.age_limit === "r18" ? (
                  <span className="age-chip age-chip-r18">R18</span>
                ) : novel.age_limit === "r15" ? (
                  <span className="age-chip">R15</span>
                ) : null}
              </span>
              <span
                className="age-chip"
                style={{
                  borderColor: "var(--accent)",
                  color: "var(--accent)",
                  background: "var(--accent-soft)",
                }}
              >
                {String(novel.creative_type || "original")}
              </span>
            </div>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 10,
                fontSize: 12,
                color: "var(--novel-card-meta)",
                marginBottom: 8,
              }}
            >
              <span>{t({ ja: "閲覧", en: "Views" })}: {novel.view_count ?? 0}</span>
              <span>{t({ ja: "LIKE", en: "Likes" })}: {novel.like_count ?? 0}</span>
              <span>{t({ ja: "お気に入り", en: "Favorites" })}: {novel.favorite_count ?? 0}</span>
              {typeof novel.comment_count === "number" ? (
                <span>{t({ ja: "コメント", en: "Comments" })}: {novel.comment_count ?? 0}</span>
              ) : null}
              <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
              <span className="tag-chip-row">
                {Array.isArray(novel.tags) && novel.tags.length > 0 ? (
                  novel.tags.map((tag) => (
                    <TagChipLink key={tag.id ?? tag.name} name={tag.name} />
                  ))
                ) : (
                  <span style={{ color: "var(--muted-text)" }}>
                    {t({ ja: "タグ: なし", en: "Tags: none" })}
                  </span>
                )}
              </span>
            </div>

            <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: 0 }}>
              {truncateDescription
                ? truncateFavoriteSummary(novel.description)
                : novel.description || ""}
            </p>
          </div>
        ))}
      </div>
    );
  };

  const tabs = [
    { key: "works", label: t({ ja: "作品", en: "Works" }) },
    { key: "popular", label: t({ ja: "人気", en: "Popular" }) },
    { key: "bookmarks", label: t({ ja: "ブックマーク", en: "Bookmarks" }) },
    { key: "profile", label: t({ ja: "プロフィール", en: "Profile" }) },
  ];
  const followListTotalCount =
    followListKind === "followers"
      ? Number(followState.followerCount || 0)
      : followListKind === "following"
        ? Number(followState.followingCount || 0)
        : 0;
  const followListTotalPages = Math.max(
    1,
    Math.ceil(followListTotalCount / Math.max(1, Number(followListPageSize || 50)))
  );
  const canPrevFollowListPage = followListPage > 0;
  const canNextFollowListPage = followListPage + 1 < followListTotalPages;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/">{t({ ja: "← トップに戻る", en: "← Back to Home" })}</Link>
      </div>

      <h2
        style={{
          marginBottom: "0.75rem",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        {t({ ja: "{{name}} さんのページ", en: "{{name}}'s page" }, { name: displayName })}
        {isPremium && (
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: "999px",
              backgroundColor: "var(--accent)",
              color: "var(--on-accent)",
              fontSize: 12,
            }}
          >
            PREMIUM
          </span>
        )}
        {canStartDm && (
          <button
            type="button"
            onClick={handleCreateDm}
            disabled={dmLoading}
            title={t({ ja: "DMを送る", en: "Send DM" })}
            className="dm-icon-button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: 999,
              padding: 0,
            }}
            aria-label={t({ ja: "DMを送る", en: "Send DM" })}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
              <path d="m22 6-10 7L2 6" />
            </svg>
          </button>
        )}
        {canShowFollowButton && (
          <button
            type="button"
            className="btn btn-border"
            onClick={handleToggleFollow}
            disabled={followLoading}
          >
            {followLoading
              ? t({ ja: "更新中...", en: "Updating..." })
              : followState.isFollowing
                ? t({ ja: "フォロー中", en: "Following" })
                : t({ ja: "フォロー", en: "Follow" })}
          </button>
        )}
      </h2>
      {dmError && <p style={{ color: "red", marginBottom: 8 }}>{dmError}</p>}
      {followError && <p style={{ color: "red", marginBottom: 8 }}>{followError}</p>}
      <p style={{ marginTop: 0, color: "var(--muted-text)" }}>
        {t({ ja: "フォロワー", en: "Followers" })}: {followState.followerCount} /{" "}
        {t({ ja: "フォロー中", en: "Following" })}: {followState.followingCount}
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <button
          type="button"
          className="btn btn-border"
          onClick={() => handleLoadFollowList("followers")}
          disabled={followListLoading}
        >
          {t({ ja: "フォロワー一覧", en: "Followers list" })}
        </button>
        <button
          type="button"
          className="btn btn-border"
          onClick={() => handleLoadFollowList("following")}
          disabled={followListLoading}
        >
          {t({ ja: "フォロー中一覧", en: "Following list" })}
        </button>
      </div>
      {followListKind && (
        <section
          style={{
            marginBottom: 14,
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 10,
          }}
        >
          <h4 style={{ marginTop: 0, marginBottom: 8 }}>
            {followListKind === "followers"
              ? t({ ja: "フォロワー一覧", en: "Followers list" })
              : t({ ja: "フォロー中一覧", en: "Following list" })}
          </h4>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
            <button
              type="button"
              className="btn btn-border"
              disabled={followListLoading || !canPrevFollowListPage}
              onClick={async () => {
                const next = Math.max(0, followListPage - 1);
                setFollowListPage(next);
                await fetchFollowList(followListKind, next, followListPageSize);
              }}
            >
              {t({ ja: "前へ", en: "Prev" })}
            </button>
            <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
              {t({ ja: "{{current}} / {{total}} ページ", en: "Page {{current}} / {{total}}" }, { current: followListPage + 1, total: followListTotalPages })}
            </span>
            <button
              type="button"
              className="btn btn-border"
              disabled={followListLoading || !canNextFollowListPage}
              onClick={async () => {
                const next = followListPage + 1;
                setFollowListPage(next);
                await fetchFollowList(followListKind, next, followListPageSize);
              }}
            >
              {t({ ja: "次へ", en: "Next" })}
            </button>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
              <span style={{ fontSize: 12, color: "var(--muted-text)" }}>
                {t({ ja: "件数", en: "Per page" })}
              </span>
              <select
                className="search-input"
                value={followListPageSize}
                onChange={async (e) => {
                  const nextSize = Number(e.target.value || 50);
                  setFollowListPageSize(nextSize);
                  setFollowListPage(0);
                  await fetchFollowList(followListKind, 0, nextSize);
                }}
                style={{ width: 88, minWidth: 88 }}
              >
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
          </div>
          {followListLoading ? (
            <p style={{ margin: 0 }}>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
          ) : followListError ? (
            <p style={{ margin: 0, color: "red" }}>{followListError}</p>
          ) : followListItems.length === 0 ? (
            <p style={{ margin: 0 }}>
              {t({ ja: "該当ユーザーはいません。", en: "No users found." })}
            </p>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {followListItems.map((item) => (
                <div key={`${followListKind}-${item.user_id}`} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <Link to={`/users/${encodeURIComponent(item.username || "")}`}>
                    @{item.username || "unknown"}
                  </Link>
                  {item.is_premium ? (
                    <span
                      style={{
                        display: "inline-block",
                        padding: "1px 6px",
                        borderRadius: 999,
                        backgroundColor: "var(--accent)",
                        color: "var(--on-accent)",
                        fontSize: 11,
                      }}
                    >
                      PREMIUM
                    </span>
                  ) : null}
                  {meUserId && Number(meUserId) !== Number(item.user_id) ? (
                    <button
                      type="button"
                      className="btn btn-border"
                      style={{ marginLeft: "auto" }}
                      disabled={followListActionUserId === Number(item.user_id)}
                      onClick={() => handleToggleFollowInList(item)}
                    >
                      {followListActionUserId === Number(item.user_id)
                        ? t({ ja: "更新中...", en: "Updating..." })
                        : item?.is_following
                          ? t({ ja: "フォロー中", en: "Following" })
                          : t({ ja: "フォロー", en: "Follow" })}
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section style={{ marginTop: "1.25rem" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={activeTab === tab.key ? "btn" : "btn btn-border"}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "works" && (
          <section style={{ marginTop: "1rem" }}>
            <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
              {t({ ja: "公開中の小説", en: "Published novels" })}
            </h3>
            {renderNovelList({
              items: novels,
              emptyText: t({ ja: "公開中の小説がありません。", en: "No published novels." }),
            })}
          </section>
        )}

        {activeTab === "popular" && (
          <section style={{ marginTop: "1rem" }}>
            <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
              {t({ ja: "人気作品", en: "Popular novels" })}
            </h3>
            {renderNovelList({
              items: popularNovels,
              emptyText: t({ ja: "人気作品はまだありません。", en: "No popular novels yet." }),
            })}
          </section>
        )}

        {activeTab === "bookmarks" && (
          <section style={{ marginTop: "1rem" }}>
            <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
              {t({ ja: "お気に入り小説", en: "Favorite novels" })}
            </h3>
            {canViewFavorites ? (
              renderNovelList({
                items: favorites,
                emptyText: t({ ja: "お気に入りはまだありません。", en: "No favorites yet." }),
                truncateDescription: false,
              })
            ) : (
              <p style={{ marginTop: 10, color: "var(--muted-text)" }}>
                {t({
                  ja: "このユーザーのブックマークは非公開です。",
                  en: "This user's bookmarks are private.",
                })}
              </p>
            )}
          </section>
        )}

        {activeTab === "profile" && (
          <section style={{ marginTop: "1rem", display: "grid", gap: 12 }}>
            <h3 style={{ borderBottom: "1px solid var(--border)", paddingBottom: 6, marginBottom: 0 }}>
              {t({ ja: "プロフィール", en: "Profile" })}
            </h3>
            {profile?.profile_header_url ? (
              <img
                src={profile.profile_header_url}
                alt={t({ ja: "ヘッダー画像", en: "Header image" })}
                style={{ width: "100%", maxHeight: 220, objectFit: "cover", borderRadius: 8 }}
              />
            ) : null}
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              {profile?.profile_icon_url ? (
                <img
                  src={profile.profile_icon_url}
                  alt={t({ ja: "アイコン", en: "Icon" })}
                  style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover" }}
                />
              ) : null}
              <div style={{ color: "var(--muted-text)", fontSize: 14 }}>
                @{displayName}
              </div>
            </div>
            {profile?.profile_bio ? (
              <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{profile.profile_bio}</p>
            ) : (
              <p style={{ whiteSpace: "pre-wrap", margin: 0, color: "var(--muted-text)" }}>
                {t({ ja: "自己紹介はまだありません。", en: "No bio yet." })}
              </p>
            )}
            {(profile?.profile_website_url || profile?.profile_x_url) && (
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {profile?.profile_website_url ? (
                  <a href={profile.profile_website_url} target="_blank" rel="noreferrer">
                    {t({ ja: "Webサイト", en: "Website" })}
                  </a>
                ) : null}
                {profile?.profile_x_url ? (
                  <a href={profile.profile_x_url} target="_blank" rel="noreferrer">
                    X
                  </a>
                ) : null}
              </div>
            )}
            {authorStats ? (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 10,
                  fontSize: 13,
                  color: "var(--muted-text)",
                }}
              >
                <span>{t({ ja: "公開作品", en: "Works" })}: {authorStats.novels ?? 0}</span>
                <span>{t({ ja: "総閲覧", en: "Total views" })}: {authorStats.views ?? 0}</span>
                <span>{t({ ja: "総いいね", en: "Total likes" })}: {authorStats.likes ?? 0}</span>
                <span>{t({ ja: "総ブックマーク", en: "Total bookmarks" })}: {authorStats.favorites ?? 0}</span>
                <span>{t({ ja: "フォロワー", en: "Followers" })}: {authorStats.followers ?? 0}</span>
                <span>{t({ ja: "フォロー中", en: "Following" })}: {authorStats.following ?? 0}</span>
              </div>
            ) : (
              <p style={{ margin: 0, color: "var(--muted-text)" }}>
                {t({ ja: "プロフィール統計は準備中です。", en: "Profile stats are not available yet." })}
              </p>
            )}
            {favoriteTags.length > 0 && (
              <div>
                <div style={{ fontSize: 13, color: "var(--muted-text)", marginBottom: 6 }}>
                  {t({ ja: "使用タグ上位", en: "Top tags" })}
                </div>
                <div className="tag-chip-row">
                  {favoriteTags.map((tag) => (
                    <TagChipLink key={`author-top-tag-${tag.name}`} name={tag.name} />
                  ))}
                </div>
              </div>
            )}
            {profile?.id && (
              <SupportPanel
                authorUserId={profile.id}
                authorName={displayName || t({ ja: "作者", en: "Author" })}
              />
            )}
          </section>
        )}
      </section>
    </div>
  );
}
