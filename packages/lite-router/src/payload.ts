import type { ForwardableEmailMessage } from "@cloudflare/workers-types";
import type { LiteEmailWebhookPayload } from "./types";
import type { ParsedLiteEmail, ReadRawResult } from "./parser";
import { cleanMetadataString } from "./sanitize";

const header = (headers: Headers, name: string) => {
  const value = headers.get(name);
  return cleanMetadataString(value, 1_000);
};

export const buildLiteEmailPayload = ({
  message,
  eventId,
  occurredAt,
  rawSize,
  rawResult,
  parsed,
  includeRaw,
}: {
  message: ForwardableEmailMessage;
  eventId: string;
  occurredAt: Date;
  rawSize: number;
  rawResult: ReadRawResult;
  parsed: ParsedLiteEmail;
  includeRaw: boolean;
}): LiteEmailWebhookPayload => ({
  eventId,
  eventType: "email.received",
  occurredAt: occurredAt.toISOString(),
  envelope: {
    from: cleanMetadataString(message.from, 320) ?? "",
    to: cleanMetadataString(message.to, 320) ?? "",
  },
  headers: {
    messageId: header(message.headers, "message-id"),
    inReplyTo: header(message.headers, "in-reply-to"),
    references: header(message.headers, "references"),
    subject: header(message.headers, "subject"),
    from: header(message.headers, "from"),
    to: header(message.headers, "to"),
    cc: header(message.headers, "cc"),
    date: header(message.headers, "date"),
  },
  subject: parsed.subject ?? header(message.headers, "subject"),
  bodies: {
    text: parsed.text,
    html: parsed.html,
    truncated: rawResult.truncated,
  },
  raw: {
    size: rawSize,
    readBytes: rawResult.readBytes,
    truncated: rawResult.truncated,
    included: includeRaw,
    content: includeRaw ? rawResult.raw : null,
  },
  attachments: parsed.attachments,
});
