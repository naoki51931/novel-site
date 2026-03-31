const ONE_DAY_MS = 24 * 60 * 60 * 1000;

function toTimestamp(value) {
  if (!value) return 0;
  const ts = new Date(value).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

export function isRecentDate(value, withinDays = 7) {
  const ts = toTimestamp(value);
  if (!ts) return false;
  const thresholdMs = Math.max(1, Number(withinDays) || 7) * ONE_DAY_MS;
  return Date.now() - ts <= thresholdMs;
}

export function hasRecentEpisodeActivity(novel, withinDays = 7) {
  const latest = novel?.latest_episode_activity_at || novel?.latest_episode_created_at;
  return isRecentDate(latest, withinDays);
}

export function isRecentEpisode(episode, withinDays = 7) {
  const activity = episode?.updated_at || episode?.created_at;
  return isRecentDate(activity, withinDays);
}
