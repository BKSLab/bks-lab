import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({
  router: { replace: vi.fn(), refresh: vi.fn() },
  fetchMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/admin" }));

import AdminLayout from "@/app/(admin)/layout";
import AdminLoginPage from "@/app/(admin)/admin/login/page";
import { AdminLoginForm } from "@/components/admin/AdminLoginForm";
import { AdminLogoutButton } from "@/components/admin/AdminLogoutButton";
import { AdminSessionRefresh } from "@/components/admin/AdminSessionRefresh";

beforeEach(() => {
  fetchMock.mockReset();
  router.replace.mockReset();
  router.refresh.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
});

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function fillLogin() {
  fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "owner" } });
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "test-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Войти" }));
}

describe("admin login and logout", () => {
  it("has one main, heading and skip-link; inputs have accessible labels", async () => {
    const { container } = render(<AdminLayout><AdminLoginPage /></AdminLayout>);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Перейти к основному содержимому" }).getAttribute("href")).toBe("#main-content");
    expect(screen.getByLabelText("Логин").getAttribute("autocomplete")).toBe("username");
    expect(screen.getByLabelText("Пароль").getAttribute("autocomplete")).toBe("current-password");
    expect(container.querySelector("form")?.getAttribute("method")).toBe("post");
    expect(container.querySelector("form")?.getAttribute("action")).toBe("/api/admin/auth/login");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("focuses a textual error when required inputs are missing", async () => {
    render(<AdminLoginForm />);
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));
    const error = await screen.findByRole("alert");
    expect(error.textContent).toContain("Заполните логин и пароль");
    expect(document.activeElement).toBe(error);
    expect(screen.getByLabelText("Пароль").getAttribute("aria-describedby")).toBe(error.id);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([[401, "Неверный логин или пароль"], [429, "Слишком много попыток"], [403, "Не удалось войти"]])("handles login status %s without echoing server errors", async (status, message) => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: "private-debug" }), { status }));
    render(<AdminLoginForm />);
    fillLogin();
    const error = await screen.findByRole("alert");
    expect(error.textContent).toContain(message);
    expect(error.textContent).not.toContain("private-debug");
    expect(document.activeElement).toBe(error);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("submits credentials only to the same-origin API and refreshes the authenticated page", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    render(<AdminLoginForm />);
    fillLogin();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/admin"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/admin/auth/login");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(JSON.parse(init.body)).toEqual({ username: "owner", password: "test-password" });
    expect(router.refresh).toHaveBeenCalledOnce();
  });

  it("restores submission after a network failure", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    render(<AdminLoginForm />);
    fillLogin();
    expect((await screen.findByRole("alert")).textContent).toContain("Нет связи с сервером");
    expect((screen.getByRole("button", { name: "Войти" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it.each([204, 401])("clears client navigation state on logout status %s", async (status) => {
    fetchMock.mockResolvedValue(new Response(null, { status }));
    render(<AdminLogoutButton />);
    fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/admin/login"));
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(router.refresh).toHaveBeenCalledOnce();
  });

  it("retains the page and shows a focused error when logout fails", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    render(<AdminLogoutButton />);
    fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
    const error = await screen.findByRole("alert");
    await waitFor(() => expect(document.activeElement).toBe(error));
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("browser session renewal", () => {
  it("renews on visible activity at most every five minutes", async () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    render(<AdminSessionRefresh />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    fireEvent.keyDown(document, { key: "Tab" });
    expect(fetchMock).toHaveBeenCalledOnce();
    now.mockReturnValue(1_301_000);
    await act(async () => { fireEvent.keyDown(document, { key: "Tab" }); });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/auth/me");
    expect(fetchMock.mock.calls[0][1].cache).toBe("no-store");
  });

  it("does not renew in a hidden tab", () => {
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    render(<AdminSessionRefresh />);
    fireEvent.focus(window);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("redirects after expiry without exposing session data to JavaScript", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }));
    render(<AdminSessionRefresh />);
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/admin/login"));
    expect(fetchMock.mock.calls[0][1].headers).toBeUndefined();
  });
});
