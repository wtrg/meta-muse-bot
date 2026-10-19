import {
  createLiteWebhookHeaders,
  LITE_EVENT_ID_HEADER,
  LITE_NONCE_HEADER,
  LITE_SIGNATURE_HEADER,
  LITE_TIMESTAMP_HEADER,
  verifyLiteWebhookRequest,
} from "../src/auth";

const buildSignedRequest = async ({
  body = '{"ok":true}',
  secret = "secret",
  bearerToken,
  timestamp = 1_800_000_000,
}: {
  body?: string;
  secret?: string;
  bearerToken?: string;
  timestamp?: number;
} = {}) => {
  const headers = await createLiteWebhookHeaders({
    body,
    secret,
    eventId: "evt_1",
    timestamp,
    nonce: "nonce_1",
    bearerToken,
  });

  return new Request("https://receiver.example/webhook", {
    method: "POST",
    headers,
    body,
  });
};

describe("lite webhook auth", () => {
  it("verifies a signed request", async () => {
    const request = await buildSignedRequest();

    const result = await verifyLiteWebhookRequest(request, "secret", {
      now: () => new Date(1_800_000_000_000),
    });

    expect(result).toEqual({
      ok: true,
      body: '{"ok":true}',
      eventId: "evt_1",
      timestamp: 1_800_000_000,
      nonce: "nonce_1",
    });
  });

  it("rejects a tampered body", async () => {
    const request = await buildSignedRequest({ body: '{"ok":true}' });
    const headers = new Headers(request.headers);

    const result = await verifyLiteWebhookRequest(
      new Request("https://receiver.example/webhook", {
        method: "POST",
        headers,
        body: '{"ok":false}',
      }),
      "secret",
      { now: () => new Date(1_800_000_000_000) }
    );

    expect(result).toEqual({ ok: false, reason: "invalid_signature" });
  });

  it("rejects stale timestamps", async () => {
    const request = await buildSignedRequest({ timestamp: 1_800_000_000 });

    const result = await verifyLiteWebhookRequest(request, "secret", {
      now: () => new Date(1_800_001_000_000),
      toleranceSeconds: 60,
    });

    expect(result).toEqual({ ok: false, reason: "stale_timestamp" });
  });

  it("rejects missing signature headers", async () => {
    const result = await verifyLiteWebhookRequest(
      new Request("https://receiver.example/webhook", {
        method: "POST",
        headers: {
          [LITE_TIMESTAMP_HEADER]: "1800000000",
          [LITE_NONCE_HEADER]: "nonce_1",
          [LITE_EVENT_ID_HEADER]: "evt_1",
        },
        body: "{}",
      }),
      "secret",
      { now: () => new Date(1_800_000_000_000) }
    );

    expect(result).toEqual({ ok: false, reason: "missing_header" });
  });

  it("verifies optional bearer authentication", async () => {
    const request = await buildSignedRequest({ bearerToken: "receiver-token" });

    const result = await verifyLiteWebhookRequest(request, "secret", {
      now: () => new Date(1_800_000_000_000),
      bearerToken: "receiver-token",
    });

    expect(result.ok).toBe(true);
  });

  it("rejects an invalid bearer token", async () => {
    const request = await buildSignedRequest({ bearerToken: "wrong-token" });

    const result = await verifyLiteWebhookRequest(request, "secret", {
      now: () => new Date(1_800_000_000_000),
      bearerToken: "receiver-token",
    });

    expect(result).toEqual({ ok: false, reason: "invalid_bearer" });
  });

  it("uses the v1 signature prefix", async () => {
    const request = await buildSignedRequest();

    expect(request.headers.get(LITE_SIGNATURE_HEADER)).toMatch(/^v1=/);
  });
});
