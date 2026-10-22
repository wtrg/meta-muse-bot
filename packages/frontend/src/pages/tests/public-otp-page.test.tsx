import { useEffect } from "react";
import { act, cleanup, fireEvent, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PublicOtpPage } from "@/pages/public-otp-page";
import { renderWithAct } from "@/test/render-with-act";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const response = (otp = "123456") =>
  new Response(
    JSON.stringify({
      ok: true,
      hasEmails: true,
      latest: { id: "synthetic", subject: "Verification", otp },
    }),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );

const deferred = () => {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>(done => {
    resolve = done;
  });
  return { promise, resolve };
};

const advance = async (milliseconds: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
};

const mount = async () => {
  const view = await renderWithAct(
    <MemoryRouter initialEntries={["/otp?email=a@example.com&pin=111111"]}>
      <PublicOtpPage />
    </MemoryRouter>
  );
  await advance(0);
  return view;
};

const navigateRef: { current: ((to: string) => void) | null } = {
  current: null,
};

const NavigationSpy = () => {
  const navigate = useNavigate();
  useEffect(() => {
    navigateRef.current = navigate;
  }, [navigate]);
  return null;
};

const mountWithNavigation = async (
  initialEntries = ["/otp?email=a@example.com&pin=111111"]
) => {
  const view = await renderWithAct(
    <MemoryRouter initialEntries={initialEntries}>
      <NavigationSpy />
      <PublicOtpPage />
    </MemoryRouter>
  );
  await advance(0);
  return view;
};

describe("PublicOtpPage request lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-22T00:00:00Z"));
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("polls for two minutes within mailbox/IP budgets and sends PIN only in a header", async () => {
    const counts = new Map<number, number>();
    let limited = 0;
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => {
        const window = Math.floor(Date.now() / 60000);
        const count = (counts.get(window) ?? 0) + 1;
        counts.set(window, count);
        if (count > 10 || count > 30) {
          limited++;
          return new Response("{}", {
            status: 429,
            headers: { "Retry-After": "60" },
          });
        }
        return response();
      });
    await mount();
    // Flush React's effect that arms the next timeout after each settled poll.
    for (let i = 0; i < 15; i++) await advance(8000);
    expect(fetchMock).toHaveBeenCalledTimes(16);
    expect(limited).toBe(0);
    expect(screen.queryByRole("alert")).toBeNull();
    for (const [url, init] of fetchMock.mock.calls) {
      expect(String(url)).not.toContain("pin=");
      expect((init?.headers as Record<string, string>)["X-Mailbox-Pin"]).toBe(
        "111111"
      );
      expect(init?.cache).toBe("no-store");
    }
  });

  it.each(["45", "Thu, 22 Oct 2026 00:00:45 GMT"])(
    "honors Retry-After %s for automatic and manual refresh",
    async retryAfter => {
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValueOnce(
          new Response("{}", {
            status: 429,
            headers: { "Retry-After": retryAfter },
          })
        )
        .mockImplementation(async () => response());
      await mount();
      await advance(44999);
      fireEvent.click(screen.getByRole("button", { name: "Lấy mã OTP" }));
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await advance(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(screen.getByText("123456")).toBeTruthy();
    }
  );

  it("does not overlap a pending request", async () => {
    const pending = deferred();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValue(pending.promise);
    await mount();
    await advance(32000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      (
        screen.getByRole("button", {
          name: /Đang kiểm tra/,
        }) as HTMLButtonElement
      ).disabled
    ).toBe(true);
  });

  it.each(["email", "pin"])(
    "rejects late responses after changing %s, including providers ignoring abort",
    async field => {
      const first = deferred();
      const second = deferred();
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockReturnValueOnce(first.promise)
        .mockReturnValueOnce(second.promise);
      await mount();
      fireEvent.change(
        screen.getByLabelText(
          field === "email" ? "Địa chỉ Email" : "Mã PIN bảo mật"
        ),
        {
          target: { value: field === "email" ? "b@example.com" : "222222" },
        }
      );
      expect((fetchMock.mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(
        true
      );
      await advance(8000);
      await act(async () => {
        second.resolve(response("654321"));
      });
      expect(screen.getByText("654321")).toBeTruthy();
      await act(async () => {
        first.resolve(response("123456"));
      });
      expect(screen.queryByText("123456")).toBeNull();
      expect(screen.getByText("654321")).toBeTruthy();
    }
  );

  it("clears a previously displayed code on credential change", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => response());
    await mount();
    expect(screen.getByText("123456")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Mã PIN bảo mật"), {
      target: { value: "222222" },
    });
    expect(screen.queryByText("123456")).toBeNull();
  });

  it("clears old results on network failure and backs off before retry", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response())
      .mockRejectedValueOnce(new Error("SYNTHETIC_NETWORK_FAILURE"))
      .mockImplementation(async () => response("654321"));
    await mount();
    await advance(8000);
    expect(screen.queryByText("123456")).toBeNull();
    expect(screen.getByRole("alert").textContent).toContain("Lỗi kết nối");
    await advance(15999);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText("654321")).toBeTruthy();
  });

  it("aborts on unmount and does not schedule a retry after a late response", async () => {
    const pending = deferred();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValue(pending.promise);
    const view = await mount();
    view.unmount();
    expect((fetchMock.mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(
      true
    );
    await act(async () => {
      pending.resolve(response());
    });
    await advance(120000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("clears old results and displays truthful error on provider 503 failure, then backs off before retry", async () => {
    const providerErrorResponse = new Response(
      JSON.stringify({
        ok: false,
        error:
          "Không thể đồng bộ hộp thư từ dịch vụ thư trực tiếp. Vui lòng thử lại sau.",
        code: "UPSTREAM_PROVIDER_ERROR",
      }),
      {
        status: 503,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      }
    );

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response("123456"))
      .mockResolvedValueOnce(providerErrorResponse)
      .mockImplementation(async () => response("654321"));

    await mount();
    expect(screen.getByText("123456")).toBeTruthy();

    await advance(8000);
    expect(screen.queryByText("123456")).toBeNull();
    expect(screen.getByRole("alert").textContent).toContain(
      "Không thể đồng bộ hộp thư từ dịch vụ thư trực tiếp"
    );

    // Backoff 8000 * 2^1 = 16000ms. No request at 15999ms.
    await advance(15999);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Third request triggers at 16000ms and recovers.
    await advance(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText("654321")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("clears old results and displays rate limit alert on 429 response", async () => {
    const rateLimitResponse = new Response(
      JSON.stringify({
        ok: false,
        error: "Too Many Requests",
      }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": "20",
        },
      }
    );

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response("123456"))
      .mockResolvedValueOnce(rateLimitResponse)
      .mockImplementation(async () => response("654321"));

    await mount();
    expect(screen.getByText("123456")).toBeTruthy();

    await advance(8000);
    expect(screen.queryByText("123456")).toBeNull();
    expect(screen.getByRole("alert").textContent).toContain(
      "Đã đạt giới hạn truy cập. Tự động chờ trước khi thử lại."
    );

    // Cooldown 20s. No request at 19999ms.
    await advance(19999);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Third request triggers at 20000ms and recovers.
    await advance(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText("654321")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("resets loading and error when credentials change during in-flight request, and ignores late response", async () => {
    const firstRequest = new Response("{}", {
      status: 429,
      headers: { "Retry-After": "45" },
    });
    const pendingDeferred = deferred();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(firstRequest)
      .mockReturnValueOnce(pendingDeferred.promise);

    await mount();
    expect(screen.getByRole("alert").textContent).toContain(
      "Đã đạt giới hạn truy cập"
    );

    // Advance 45s to clear initial cooldown and trigger second request, which is pending
    await advance(45000);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Verify in-flight loading state
    const button = screen.getByRole("button", {
      name: /Đang kiểm tra/,
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    // User changes email while request is in-flight
    fireEvent.change(screen.getByLabelText("Địa chỉ Email"), {
      target: { value: "changed@example.com" },
    });

    // Verification 1: Loading is immediately reset, button is no longer disabled
    const readyButton = screen.getByRole("button", {
      name: "Lấy mã OTP",
    }) as HTMLButtonElement;
    expect(readyButton.disabled).toBe(false);
    expect(screen.queryByText(/Đang kiểm tra/)).toBeNull();

    // Verification 2: Error alert is cleared
    expect(screen.queryByRole("alert")).toBeNull();

    // Verification 3: Resolving the pending deferred response late does not update UI
    await act(async () => {
      pendingDeferred.resolve(response("999999"));
    });
    expect(screen.queryByText("999999")).toBeNull();
  });

  it("resets loading, error, and stale state on URL navigation during in-flight request, and ignores late response", async () => {
    const pendingDeferred = deferred();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValueOnce(pendingDeferred.promise);

    await mountWithNavigation(["/otp?email=first@example.com&pin=111111"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Request is in-flight
    const button = screen.getByRole("button", {
      name: /Đang kiểm tra/,
    }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    // Navigate to a new URL while request is still pending
    await act(async () => {
      navigateRef.current?.("/otp?email=navigated@example.com&pin=222222");
    });

    // Loading must be reset immediately during navigation render
    const readyButton = screen.getByRole("button", {
      name: "Lấy mã OTP",
    }) as HTMLButtonElement;
    expect(readyButton.disabled).toBe(false);
    expect(screen.queryByText(/Đang kiểm tra/)).toBeNull();

    // Input values reflect new URL
    expect(
      (screen.getByLabelText("Địa chỉ Email") as HTMLInputElement).value
    ).toBe("navigated@example.com");
    expect(
      (screen.getByLabelText("Mã PIN bảo mật") as HTMLInputElement).value
    ).toBe("222222");

    // Late response resolution is ignored
    await act(async () => {
      pendingDeferred.resolve(response("888888"));
    });
    expect(screen.queryByText("888888")).toBeNull();
  });

  it("preserves active 429 cooldown across email/pin changes", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("{}", {
        status: 429,
        headers: { "Retry-After": "40" },
      })
    );

    await mount();
    expect(screen.getByRole("alert").textContent).toContain(
      "Đã đạt giới hạn truy cập"
    );

    // User changes email while 40s cooldown is active
    fireEvent.change(screen.getByLabelText("Địa chỉ Email"), {
      target: { value: "other@example.com" },
    });
    // Error alert is cleared on input change
    expect(screen.queryByRole("alert")).toBeNull();

    // User tries to click "Lấy mã OTP" before 40s expires (at 20s)
    await advance(20000);
    fireEvent.click(screen.getByRole("button", { name: "Lấy mã OTP" }));

    // Cooldown is still enforced! Shows cooldown message and does not fire a request
    expect(screen.getByRole("alert").textContent).toContain(
      "Vui lòng chờ đến lần cập nhật tiếp theo"
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("renders authenticated /addresses link and no /bulk link for local dev domain empty inbox", async () => {
    const localDevResponse = new Response(
      JSON.stringify({
        ok: true,
        hasEmails: false,
        isLocalDevDomain: true,
        message: "Chưa có thư mới nào gửi đến.",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(localDevResponse);

    await mount();

    const addressesLinks = screen.getAllByRole("link", {
      name: /Trang Quản Lý Hộp Thư/i,
    });
    expect(addressesLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of addressesLinks) {
      expect(link.getAttribute("href")).toBe("/addresses");
    }
    expect(screen.queryByRole("link", { name: /bulk/i })).toBeNull();
  });
});
