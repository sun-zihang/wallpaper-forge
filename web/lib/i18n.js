// web/lib/i18n.js
// Minimal language store: zh (default) / en, persisted in localStorage.
const KEY = "wc.lang";

export function getLang() {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "en" || v === "zh") return v;
  } catch {
    /* storage unavailable */
  }
  return "zh";
}

export function setLang(lang) {
  const v = lang === "en" ? "en" : "zh";
  try {
    localStorage.setItem(KEY, v);
  } catch {
    /* storage unavailable */
  }
  return v;
}
