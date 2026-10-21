import { describe, expect, it, vi, beforeEach } from "vitest";
import { Hono } from "hono";
import type { AppHonoEnv } from "@/app/types";

const mocks = vi.hoisted(() => ({
  getDb: vi.fn(),
  fetchLiveMailMessages: vi.fn(),
}));

vi.mock("@/platform/db/client", () => ({
  getDb: mocks.getDb,
}));

vi.mock("@/modules/public-otp/mail-tm", () => ({
  getLiveMailDomains: vi.fn().mockResolvedValue(["maxxspace.com"]),
  fetchLiveMailMessages: mocks.fetchLiveMailMessages,
}));

import { createPublicOtpRouter } from "@/modules/public-otp/router";

describe("public-otp router security & isolation (A01, A02, A04, A05)", () => {
  let app: Hono<AppHonoEnv>;

  beforeEach(() => {
    vi.clearAllMocks();
    app = new Hono<AppHonoEnv>();
    app.route("/api/public", createPublicOtpRouter());
  });

  it("A01: rejects recent-otps scanner on public router with 404", async () => {
    const res = await app.request("/api/public/recent-otps");
    expect(res.status).toBe(404);
  });

  it("A04: rejects public bulk-create on public router with 404", async () => {
    const res = await app.request("/api/public/bulk-create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count: 5, domain: "maxxspace.com" }),
    });
    expect(res.status).toBe(404);
  });

  it("A05: rejects public auto-login with hardcoded credentials with 404", async () => {
    const res = await app.request("/api/public/auto-login");
    expect(res.status).toBe(404);
  });

  it("A02: rejects OTP request when email is missing with 400", async () => {
    const res = await app.request("/api/public/otp?pin=123456");
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  it("A02: rejects OTP request when PIN is missing with 400", async () => {
    const res = await app.request("/api/public/otp?email=user@example.com");
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  it("A02: fail-closed 404 when mailbox is not registered in system (does NOT leak via provider fallback)", async () => {
    // Mock DB select returning empty
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([]),
          }),
        }),
      }),
    });

    const res = await app.request("/api/public/otp?email=unregistered@example.com&pin=999999");
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain("Không tìm thấy");
    // Ensure provider was NOT called
    expect(mocks.fetchLiveMailMessages).not.toHaveBeenCalled();
  });

  it("A02: rejects request when PIN does not match mailbox PIN with 401", async () => {
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([
              {
                id: "addr-1",
                address: "tenant-a@example.com",
                meta: JSON.stringify({ pin: "123456" }),
                createdAt: new Date(),
              },
            ]),
          }),
        }),
      }),
    });

    const res = await app.request("/api/public/otp?email=tenant-a@example.com&pin=wrongpin");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain("Mã PIN bảo mật không chính xác");
    expect(mocks.fetchLiveMailMessages).not.toHaveBeenCalled();
  });

  it("A02: succeeds with 200 and Cache-Control: no-store when mailbox and PIN are valid", async () => {
    mocks.getDb.mockReturnValue({
      select: vi.fn((fields) => {
        // First select is emailAddresses, second is emails
        return {
          from: () => ({
            where: () => ({
              limit: vi.fn().mockResolvedValue([
                {
                  id: "addr-1",
                  address: "valid-user@example.com",
                  meta: JSON.stringify({ pin: "888888" }),
                  createdAt: new Date(),
                },
              ]),
              orderBy: () => ({
                limit: vi.fn().mockResolvedValue([
                  {
                    id: "msg-1",
                    from: "noreply@muse.ai",
                    subject: "Your Muse Code: 654321",
                    bodyText: "Verification code: 654321",
                    bodyHtml: "<p>Verification code: 654321</p>",
                    receivedAt: new Date(),
                  },
                ]),
              }),
            }),
          }),
        };
      }),
    });

    const res = await app.request("/api/public/otp?email=valid-user@example.com&pin=888888");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.hasEmails).toBe(true);
    expect(body.latest.otp).toBe("654321");
  });
});
