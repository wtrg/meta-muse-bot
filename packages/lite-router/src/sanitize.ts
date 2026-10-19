const WHITESPACE_RUN = /\s+/g;
const PATH_SEPARATORS = /[\\/]+/g;

const stripControlCharacters = (value: string) =>
  Array.from(value)
    .filter(character => {
      const codePoint = character.codePointAt(0);
      return (
        codePoint !== undefined &&
        (codePoint > 0x1f ||
          codePoint === 0x09 ||
          codePoint === 0x0a ||
          codePoint === 0x0d) &&
        codePoint !== 0x7f
      );
    })
    .join("");

export const cleanMetadataString = (
  value: string | null | undefined,
  maxLength: number
) => {
  const cleaned = value
    ? stripControlCharacters(value).replace(WHITESPACE_RUN, " ").trim()
    : null;

  if (!cleaned) return null;
  return Array.from(cleaned).slice(0, maxLength).join("");
};

export const sanitizeAttachmentFilename = (
  value: string | null | undefined,
  maxLength = 180
) => {
  const cleaned = cleanMetadataString(
    value?.replace(PATH_SEPARATORS, "_"),
    maxLength
  );
  return cleaned || null;
};

export const sanitizeContentType = (value: string | null | undefined) => {
  const cleaned = cleanMetadataString(value, 120);
  return cleaned || "application/octet-stream";
};

export const parseWebhookUrl = (value: string | undefined) => {
  const cleaned = value?.trim();
  if (!cleaned) return null;

  try {
    const url = new URL(cleaned);
    if (url.protocol !== "https:" && !isLocalHttpUrl(url)) return null;
    url.hash = "";
    return url.toString();
  } catch {
    return null;
  }
};

const isLocalHttpUrl = (url: URL) => {
  if (url.protocol !== "http:") return false;
  const hostname = url.hostname.toLowerCase();
  return (
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1"
  );
};
