"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { CloseIcon, MenuIcon } from "@/components/ui/icons";
import { NAV_ITEMS, isActivePath } from "@/lib/constants";

const PANEL_ID = "mobile-navigation";

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();
  const previousPathname = useRef(pathname);

  // Close the panel after client-side navigation.
  useEffect(() => {
    if (previousPathname.current !== pathname) {
      previousPathname.current = pathname;
      setOpen(false);
    }
  }, [pathname]);

  // Escape closes the menu and returns focus to the toggle button
  // (design spec section 9).
  useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <div
      className="desktop:hidden"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
        }
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={PANEL_ID}
        aria-label={open ? "Закрыть меню" : "Открыть меню"}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-text hover:text-accent"
      >
        {open ? (
          <CloseIcon className="h-6 w-6" />
        ) : (
          <MenuIcon className="h-6 w-6" />
        )}
      </button>
      {open ? (
        <nav
          id={PANEL_ID}
          aria-label="Мобильная навигация"
          className="absolute inset-x-0 top-full border-b border-border bg-surface-alt"
        >
          <ul className="flex flex-col gap-1 px-4 py-4">
            {NAV_ITEMS.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`block rounded-md px-3 py-3 text-base font-medium ${
                      active
                        ? "text-accent underline decoration-2 underline-offset-8"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
            <li className="pt-2">
              <Link
                href="/contacts"
                className="inline-flex min-h-11 items-center rounded-[var(--radius-button)] bg-accent px-6 py-2 text-base font-semibold text-on-accent hover:bg-accent-hover"
              >
                Связаться
              </Link>
            </li>
          </ul>
        </nav>
      ) : null}
    </div>
  );
}
