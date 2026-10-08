"use client";

import { useSyncExternalStore } from "react";

import { MoonIcon, SunIcon } from "@/components/ui/icons";
import { getTheme, setTheme, subscribeTheme, type Theme } from "@/lib/theme";

const getServerSnapshot = (): Theme => "light";

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    subscribeTheme,
    getTheme,
    getServerSnapshot,
  );

  function toggle() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={
        theme === "dark"
          ? "Переключить на светлую тему"
          : "Переключить на тёмную тему"
      }
      className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-text-muted hover:text-accent"
    >
      {theme === "dark" ? (
        <SunIcon className="h-5 w-5" />
      ) : (
        <MoonIcon className="h-5 w-5" />
      )}
    </button>
  );
}
