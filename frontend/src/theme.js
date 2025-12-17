export const THEME_STORAGE_KEY = "theme";

export function normalizeTheme(value) {
  return value === "dark" ? "dark" : "light";
}

export function getSavedTheme() {
  return normalizeTheme(localStorage.getItem(THEME_STORAGE_KEY));
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = normalizeTheme(theme);
}

export function setTheme(theme) {
  const normalized = normalizeTheme(theme);
  localStorage.setItem(THEME_STORAGE_KEY, normalized);
  applyTheme(normalized);
  return normalized;
}

export function initTheme() {
  applyTheme(getSavedTheme());
}
