import PostalMime, { type Attachment } from "postal-mime";
import type { LiteEmailAttachmentMetadata } from "./types";
import {
  cleanMetadataString,
  sanitizeAttachmentFilename,
  sanitizeContentType,
} from "./sanitize";

export type ReadRawResult = {
  raw: string;
  rawBytes: Uint8Array;
  readBytes: number;
  truncated: boolean;
};

export type ParsedLiteEmail = {
  subject: string | null;
  text: string | null;
  html: string | null;
  attachments: LiteEmailAttachmentMetadata[];
};

const textDecoder = new TextDecoder();
const textEncoder = new TextEncoder();

export const readRawWithLimit = async (
  stream: ReadableStream<Uint8Array>,
  maxBytes: number
): Promise<ReadRawResult> => {
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let readBytes = 0;
  let truncated = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    if (!value || value.byteLength === 0) continue;

    if (readBytes + value.byteLength > maxBytes) {
      const remaining = Math.max(0, maxBytes - readBytes);
      if (remaining > 0) {
        const slice = value.slice(0, remaining);
        chunks.push(slice);
        readBytes += slice.byteLength;
      }
      truncated = true;
      await reader.cancel();
      break;
    }

    chunks.push(value);
    readBytes += value.byteLength;
  }

  const rawBytes = new Uint8Array(readBytes);
  let offset = 0;
  for (const chunk of chunks) {
    rawBytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  return {
    rawBytes,
    raw: textDecoder.decode(rawBytes),
    readBytes,
    truncated,
  };
};

const contentSize = (attachment: Attachment) => {
  const { content } = attachment;
  if (typeof content === "string")
    return textEncoder.encode(content).byteLength;
  return content.byteLength;
};

const capBody = (value: string | undefined, maxBytes: number) => {
  if (!value || value.trim().length === 0) return null;

  let bytes = 0;
  let output = "";
  for (const character of value) {
    const size = textEncoder.encode(character).byteLength;
    if (bytes + size > maxBytes) break;
    bytes += size;
    output += character;
  }

  return output.length > 0 ? output : null;
};

export const parseLiteEmail = async (
  rawBytes: Uint8Array,
  bodyMaxBytes: number
): Promise<ParsedLiteEmail> => {
  const parser = new PostalMime({ attachmentEncoding: "arraybuffer" });
  const parsed = await parser.parse(rawBytes);

  return {
    subject: cleanMetadataString(parsed.subject, 500),
    text: capBody(parsed.text, bodyMaxBytes),
    html: capBody(
      typeof parsed.html === "string" ? parsed.html : undefined,
      bodyMaxBytes
    ),
    attachments: (parsed.attachments ?? []).map(attachment => ({
      filename: sanitizeAttachmentFilename(attachment.filename),
      contentType: sanitizeContentType(attachment.mimeType),
      disposition: attachment.disposition,
      contentId: cleanMetadataString(attachment.contentId, 300),
      size: contentSize(attachment),
    })),
  };
};
