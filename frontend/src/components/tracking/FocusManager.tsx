"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";

function hashTarget(main: HTMLElement): HTMLElement | null {
  let id: string;
  try {
    id = decodeURIComponent(window.location.hash.slice(1));
  } catch {
    return null;
  }
  const target = id ? document.getElementById(id) : null;
  if (
    !(target instanceof HTMLElement) ||
    !main.contains(target) ||
    target.closest('[hidden], [inert], [aria-hidden="true"]') ||
    target.matches(":disabled")
  ) {
    return null;
  }
  for (
    let element: HTMLElement | null = target;
    element;
    element = element.parentElement
  ) {
    const style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.visibility === "collapse"
    ) {
      return null;
    }
  }
  return target;
}

function focusTarget(target: HTMLElement) {
  if (!target.hasAttribute("tabindex") && target.tabIndex < 0) {
    target.setAttribute("tabindex", "-1");
  }
  // Next and the browser own scrolling, including history restoration.
  target.focus({ preventScroll: true });
}

// This stays mounted in the root layout, including on global 404/error pages.
// Initial loading is left to the browser; later routes and fragments announce
// their content without overriding native/Next scroll restoration.
export function FocusManager() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const previousUrl = useRef<string | null>(null);

  useEffect(() => {
    function onLocationChange() {
      // A history event can precede the React commit for a different page.
      if (
        window.location.pathname !== pathname ||
        new URLSearchParams(window.location.search).toString() !==
          (searchParams?.toString() ?? "")
      ) {
        return;
      }
      const url = window.location.href;
      if (previousUrl.current === url) {
        return;
      }
      const previous = previousUrl.current ? new URL(previousUrl.current) : null;
      previousUrl.current = url;
      if (
        !previous ||
        (previous.pathname === pathname && previous.hash === window.location.hash)
      ) {
        return;
      }

      const main = document.getElementById("main-content");
      if (!main) {
        return;
      }
      const heading = main.querySelector<HTMLHeadingElement>("h1");
      const target = hashTarget(main) ?? heading;
      if (target) {
        focusTarget(target);
        if (document.activeElement !== target && heading && target !== heading) {
          focusTarget(heading);
        }
      }
    }

    onLocationChange();
    window.addEventListener("hashchange", onLocationChange);
    window.addEventListener("popstate", onLocationChange);
    return () => {
      window.removeEventListener("hashchange", onLocationChange);
      window.removeEventListener("popstate", onLocationChange);
    };
  }, [pathname, searchParams]);

  return null;
}
