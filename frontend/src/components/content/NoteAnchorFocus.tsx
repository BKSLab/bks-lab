"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export function NoteAnchorFocus() {
  const pathname = usePathname();
  useEffect(() => {
    function focusNote() {
      if (window.location.pathname !== pathname) return;
      let id: string;
      try {
        id = decodeURIComponent(window.location.hash.slice(1));
      } catch {
        return;
      }
      if (!id.startsWith("note-")) return;
      const target = document.getElementById(id);
      if (
        target?.matches("article[data-note]") &&
        document.activeElement !== target
      )
        target.focus({ preventScroll: true });
    }
    focusNote();
    window.addEventListener("hashchange", focusNote);
    return () => window.removeEventListener("hashchange", focusNote);
  }, [pathname]);
  return null;
}
