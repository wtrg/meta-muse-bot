import { Hono } from "hono";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { AppHonoEnv } from "@/app/types";

const mocks = vi.hoisted(() => ({
  createEmailAddress: vi.fn(),
  listEmailAddresses: vi.fn(),
}));

vi.mock("@/modules/email-addresses/service", () => ({
  createEmailAddress: mocks.createEmailAddress,
  listEmailAddresses: mocks.listEmailAddresses,
  deleteEmailAddress: vi.fn(),
  getEmailAddress: vi.fn(),
  listRecentAddressActivity: vi.fn(),
  updateEmailAddress: vi.fn(),
}));

import { createEmailAddressesRouter } from "@/modules/email-addresses/router";

describe("email-addresses router (HTTP schema & Cache-Control)", () => {
  let app: Hono<AppHonoEnv>;

  beforeEach(() => {
    vi.clearAllMocks();
    app = new Hono<AppHonoEnv>();
    app.use("*", async (c, next) => {
      c.set("session", {
        session: { id: "sess-1", userId: "u-1" },
        user: { id: "u-1", emailVerified: true },
      } as any);
      c.set("organizationId", "org-1");
      c.env = { EMAIL_DOMAINS: "spinupmail.com" } as any;
      await next();
    });
    app.route("/api", createEmailAddressesRouter());
  });

  it("POST /email-addresses accepts top-level generatePin: true, forwards to service, returns Cache-Control: no-store", async () => {
    mocks.createEmailAddress.mockResolvedValueOnce({
      status: 200,
      body: {
        id: "addr-gen-1",
        address: "test-auto@spinupmail.com",
        localPart: "test-auto",
        domain: "spinupmail.com",
        meta: { label: "Auto Box" },
        pin: "555777",
        emailCount: 0,
        createdAt: "2026-10-22T00:00:00.000Z",
      },
    });

    const res = await app.request("/api/email-addresses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        localPart: "test-auto",
        domain: "spinupmail.com",
        acceptedRiskNotice: true,
        generatePin: true,
      }),
    });

    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");

    expect(mocks.createEmailAddress).toHaveBeenCalledTimes(1);
    const callArgs = mocks.createEmailAddress.mock.calls[0][0];
    expect(callArgs.payload.generatePin).toBe(true);

    const data = await res.json();
    expect(data.pin).toBe("555777");
    expect(data.meta.pin).toBeUndefined();
  });

  it("POST /email-addresses rejects invalid request body with 400", async () => {
    const res = await app.request("/api/email-addresses", {
      method: "POST",
      headers: { "Content-Type": "application/json BODY" },
      body: JSON.stringify({
        localPart: "invalid local part with spaces!!!",
      }),
    });

    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toBe("invalid request body");
  });

  it("GET /email-addresses retains Cache-Control: private, max-age=15 and does not leak secrets", async () => {
    mocks.listEmailAddresses.mockResolvedValueOnce({
      items: [
        {
          id: "addr-list-1",
          address: "listed@spinupmail.com",
          localPart: "listed",
          domain: "spinupmail.com",
          meta: { label: "Standard Box" },
          emailCount: 3,
        },
      ],
      total: 1,
    });

    const res = await app.request("/api/email-addresses");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("private, max-age=15");

    const data = await res.json();
    expect(data.items[0].pin).toBeUndefined();
    expect(data.items[0].meta.pin).toBeUndefined();
  });
});
