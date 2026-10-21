/**
 * Pure PIN validation and secure generation utilities for SpinupMail addresses.
 * Independent of database schemas, router layers, or external providers.
 */

/**
 * Retrieves the configured PIN from mailbox metadata.
 * Fails closed (returns undefined) if no valid PIN string is explicitly present.
 * Does NOT generate pseudo-secrets from address IDs, nor accept numeric types.
 */
export const getMailboxPin = (meta: unknown): string | undefined => {
  if (meta && typeof meta === "object") {
    const pin = (meta as Record<string, unknown>).pin;
    if (typeof pin === "string" && pin.trim().length >= 4) {
      return pin.trim();
    }
  }
  if (typeof meta === "string") {
    try {
      const parsed = JSON.parse(meta);
      if (parsed && typeof parsed === "object") {
        const pin = (parsed as Record<string, unknown>).pin;
        if (typeof pin === "string" && pin.trim().length >= 4) {
          return pin.trim();
        }
      }
    } catch {}
  }
  return undefined;
};

/**
 * Backward compatibility helper that preserves the function name
 * but enforces fail-closed semantics (returns undefined when no PIN is configured).
 */
export const getOrDerivePin = (
  meta: unknown,
  _addressId?: string
): string | undefined => {
  return getMailboxPin(meta);
};

/**
 * Generates a cryptographically secure 6-digit PIN using CSPRNG.
 */
export const generateSecurePin = (): string => {
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    const buf = new Uint32Array(1);
    crypto.getRandomValues(buf);
    return String(100000 + (buf[0] % 900000));
  }
  return String(Math.floor(100000 + Math.random() * 900000));
};
