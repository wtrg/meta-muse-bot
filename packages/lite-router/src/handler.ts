import type {
  ExecutionContext,
  ExportedHandler,
  ForwardableEmailMessage,
} from "@cloudflare/workers-types";
import { createLiteWebhookHeaders } from "./auth";
import { readRawWithLimit, parseLiteEmail } from "./parser";
import { buildLiteEmailPayload } from "./payload";
import { parseWebhookUrl } from "./sanitize";
import type { LiteRouterEnv, LiteRouterOptions } from "./types";

const DEFAULT_MAX_BYTES = 524_288;
const DEFAULT_BODY_MAX_BYTES = 65_536;
const DEFAULT_DELIVERY_TIMEOUT_MS = 8_000;

type LiteConfig = {
  webhookUrl: string;
  webhookSecret: string;
  bearerToken?: string;
  allowedRecipients: Set<string>;
  maxBytes: number;
  bodyMaxBytes: number;
  includeRaw: boolean;
  deliveryTimeoutMs: number;
  rejectOnFailure: boolean;
};

const parsePositiveInteger = (value: string | undefined, fallback: number) => {
  if (!value?.trim()) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) return fallback;
  return parsed;
};

const parseBoolean = (value: string | undefined, fallback: boolean) => {
  if (!value?.trim()) return fallback;
  if (/^(true|1|yes|on)$/i.test(value)) return true;
  if (/^(false|0|no|off)$/i.test(value)) return false;
  return fallback;
};

const parseRecipients = (value: string | undefined) =>
  new Set(
    (value ?? "")
      .split(",")
      .map(item => item.trim().toLowerCase())
      .filter(Boolean)
  );

const readConfig = (env: LiteRouterEnv): LiteConfig | null => {
  const webhookUrl = parseWebhookUrl(env.LITE_WEBHOOK_URL);
  const webhookSecret = env.LITE_WEBHOOK_SECRET?.trim();

  if (!webhookUrl || !webhookSecret) return null;

  return {
    webhookUrl,
    webhookSecret,
    bearerToken: env.LITE_WEBHOOK_BEARER_TOKEN?.trim() || undefined,
    allowedRecipients: parseRecipients(env.LITE_ALLOWED_RECIPIENTS),
    maxBytes: parsePositiveInteger(env.LITE_MAX_BYTES, DEFAULT_MAX_BYTES),
    bodyMaxBytes: parsePositiveInteger(
      env.LITE_BODY_MAX_BYTES,
      DEFAULT_BODY_MAX_BYTES
    ),
    includeRaw: parseBoolean(env.LITE_INCLUDE_RAW, false),
    deliveryTimeoutMs: parsePositiveInteger(
      env.LITE_DELIVERY_TIMEOUT_MS,
      DEFAULT_DELIVERY_TIMEOUT_MS
    ),
    rejectOnFailure: parseBoolean(env.LITE_REJECT_ON_FAILURE, true),
  };
};

const rejectOrDrop = (
  message: ForwardableEmailMessage,
  config: Pick<LiteConfig, "rejectOnFailure"> | null,
  reason: string
) => {
  if (config?.rejectOnFailure ?? true) {
    message.setReject(reason);
  }
};

const normalizeRecipient = (value: string) => value.trim().toLowerCase();

const validateRawSize = (value: unknown) => {
  if (!Number.isSafeInteger(value) || (value as number) < 0) return null;
  return value as number;
};

const defaultCreateNonce = () => {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
};

const deliverWebhook = async ({
  fetchImpl,
  config,
  body,
  eventId,
  timestamp,
  nonce,
}: {
  fetchImpl: typeof fetch;
  config: LiteConfig;
  body: string;
  eventId: string;
  timestamp: number;
  nonce: string;
}) => {
  const headers = await createLiteWebhookHeaders({
    body,
    secret: config.webhookSecret,
    eventId,
    timestamp,
    nonce,
    bearerToken: config.bearerToken,
  });
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    config.deliveryTimeoutMs
  );

  try {
    const response = await fetchImpl(config.webhookUrl, {
      method: "POST",
      headers,
      body,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Webhook delivery failed with HTTP ${response.status}`);
    }
  } finally {
    clearTimeout(timeout);
  }
};

export const handleLiteEmail = async (
  message: ForwardableEmailMessage,
  env: LiteRouterEnv,
  ctx: ExecutionContext,
  options: LiteRouterOptions = {}
) => {
  void ctx;
  const config = readConfig(env);
  if (!config) {
    rejectOrDrop(message, null, "Lite router is not configured");
    return;
  }

  const recipient = normalizeRecipient(message.to);
  if (
    config.allowedRecipients.size > 0 &&
    !config.allowedRecipients.has(recipient)
  ) {
    rejectOrDrop(message, config, "Recipient is not allowed");
    return;
  }

  const rawSize = validateRawSize(message.rawSize);
  if (rawSize === null) {
    rejectOrDrop(message, config, "Invalid message size");
    return;
  }
  if (rawSize > config.maxBytes) {
    rejectOrDrop(message, config, "Message exceeds lite router size limit");
    return;
  }

  try {
    const rawResult = await readRawWithLimit(message.raw, config.maxBytes);
    if (rawResult.truncated) {
      rejectOrDrop(message, config, "Message exceeds lite router size limit");
      return;
    }

    const now = options.now?.() ?? new Date();
    const eventId = options.createEventId?.() ?? crypto.randomUUID();
    const parsed = await parseLiteEmail(
      rawResult.rawBytes,
      config.bodyMaxBytes
    );
    const payload = buildLiteEmailPayload({
      message,
      eventId,
      occurredAt: now,
      rawSize,
      rawResult,
      parsed,
      includeRaw: config.includeRaw,
    });
    const body = JSON.stringify(payload);

    await deliverWebhook({
      fetchImpl: options.fetch ?? fetch,
      config,
      body,
      eventId,
      timestamp: Math.floor(now.getTime() / 1000),
      nonce: options.createNonce?.() ?? defaultCreateNonce(),
    });
  } catch (error) {
    console.error("[lite-router] Failed to route inbound email", { error });
    rejectOrDrop(message, config, "Webhook delivery failed");
  }
};

export const createLiteRouter = (
  options: LiteRouterOptions = {}
): ExportedHandler<LiteRouterEnv> => ({
  fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return Response.json({
        status: "ok",
        timestamp: new Date().toISOString(),
      });
    }

    return Response.json({ error: "not found" }, { status: 404 });
  },
  email(message, env, ctx) {
    return handleLiteEmail(message, env, ctx, options);
  },
});
