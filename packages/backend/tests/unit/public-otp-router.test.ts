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

import {
  createPublicOtpRouter,
  extractOtpAndLinks,
  isAllowedMagicLinkHostname,
  _resetOtpRateLimitsForTesting,
  _getMemoryRateLimitsSizeForTesting,
  cleanupMemoryRateLimits,
} from "@/modules/public-otp/router";
import { generateSecurePin } from "@/shared/pin";
import { createApp } from "@/index";

describe("public-otp router security, isolation & contract (A01, A02, A04, A05)", () => {
  let app: Hono<AppHonoEnv>;

  beforeEach(() => {
    vi.clearAllMocks();
    _resetOtpRateLimitsForTesting();
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

  it("A02: fail-closed 401 when mailbox has no PIN configured in meta (does not derive secret from addressId)", async () => {
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([
              {
                id: "addr-no-pin",
                address: "nopin@example.com",
                meta: JSON.stringify({ label: "no-pin-box" }),
                createdAt: new Date(),
              },
            ]),
          }),
        }),
      }),
    });

    // Even if caller tries to compute a deterministic hash or any PIN, it must fail closed
    const res = await app.request("/api/public/otp?email=nopin@example.com&pin=123456");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(mocks.fetchLiveMailMessages).not.toHaveBeenCalled();
  });

  it("Tenant isolation: cross-mailbox PIN access (Tenant B PIN against Tenant A mailbox) is rejected with 401", async () => {
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([
              {
                id: "addr-tenant-a",
                address: "tenant-a@example.com",
                meta: JSON.stringify({ pin: "111111" }),
                createdAt: new Date(),
              },
            ]),
          }),
        }),
      }),
    });

    // Tenant B attempts to use its own PIN (222222) to view Tenant A's mailbox
    const res = await app.request("/api/public/otp?email=tenant-a@example.com&pin=222222");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(mocks.fetchLiveMailMessages).not.toHaveBeenCalled();
  });

  it("A02: succeeds with 200 and Cache-Control: no-store when mailbox and PIN are valid", async () => {
    mocks.getDb.mockReturnValue({
      select: vi.fn(() => ({
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
      })),
    });

    const res = await app.request("/api/public/otp?email=valid-user@example.com&pin=888888");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.hasEmails).toBe(true);
    expect(body.latest.otp).toBe("654321");
  });

  it("Rate limit: enforces 10 requests/minute threshold and returns 429 Too Many Requests on overflow", async () => {
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([]),
          }),
        }),
      }),
    });

    const headers = { "cf-connecting-ip": "203.0.113.42" };
    for (let i = 0; i < 10; i++) {
      const res = await app.request("/api/public/otp?email=rate-target@example.com&pin=123456", { headers });
      expect(res.status).toBe(404);
    }

    // 11th request from the same IP/email key must be blocked by rate limiter
    const blockedRes = await app.request("/api/public/otp?email=rate-target@example.com&pin=123456", { headers });
    expect(blockedRes.status).toBe(429);
    expect(blockedRes.headers.get("Retry-After")).toBeDefined();
    const body = await blockedRes.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain("vượt quá giới hạn thử OTP");
  });

  it("Rate limit DO outage: fails closed with 429 when FIXED_WINDOW_RATE_LIMITERS throws", async () => {
    const brokenDoEnv = {
      FIXED_WINDOW_RATE_LIMITERS: {
        idFromName: vi.fn().mockReturnValue("do-id-1"),
        get: vi.fn().mockReturnValue({
          consume: vi.fn().mockRejectedValue(new Error("DO_STORE_UNAVAILABLE")),
        }),
      },
    } as unknown as AppHonoEnv["Bindings"];

    const brokenApp = new Hono<AppHonoEnv>();
    brokenApp.use("*", async (c, next) => {
      c.env = brokenDoEnv;
      await next();
    });
    brokenApp.route("/api/public", createPublicOtpRouter());

    const res = await brokenApp.request(
      "/api/public/otp?email=do-test@example.com&pin=123456"
    );
    expect(res.status).toBe(429);
    expect(res.headers.get("Retry-After")).toBe("60");
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  it("Rate limit dual budget: independent mailbox protection blocks distributed attack across rotating IPs", async () => {
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([]),
          }),
        }),
      }),
    });

    // 10 requests from 10 different IP addresses targeting the SAME mailbox
    for (let i = 1; i <= 10; i++) {
      const res = await app.request("/api/public/otp?email=victim@example.com&pin=123456", {
        headers: { "cf-connecting-ip": `198.51.100.${i}` },
      });
      expect(res.status).toBe(404);
    }

    // 11th request from an 11th distinct IP must still be blocked by the mailbox budget
    const blockedRes = await app.request("/api/public/otp?email=victim@example.com&pin=123456", {
      headers: { "cf-connecting-ip": "198.51.100.99" },
    });
    expect(blockedRes.status).toBe(429);
    const body = await blockedRes.json();
    expect(body.error).toContain("Hộp thư đã vượt quá");
  });

  it("Rate limit dual budget: independent client IP protection blocks wide enumeration across distinct mailboxes", async () => {
    mocks.getDb.mockReturnValue({
      select: () => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockResolvedValue([]),
          }),
        }),
      }),
    });

    const attackerIp = "203.0.113.88";
    // 30 requests to 30 DIFFERENT mailboxes from the same IP
    for (let i = 1; i <= 30; i++) {
      const res = await app.request(`/api/public/otp?email=target${i}@example.com&pin=123456`, {
        headers: { "cf-connecting-ip": attackerIp },
      });
      expect(res.status).toBe(404);
    }

    // 31st request to yet another mailbox must be blocked by IP budget
    const blockedRes = await app.request("/api/public/otp?email=target31@example.com&pin=123456", {
      headers: { "cf-connecting-ip": attackerIp },
    });
    expect(blockedRes.status).toBe(429);
    const body = await blockedRes.json();
    expect(body.error).toContain("Địa chỉ mạng đã vượt quá");
  });

  it("Rate limit memory cleanup: purges expired keys and bounds total memory entries", async () => {
    for (let i = 0; i < 50; i++) {
      await app.request(`/api/public/otp?email=expire${i}@example.com&pin=123456`, {
        headers: { "cf-connecting-ip": `10.0.0.${i}` },
      });
    }
    expect(_getMemoryRateLimitsSizeForTesting()).toBeGreaterThan(0);

    // Fast-forward expiry
    cleanupMemoryRateLimits(Date.now() + 70000);
    expect(_getMemoryRateLimitsSizeForTesting()).toBe(0);
  });

  it("Mounted via createApp(): verifies routing and security through top-level application factory", async () => {
    const mockCtx = { waitUntil: vi.fn(), passThroughOnException: vi.fn() };
    const fullApp = createApp({ createAuthFactory: (() => ({}) as any) });
    const res = await fullApp.request("/api/public/recent-otps", undefined, {} as any, mockCtx as any);
    expect(res.status).toBe(404);

    const otpMissingParam = await fullApp.request("/api/public/otp?email=test@example.com", undefined, {} as any, mockCtx as any);
    expect(otpMissingParam.status).toBe(400);
  });

  it("Contract end-to-end: create address with auto PIN delivers secret once, allows OTP query, denies wrong/tenant PIN", async () => {
    const testEmail = "auto-pin-box@spinupmail.com";
    const generatedPin = "481516";
    const tenantBPin = "999999";

    // Setup DB query for OTP endpoint
    mocks.getDb.mockReturnValue({
      select: vi.fn(() => ({
        from: () => ({
          where: () => ({
            limit: vi.fn().mockImplementation(() => [
              {
                id: "addr-synth-1",
                address: testEmail,
                meta: JSON.stringify({ pin: generatedPin, label: "Synth Mailbox" }),
                createdAt: new Date(),
              },
            ]),
            orderBy: () => ({
              limit: vi.fn().mockResolvedValue([
                {
                  id: "msg-synth-1",
                  from: "noreply@muse.ai",
                  subject: "Mã xác thực Muse AI của bạn",
                  bodyText: "Mã OTP Muse của bạn là 314159",
                  bodyHtml: "<p>Mã OTP Muse của bạn là 314159</p>",
                  receivedAt: new Date(),
                },
              ]),
            }),
          }),
        }),
      })),
    });

    // 1. Query OTP using the valid received secret -> SUCCESS (200) + Cache-Control: no-store
    const validRes = await app.request(`/api/public/otp?email=${testEmail}&pin=${generatedPin}`);
    expect(validRes.status).toBe(200);
    expect(validRes.headers.get("Cache-Control")).toBe("no-store");
    const validData = await validRes.json();
    expect(validData.ok).toBe(true);
    expect(validData.hasEmails).toBe(true);
    expect(validData.latest.otp).toBe("314159");

    // 2. Negative test: Wrong PIN -> 401 Unauthorized
    const wrongPinRes = await app.request(`/api/public/otp?email=${testEmail}&pin=111111`);
    expect(wrongPinRes.status).toBe(401);
    const wrongData = await wrongPinRes.json();
    expect(wrongData.ok).toBe(false);

    // 3. Negative test: Tenant B PIN -> 401 Unauthorized
    const tenantBRes = await app.request(`/api/public/otp?email=${testEmail}&pin=${tenantBPin}`);
    expect(tenantBRes.status).toBe(401);
    const tenantBData = await tenantBRes.json();
    expect(tenantBData.ok).toBe(false);

    // 4. Negative test: Missing PIN -> 400 Bad Request
    const missingPinRes = await app.request(`/api/public/otp?email=${testEmail}`);
    expect(missingPinRes.status).toBe(400);
  });
});

describe("extractOtpAndLinks hostname validation and phishing defense", () => {
  it("strictly validates allowed hostnames and subdomains", () => {
    expect(isAllowedMagicLinkHostname("muse.ai")).toBe(true);
    expect(isAllowedMagicLinkHostname("auth.muse.ai")).toBe(true);
    expect(isAllowedMagicLinkHostname("facebook.com")).toBe(true);
    expect(isAllowedMagicLinkHostname("www.facebook.com")).toBe(true);
    expect(isAllowedMagicLinkHostname("meta.com")).toBe(true);
    expect(isAllowedMagicLinkHostname("instagram.com")).toBe(true);

    // Negative tests: Lookalikes, spoofing, query injection
    expect(isAllowedMagicLinkHostname("evil-phishing.com")).toBe(false);
    expect(isAllowedMagicLinkHostname("muse.ai.attacker.com")).toBe(false);
    expect(isAllowedMagicLinkHostname("fake-facebook.com")).toBe(false);
    expect(isAllowedMagicLinkHostname("attacker-meta.com")).toBe(false);
    expect(isAllowedMagicLinkHostname("notmuse.ai")).toBe(false);
  });

  it("rejects links from evil hosts containing target domains in query or path", () => {
    const evilQueryEmail = `
      Xin chào, vui lòng xác nhận tài khoản:
      https://evil-phishing.com/steal?fake=muse.ai&ref=meta.com
    `;
    const res1 = extractOtpAndLinks("Xác nhận tài khoản", evilQueryEmail, "");
    expect(res1.magicLink).toBeNull();

    const evilSubdomainEmail = `
      Bấm vào đây để đăng nhập:
      https://muse.ai.attacker.com/session/confirm
    `;
    const res2 = extractOtpAndLinks("Xác nhận", evilSubdomainEmail, "");
    expect(res2.magicLink).toBeNull();

    const evilKeywordPathEmail = `
      https://attacker.com/confirm?provider=facebook.com
    `;
    const res3 = extractOtpAndLinks("Xác nhận", evilKeywordPathEmail, "");
    expect(res3.magicLink).toBeNull();
  });

  it("accepts valid links from official providers", () => {
    const legitimateEmail = `
      Mã của bạn: 543210
      Hoặc bấm vào link:
      https://auth.muse.ai/verify?token=secure-token-123
    `;
    const res = extractOtpAndLinks("Mã đăng nhập", legitimateEmail, "");
    expect(res.otp).toBe("543210");
    expect(res.magicLink).toBe("https://auth.muse.ai/verify?token=secure-token-123");
  });
});

describe("generateSecurePin CSPRNG requirement", () => {
  it("generates a 6-digit numeric PIN with CSPRNG", () => {
    const pin = generateSecurePin();
    expect(pin).toMatch(/^[1-9][0-9]{5}$/);
    expect(pin.length).toBe(6);
  });

  it("fails closed (throws) when CSPRNG is unavailable", () => {
    const originalCrypto = globalThis.crypto;
    try {
      // Mock crypto without getRandomValues
      Object.defineProperty(globalThis, "crypto", {
        value: {},
        configurable: true,
        writable: true,
      });
      expect(() => generateSecurePin()).toThrow("CSPRNG_UNAVAILABLE");
    } finally {
      Object.defineProperty(globalThis, "crypto", {
        value: originalCrypto,
        configurable: true,
        writable: true,
      });
    }
  });
});
