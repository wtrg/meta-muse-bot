const FALLBACK_SITE_URL = "https://spinupmail.com";

const normalizeUrl = (value: string | undefined) => {
  const trimmed = value?.trim();
  if (!trimmed) return FALLBACK_SITE_URL;
  return trimmed.replace(/\/+$/, "");
};

const siteUrl = normalizeUrl(import.meta.env.VITE_SITE_URL);

export const siteConfig = {
  siteName: "SpinupMail",
  alternateSiteName: "Spinupmail",
  locale: "en_US",
  siteUrl,
  homeUrl: `${siteUrl}/`,
  title: "Self-host disposable emails on Cloudflare | SpinupMail",
  description:
    "Self-hosted disposable email infrastructure for teams on Cloudflare with temporary inboxes, API access, TTL controls, sender policies, and attachment support.",
  ogImageUrl: `${siteUrl}/og-image.jpg`,
  ogImageAlt:
    "SpinupMail homepage preview showing self-hosted disposable email infrastructure on Cloudflare.",
  logoUrl: `${siteUrl}/logo-512.png`,
} as const;
