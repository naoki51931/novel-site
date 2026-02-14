export const THEME_STORAGE_KEY = "theme";
export const COLOR_PRESET_STORAGE_KEY = "color_preset";

export function normalizeTheme(value) {
  return value === "dark" ? "dark" : "light";
}

export function getSavedTheme() {
  return normalizeTheme(localStorage.getItem(THEME_STORAGE_KEY));
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = normalizeTheme(theme);
}

export function normalizeColorPreset(value) {
  return value === "classic" ? "classic" : "wa-modern";
}

export function getSavedColorPreset() {
  return normalizeColorPreset(localStorage.getItem(COLOR_PRESET_STORAGE_KEY));
}

export function applyColorPreset(preset) {
  document.documentElement.dataset.colorPreset = normalizeColorPreset(preset);
}

export function setColorPreset(preset) {
  const normalized = normalizeColorPreset(preset);
  localStorage.setItem(COLOR_PRESET_STORAGE_KEY, normalized);
  applyColorPreset(normalized);
  return normalized;
}

export function setTheme(theme) {
  const normalized = normalizeTheme(theme);
  localStorage.setItem(THEME_STORAGE_KEY, normalized);
  applyTheme(normalized);
  return normalized;
}

export function initTheme() {
  applyTheme(getSavedTheme());
  applyColorPreset(getSavedColorPreset());
}
