/**
 * Pure PIN derivation utility for SpinupMail addresses.
 * Independent of database schemas, router layers, or external providers.
 */
export const getOrDerivePin = (meta: unknown, addressId: string): string => {
  if (meta && typeof meta === "object") {
    const pin = (meta as Record<string, unknown>).pin;
    if (typeof pin === "string" && pin.length >= 4) return pin;
    if (typeof pin === "number") return String(pin);
  }
  if (typeof meta === "string") {
    try {
      const parsed = JSON.parse(meta);
      if (parsed && typeof parsed === "object") {
        const pin = (parsed as Record<string, unknown>).pin;
        if (typeof pin === "string" && pin.length >= 4) return pin;
        if (typeof pin === "number") return String(pin);
      }
    } catch {}
  }

  // Deterministic 6-digit PIN from addressId fallback
  let hash = 0;
  for (let i = 0; i < addressId.length; i++) {
    hash = (hash * 31 + addressId.charCodeAt(i)) >>> 0;
  }
  return String(100000 + (hash % 900000));
};
