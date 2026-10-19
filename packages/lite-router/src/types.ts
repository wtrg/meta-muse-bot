export type LiteRouterEnv = {
  LITE_WEBHOOK_URL?: string;
  LITE_WEBHOOK_SECRET?: string;
  LITE_WEBHOOK_BEARER_TOKEN?: string;
  LITE_ALLOWED_RECIPIENTS?: string;
  LITE_MAX_BYTES?: string;
  LITE_BODY_MAX_BYTES?: string;
  LITE_INCLUDE_RAW?: string;
  LITE_DELIVERY_TIMEOUT_MS?: string;
  LITE_REJECT_ON_FAILURE?: string;
};

export type LiteRouterOptions = {
  fetch?: typeof fetch;
  now?: () => Date;
  createEventId?: () => string;
  createNonce?: () => string;
};

export type LiteEmailAttachmentMetadata = {
  filename: string | null;
  contentType: string;
  disposition: "attachment" | "inline" | null;
  contentId: string | null;
  size: number;
};

export type LiteEmailWebhookPayload = {
  eventId: string;
  eventType: "email.received";
  occurredAt: string;
  envelope: {
    from: string;
    to: string;
  };
  headers: {
    messageId: string | null;
    inReplyTo: string | null;
    references: string | null;
    subject: string | null;
    from: string | null;
    to: string | null;
    cc: string | null;
    date: string | null;
  };
  subject: string | null;
  bodies: {
    text: string | null;
    html: string | null;
    truncated: boolean;
  };
  raw: {
    size: number;
    readBytes: number;
    truncated: boolean;
    included: boolean;
    content: string | null;
  };
  attachments: LiteEmailAttachmentMetadata[];
};
