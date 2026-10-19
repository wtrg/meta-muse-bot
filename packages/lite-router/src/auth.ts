export const LITE_TIMESTAMP_HEADER = "X-Spinupmail-Lite-Timestamp";
export const LITE_NONCE_HEADER = "X-Spinupmail-Lite-Nonce";
export const LITE_EVENT_ID_HEADER = "X-Spinupmail-Lite-Event-Id";
export const LITE_SIGNATURE_HEADER = "X-Spinupmail-Lite-Signature";

const SIGNATURE_PREFIX = "v1=";
const DEFAULT_TOLERANCE_SECONDS = 300;

export type LiteWebhookHeadersInput = {
  body: string;
  secret: string;
  eventId: string;
  timestamp: number;
  nonce: string;
  bearerToken?: string;
};

export type VerifyLiteWebhookOptions = {
  toleranceSeconds?: number;
  now?: () => Date;
  bearerToken?: string;
};

export type VerifyLiteWebhookResult =
  | {
      ok: true;
      body: string;
      eventId: string;
      timestamp: number;
      nonce: string;
    }
  | {
      ok: false;
      reason:
        | "missing_header"
        | "invalid_timestamp"
        | "stale_timestamp"
        | "invalid_bearer"
        | "invalid_signature";
    };

const textEncoder = new TextEncoder();

const toHex = (bytes: Uint8Array) =>
  Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");

const fromHex = (value: string) => {
  if (!/^[0-9a-f]+$/i.test(value) || value.length % 2 !== 0) return null;
  const bytes = new Uint8Array(value.length / 2);
  for (let index = 0; index < value.length; index += 2) {
    bytes[index / 2] = Number.parseInt(value.slice(index, index + 2), 16);
  }
  return bytes;
};

const timingSafeEqual = (left: Uint8Array, right: Uint8Array) => {
  let diff = left.length ^ right.length;
  const length = Math.max(left.length, right.length);

  for (let index = 0; index < length; index += 1) {
    diff |= (left[index] ?? 0) ^ (right[index] ?? 0);
  }

  return diff === 0;
};

export const buildLiteSignatureInput = ({
  timestamp,
  nonce,
  body,
}: {
  timestamp: number;
  nonce: string;
  body: string;
}) => `${timestamp}\n${nonce}\n${body}`;

export const signLiteWebhookBody = async ({
  body,
  secret,
  timestamp,
  nonce,
}: {
  body: string;
  secret: string;
  timestamp: number;
  nonce: string;
}) => {
  const key = await crypto.subtle.importKey(
    "raw",
    textEncoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    textEncoder.encode(buildLiteSignatureInput({ timestamp, nonce, body }))
  );

  return `${SIGNATURE_PREFIX}${toHex(new Uint8Array(signature))}`;
};

export const createLiteWebhookHeaders = async ({
  body,
  secret,
  eventId,
  timestamp,
  nonce,
  bearerToken,
}: LiteWebhookHeadersInput) => {
  const signature = await signLiteWebhookBody({
    body,
    secret,
    timestamp,
    nonce,
  });
  const headers = new Headers({
    "content-type": "application/json",
    [LITE_TIMESTAMP_HEADER]: String(timestamp),
    [LITE_NONCE_HEADER]: nonce,
    [LITE_EVENT_ID_HEADER]: eventId,
    [LITE_SIGNATURE_HEADER]: signature,
  });

  if (bearerToken) {
    headers.set("authorization", `Bearer ${bearerToken}`);
  }

  return headers;
};

const readBearerToken = (authorization: string | null) => {
  const match = /^Bearer\s+(.+)$/i.exec(authorization ?? "");
  return match?.[1] ?? null;
};

export const verifyLiteWebhookRequest = async (
  request: Request,
  secret: string,
  options: VerifyLiteWebhookOptions = {}
): Promise<VerifyLiteWebhookResult> => {
  const timestampHeader = request.headers.get(LITE_TIMESTAMP_HEADER);
  const nonce = request.headers.get(LITE_NONCE_HEADER);
  const eventId = request.headers.get(LITE_EVENT_ID_HEADER);
  const signature = request.headers.get(LITE_SIGNATURE_HEADER);

  if (!timestampHeader || !nonce || !eventId || !signature) {
    return { ok: false, reason: "missing_header" };
  }

  if (options.bearerToken) {
    const bearerToken = readBearerToken(request.headers.get("authorization"));
    if (
      !bearerToken ||
      !timingSafeEqual(
        textEncoder.encode(bearerToken),
        textEncoder.encode(options.bearerToken)
      )
    ) {
      return { ok: false, reason: "invalid_bearer" };
    }
  }

  const timestamp = Number(timestampHeader);
  if (!Number.isSafeInteger(timestamp) || timestamp <= 0) {
    return { ok: false, reason: "invalid_timestamp" };
  }

  const nowSeconds = Math.floor(
    (options.now?.() ?? new Date()).getTime() / 1000
  );
  const toleranceSeconds =
    options.toleranceSeconds ?? DEFAULT_TOLERANCE_SECONDS;
  if (Math.abs(nowSeconds - timestamp) > toleranceSeconds) {
    return { ok: false, reason: "stale_timestamp" };
  }

  if (!signature.startsWith(SIGNATURE_PREFIX)) {
    return { ok: false, reason: "invalid_signature" };
  }

  const body = await request.text();
  const expectedSignature = await signLiteWebhookBody({
    body,
    secret,
    timestamp,
    nonce,
  });
  const receivedBytes = fromHex(signature.slice(SIGNATURE_PREFIX.length));
  const expectedBytes = fromHex(
    expectedSignature.slice(SIGNATURE_PREFIX.length)
  );

  if (
    !receivedBytes ||
    !expectedBytes ||
    !timingSafeEqual(receivedBytes, expectedBytes)
  ) {
    return { ok: false, reason: "invalid_signature" };
  }

  return {
    ok: true,
    body,
    eventId,
    timestamp,
    nonce,
  };
};
