export type Theme = "dark" | "light";

const CHANGE_EVENT = "bks:theme-change";
const DARK_QUERY = "(prefers-color-scheme: dark)";

// Runs in <head> before paint, including when storage is unavailable.
export const themeInitScript = `(function(){var t;try{t=localStorage.getItem("theme")}catch(e){}var saved=t==="light"||t==="dark";var dark=window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches;var root=document.documentElement;root.dataset.themePreference=saved?t:"system";root.dataset.theme=saved?t:dark?"dark":"light";var meta=document.querySelector('meta[name="theme-color"]');if(meta)meta.content=root.dataset.theme==="dark"?"#071827":"#f4f7f9";})();`;

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (meta) meta.content = theme === "dark" ? "#071827" : "#f4f7f9";
}

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.themePreference = theme;
  applyTheme(theme);
  try {
    localStorage.setItem("theme", theme);
  } catch {
    // Keep the selection for this document when storage is blocked or full.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function subscribeTheme(callback: () => void): () => void {
  const media = window.matchMedia?.(DARK_QUERY);
  const onSystemChange = () => {
    const preference = document.documentElement.dataset.themePreference;
    if (preference !== "light" && preference !== "dark") {
      applyTheme(media?.matches ? "dark" : "light");
      callback();
    }
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key !== "theme" && event.key !== null) return;
    const value = event.newValue;
    const saved = value === "light" || value === "dark";
    document.documentElement.dataset.themePreference = saved ? value : "system";
    applyTheme(saved ? value : media?.matches ? "dark" : "light");
    callback();
  };
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", onStorage);
  media?.addEventListener("change", onSystemChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", onStorage);
    media?.removeEventListener("change", onSystemChange);
  };
}
