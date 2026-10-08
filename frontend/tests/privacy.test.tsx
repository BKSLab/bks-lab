import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import PrivacyPage, { metadata } from "@/app/(public)/privacy/page";
import ContactsPage from "@/app/(public)/contacts/page";
import { blogMetadata } from "@/components/blog/BlogPageContent";
import { notesMetadata } from "@/components/content/NotesPageContent";

afterEach(() => vi.unstubAllEnvs());

describe("privacy and contact details", () => {
  it("uses the configured address, describes actual storage and has accessible sections", async () => {
    vi.stubEnv("CONTACT_EMAIL", "author@example.com");
    vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "false");
    const { container } = render(<main><PrivacyPage /></main>);
    expect(screen.getByRole("link", { name: "author@example.com" }).getAttribute("href")).toBe("mailto:author@example.com");
    expect(screen.getByText(/В базе данных сайта обращения не сохраняются/)).toBeTruthy();
    expect(screen.getByText(/Рассылка пока не запущена/)).toBeTruthy();
    expect(screen.getByText(/Код Рекламной сети Яндекса не загружается/)).toBeTruthy();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("links to the contact form without inventing an owner address", () => {
    vi.stubEnv("CONTACT_EMAIL", "");
    render(<PrivacyPage />);
    expect(screen.getByRole("link", { name: "страницу контактов" }).getAttribute("href")).toBe("/contacts");
    expect(document.querySelector('a[href^="mailto:"]')).toBeNull();
  });

  it("discloses third-party advertising only when a slot can be loaded", () => {
    vi.stubEnv("NEXT_PUBLIC_ADS_ENABLED", "true");
    vi.stubEnv("NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID", "R-A-123456-1");
    render(<PrivacyPage />);
    expect(screen.getByRole("link", { name: "политика конфиденциальности Яндекса" }).getAttribute("href")).toBe("https://yandex.ru/legal/confidential/");
    expect(screen.queryByText(/Рекламные блоки отключены/)).toBeNull();
  });

  it("offers the actual contact address alongside a working form", () => {
    vi.stubEnv("CONTACT_EMAIL", "author@example.com");
    render(<ContactsPage />);
    expect(screen.getByRole("link", { name: "author@example.com" }).getAttribute("href")).toBe("mailto:author@example.com");
    expect(screen.getByRole("form", { name: "Связаться с автором" })).toBeTruthy();
    expect(screen.queryByText(/ознакомительном режиме/)).toBeNull();
  });

  it("supplies canonical and social metadata and distinct pagination descriptions", () => {
    expect(metadata.alternates?.canonical).toBe("/privacy");
    expect(metadata.openGraph).toMatchObject({ url: "/privacy", images: [{ url: "/og/bks-lab-default.jpg" }] });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
    expect(blogMetadata(2, "ai").description).toMatch(/AI.*Страница 2/);
    expect(blogMetadata(2, "ai").alternates?.canonical).toBe("/blog/ai/page/2");
    expect(notesMetadata(2).description).toContain("Страница 2");
  });
});
