import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { PublicForm } from "@/components/forms/PublicForm";

const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

beforeEach(() => { vi.stubGlobal("fetch", fetchMock); fetchMock.mockReset(); });
afterEach(() => vi.unstubAllGlobals());

function fill(kind: "newsletter" | "contact" = "newsletter") {
  fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: "reader@example.com" } });
  if (kind === "contact") {
    fireEvent.change(screen.getByLabelText(/^Имя/), { target: { value: "  Читатель  " } });
    fireEvent.change(screen.getByLabelText(/^Сообщение/), { target: { value: "  Обсудим проект и статью.  " } });
  }
  fireEvent.click(screen.getByRole("checkbox"));
}

describe("public forms", () => {
  it.each(["newsletter", "contact"] as const)("validates %s with labels, described errors and first-field focus", async (kind) => {
    const { container } = render(<PublicForm kind={kind} />);
    fireEvent.click(screen.getByRole("button"));
    const first = screen.getByLabelText(kind === "contact" ? /^Имя/ : /^Email/);
    expect(document.activeElement).toBe(first);
    expect(first.getAttribute("aria-invalid")).toBe("true");
    expect(first.getAttribute("aria-describedby")).toContain("error");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(await axe(container)).toHaveNoViolations();
  });

  it.each([
    ["newsletter", "/api/v1/subscribe", "subscribed"],
    ["contact", "/api/v1/feedback", "sent"],
  ] as const)("submits %s and focuses only a confirmed success", async (kind, endpoint, status) => {
    fetchMock.mockResolvedValue(json({ status }));
    const { container } = render(<PublicForm kind={kind} />);
    fill(kind);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/Спасибо/));
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe(endpoint);
    expect(screen.getByRole("form").getAttribute("method")).toBe("post");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(String(options?.body))).toEqual(kind === "contact"
      ? { name: "Читатель", email: "reader@example.com", message: "Обсудим проект и статью.", website: "" }
      : { email: "reader@example.com", website: "" });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("status")));
    expect((screen.getByLabelText(/^Email/) as HTMLInputElement).value).toBe("");
    expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(false);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("requires consent and does not send an invalid message", () => {
    render(<PublicForm kind="contact" />);
    fill("contact");
    fireEvent.change(screen.getByLabelText(/^Сообщение/), { target: { value: "   short   " } });
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/Напишите сообщение длиной/)).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByLabelText(/^Сообщение/));
    fireEvent.change(screen.getByLabelText(/^Сообщение/), { target: { value: "Сообщение достаточной длины" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button"));
    expect(document.activeElement).toBe(screen.getByRole("checkbox"));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("prevents a second request while pending and keeps a hidden honeypot", async () => {
    let resolve!: (response: Response) => void;
    fetchMock.mockImplementation(() => new Promise((done) => { resolve = done; }));
    const { container } = render(<PublicForm kind="newsletter" />);
    fill();
    const honeypot = container.querySelector<HTMLInputElement>('[name="website"]')!;
    expect(honeypot.closest("[hidden]")).not.toBeNull();
    expect(honeypot.tabIndex).toBe(-1);
    fireEvent.change(honeypot, { target: { value: "https://spam.example" } });
    fireEvent.submit(screen.getByRole("form"));
    fireEvent.submit(screen.getByRole("form"));
    expect(fetchMock).toHaveBeenCalledOnce();
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toBe("Отправка…");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).website).toBe("https://spam.example");
    await act(async () => { resolve(json({ status: "subscribed" })); });
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(false);
  });

  it("associates backend validation with the field without exposing raw response input", async () => {
    fetchMock.mockResolvedValue(json({ detail: [{ loc: ["body", "email"], msg: "Backend detail", input: "sensitive" }] }, 422));
    render(<PublicForm kind="newsletter" />);
    fill();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByLabelText(/^Email/).getAttribute("aria-invalid")).toBe("true"));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText(/^Email/)));
    expect(screen.getByText("Проверьте поле «Email».")).toBeTruthy();
    expect(screen.queryByText(/sensitive|Backend detail/)).toBeNull();
  });

  it.each([
    [429, /через час/],
    [503, /Почта временно недоступна/],
    [500, /Не удалось получить подтверждение/],
  ] as const)("reports HTTP %s without success and preserves the message", async (code, message) => {
    fetchMock.mockResolvedValue(json({ detail: "failure" }, code));
    render(<PublicForm kind="contact" />);
    fill("contact");
    fireEvent.click(screen.getByRole("button"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(message);
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect((screen.getByLabelText(/^Сообщение/) as HTMLTextAreaElement).value).toContain("Обсудим проект");
    expect(screen.queryByText(/Сообщение отправлено/)).toBeNull();
  });

  it("does not report a successful subscription on a network error or malformed success", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    fetchMock.mockResolvedValueOnce(json({ status: "unknown" }));
    render(<PublicForm kind="newsletter" />);
    fill();
    fireEvent.click(screen.getByRole("button"));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Проверьте соединение/);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/Сервис не подтвердил/));
    expect((screen.getByLabelText(/^Email/) as HTMLInputElement).value).toBe("reader@example.com");
    expect(screen.queryByText(/Email сохранён/)).toBeNull();
  });
});
