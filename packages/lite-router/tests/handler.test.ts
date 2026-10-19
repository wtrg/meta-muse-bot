import type {
  ExecutionContext,
  ForwardableEmailMessage,
} from "@cloudflare/workers-types";
import {
  handleLiteEmail,
  verifyLiteWebhookRequest,
  type LiteEmailWebhookPayload,
  type LiteRouterEnv,
} from "../src";

const rawEmail = ({
  body = "Hello from lite router",
  subject = "Lite Router Test",
  attachment = false,
}: {
  body?: string;
  subject?: string;
  attachment?: boolean;
} = {}) =>
  attachment
    ? [
        'From: "Sender" <sender@example.com>',
        "To: inbox@example.com",
        `Subject: ${subject}`,
        "Message-ID: <msg-1@example.com>",
        "Date: Sat, 06 Jun 2026 12:00:00 +0000",
        "Content-Type: multipart/mixed; boundary=test-boundary",
        "",
        "--test-boundary",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
        "--test-boundary",
        "Content-Type: text/plain",
        'Content-Disposition: attachment; filename="../../secret\u0007.txt"',
        "Content-ID: <file\u0001id>",
        "",
        "attachment body",
        "--test-boundary--",
      ].join("\r\n")
    : [
        'From: "Sender" <sender@example.com>',
        "To: inbox@example.com",
        `Subject: ${subject}`,
        "Message-ID: <msg-1@example.com>",
        "Date: Sat, 06 Jun 2026 12:00:00 +0000",
        "Content-Type: text/plain; charset=utf-8",
        "",
        body,
      ].join("\r\n");

const streamFromText = (value: string, onStart?: () => void) =>
  new ReadableStream<Uint8Array>({
    start(controller) {
      onStart?.();
      controller.enqueue(new TextEncoder().encode(value));
      controller.close();
    },
  });

const hasUnsafeControlCharacter = (value: string) =>
  Array.from(value).some(character => {
    const codePoint = character.codePointAt(0);
    return (
      codePoint !== undefined &&
      ((codePoint <= 0x1f &&
        codePoint !== 0x09 &&
        codePoint !== 0x0a &&
        codePoint !== 0x0d) ||
        codePoint === 0x7f)
    );
  });

const buildMessage = ({
  raw = rawEmail(),
  rawSize,
  to = "inbox@example.com",
  onRawAccess,
}: {
  raw?: string;
  rawSize?: number;
  to?: string;
  onRawAccess?: () => void;
} = {}) => {
  const headers = new Headers([
    ["from", '"Sender" <sender@example.com>'],
    ["to", "inbox@example.com"],
    ["subject", "Lite Router Test"],
    ["message-id", "<msg-1@example.com>"],
    ["date", "Sat, 06 Jun 2026 12:00:00 +0000"],
  ]);
  let rawStream: ReadableStream<Uint8Array> | null = null;

  return {
    from: "sender@example.com",
    to,
    headers,
    rawSize: rawSize ?? new TextEncoder().encode(raw).byteLength,
    get raw() {
      onRawAccess?.();
      rawStream ??= streamFromText(raw);
      return rawStream;
    },
    setReject: vi.fn(),
    forward: vi.fn(),
  } as unknown as ForwardableEmailMessage & {
    setReject: ReturnType<typeof vi.fn>;
  };
};

const buildEnv = (overrides: Partial<LiteRouterEnv> = {}): LiteRouterEnv => ({
  LITE_WEBHOOK_URL: "https://receiver.example/webhook",
  LITE_WEBHOOK_SECRET: "secret",
  ...overrides,
});

const ctx = {} as ExecutionContext;

describe("lite email handler", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("delivers a signed JSON webhook", async () => {
    const message = buildMessage();
    let request: Request | null = null;
    const fetchMock = vi.fn(
      async (url: string | URL | Request, init?: RequestInit) => {
        request = new Request(url, init);
        return new Response("ok");
      }
    );

    await handleLiteEmail(message, buildEnv(), ctx, {
      fetch: fetchMock as typeof fetch,
      now: () => new Date("2026-06-06T12:00:00.000Z"),
      createEventId: () => "evt_1",
      createNonce: () => "nonce_1",
    });

    expect(message.setReject).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith(
      "https://receiver.example/webhook",
      expect.objectContaining({ method: "POST" })
    );
    expect(request).not.toBeNull();

    const verification = await verifyLiteWebhookRequest(request!, "secret", {
      now: () => new Date("2026-06-06T12:00:00.000Z"),
    });
    expect(verification.ok).toBe(true);
    if (!verification.ok) return;

    const payload = JSON.parse(verification.body) as LiteEmailWebhookPayload;
    expect(payload).toMatchObject({
      eventId: "evt_1",
      eventType: "email.received",
      envelope: {
        from: "sender@example.com",
        to: "inbox@example.com",
      },
      subject: "Lite Router Test",
      raw: {
        included: false,
        content: null,
      },
    });
    expect(payload.bodies.text).toContain("Hello from lite router");
  });

  it("adds optional bearer auth", async () => {
    const message = buildMessage();
    let request: Request | null = null;
    const fetchMock = vi.fn(
      async (url: string | URL | Request, init?: RequestInit) => {
        request = new Request(url, init);
        return new Response("ok");
      }
    );

    await handleLiteEmail(
      message,
      buildEnv({ LITE_WEBHOOK_BEARER_TOKEN: "receiver-token" }),
      ctx,
      {
        fetch: fetchMock as typeof fetch,
        now: () => new Date("2026-06-06T12:00:00.000Z"),
        createEventId: () => "evt_1",
        createNonce: () => "nonce_1",
      }
    );

    expect((request as Request | null)?.headers.get("authorization")).toBe(
      "Bearer receiver-token"
    );
  });

  it("rejects missing required configuration", async () => {
    const message = buildMessage();
    const fetchMock = vi.fn();

    await handleLiteEmail(message, {}, ctx, {
      fetch: fetchMock as typeof fetch,
    });

    expect(message.setReject).toHaveBeenCalledWith(
      "Lite router is not configured"
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects non-https webhook URLs except localhost", async () => {
    const message = buildMessage();
    const fetchMock = vi.fn();

    await handleLiteEmail(
      message,
      buildEnv({ LITE_WEBHOOK_URL: "http://example.com/webhook" }),
      ctx,
      {
        fetch: fetchMock as typeof fetch,
      }
    );

    expect(message.setReject).toHaveBeenCalledWith(
      "Lite router is not configured"
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects recipients outside the allowlist before reading raw", async () => {
    let streamStarted = false;
    const message = buildMessage({
      to: "other@example.com",
      onRawAccess: () => {
        streamStarted = true;
      },
    });
    const fetchMock = vi.fn();

    await handleLiteEmail(
      message,
      buildEnv({ LITE_ALLOWED_RECIPIENTS: "inbox@example.com" }),
      ctx,
      { fetch: fetchMock as typeof fetch }
    );

    expect(message.setReject).toHaveBeenCalledWith("Recipient is not allowed");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(streamStarted).toBe(false);
  });

  it("rejects oversized messages before reading raw", async () => {
    let streamStarted = false;
    const message = buildMessage({
      rawSize: 11,
      onRawAccess: () => {
        streamStarted = true;
      },
    });
    const fetchMock = vi.fn();

    await handleLiteEmail(message, buildEnv({ LITE_MAX_BYTES: "10" }), ctx, {
      fetch: fetchMock as typeof fetch,
    });

    expect(message.setReject).toHaveBeenCalledWith(
      "Message exceeds lite router size limit"
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(streamStarted).toBe(false);
  });

  it("rejects non-2xx delivery failures", async () => {
    const message = buildMessage();

    await handleLiteEmail(message, buildEnv(), ctx, {
      fetch: vi.fn(
        async () => new Response("nope", { status: 500 })
      ) as typeof fetch,
      now: () => new Date("2026-06-06T12:00:00.000Z"),
      createEventId: () => "evt_1",
      createNonce: () => "nonce_1",
    });

    expect(message.setReject).toHaveBeenCalledWith("Webhook delivery failed");
  });

  it("drops delivery failures when reject-on-failure is disabled", async () => {
    const message = buildMessage();

    await handleLiteEmail(
      message,
      buildEnv({ LITE_REJECT_ON_FAILURE: "false" }),
      ctx,
      {
        fetch: vi.fn(
          async () => new Response("nope", { status: 500 })
        ) as typeof fetch,
      }
    );

    expect(message.setReject).not.toHaveBeenCalled();
  });

  it("truncates body text without including raw by default", async () => {
    const message = buildMessage({
      raw: rawEmail({ body: "abcdefghijklmnopqrstuvwxyz" }),
    });
    let request: Request | null = null;

    await handleLiteEmail(
      message,
      buildEnv({ LITE_BODY_MAX_BYTES: "5" }),
      ctx,
      {
        fetch: vi.fn(
          async (url: string | URL | Request, init?: RequestInit) => {
            request = new Request(url, init);
            return new Response("ok");
          }
        ) as typeof fetch,
        now: () => new Date("2026-06-06T12:00:00.000Z"),
        createEventId: () => "evt_1",
        createNonce: () => "nonce_1",
      }
    );

    const verification = await verifyLiteWebhookRequest(request!, "secret", {
      now: () => new Date("2026-06-06T12:00:00.000Z"),
    });
    expect(verification.ok).toBe(true);
    if (!verification.ok) return;

    const payload = JSON.parse(verification.body) as LiteEmailWebhookPayload;
    expect(payload.bodies.text).toBe("abcde");
    expect(payload.raw.included).toBe(false);
    expect(payload.raw.content).toBeNull();
  });

  it("includes raw content only when configured", async () => {
    const raw = rawEmail();
    const message = buildMessage({ raw });
    let request: Request | null = null;

    await handleLiteEmail(
      message,
      buildEnv({ LITE_INCLUDE_RAW: "true" }),
      ctx,
      {
        fetch: vi.fn(
          async (url: string | URL | Request, init?: RequestInit) => {
            request = new Request(url, init);
            return new Response("ok");
          }
        ) as typeof fetch,
        now: () => new Date("2026-06-06T12:00:00.000Z"),
        createEventId: () => "evt_1",
        createNonce: () => "nonce_1",
      }
    );

    const verification = await verifyLiteWebhookRequest(request!, "secret", {
      now: () => new Date("2026-06-06T12:00:00.000Z"),
    });
    expect(verification.ok).toBe(true);
    if (!verification.ok) return;

    const payload = JSON.parse(verification.body) as LiteEmailWebhookPayload;
    expect(payload.raw.included).toBe(true);
    expect(payload.raw.content).toBe(raw);
  });

  it("cleans metadata and attachment filenames", async () => {
    const message = buildMessage({
      raw: rawEmail({
        subject: "Subject\u0007 with\ncontrols",
        attachment: true,
      }),
    });
    let request: Request | null = null;

    await handleLiteEmail(message, buildEnv(), ctx, {
      fetch: vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        request = new Request(url, init);
        return new Response("ok");
      }) as typeof fetch,
      now: () => new Date("2026-06-06T12:00:00.000Z"),
      createEventId: () => "evt_1",
      createNonce: () => "nonce_1",
    });

    const verification = await verifyLiteWebhookRequest(request!, "secret", {
      now: () => new Date("2026-06-06T12:00:00.000Z"),
    });
    expect(verification.ok).toBe(true);
    if (!verification.ok) return;

    const payload = JSON.parse(verification.body) as LiteEmailWebhookPayload;
    expect(hasUnsafeControlCharacter(payload.subject ?? "")).toBe(false);
    expect(payload.attachments[0]).toMatchObject({
      filename: ".._.._secret.txt",
      contentType: "text/plain",
      contentId: "<fileid>",
    });
    expect(payload.attachments[0]?.filename).not.toMatch(/[\\/]/);
  });
});
