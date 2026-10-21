import { Hono } from "hono";
import { eq, desc } from "drizzle-orm";
import type { AppHonoEnv } from "@/app/types";
import { getDb } from "@/platform/db/client";
import { emailAddresses, emails } from "@/db/email.schema";
import { getAllowedDomains } from "@/shared/env";
import { getMailboxPin, getOrDerivePin } from "@/shared/pin";
import { consumeFixedWindowRateLimit } from "@/shared/rate-limiter";
import {
  getLiveMailDomains,
  fetchLiveMailMessages,
} from "./mail-tm";

export { getMailboxPin, getOrDerivePin };

export const ALLOWED_MAGIC_LINK_DOMAINS = [
  "muse.ai",
  "facebook.com",
  "meta.com",
  "instagram.com",
];

export const isAllowedMagicLinkHostname = (hostname: string): boolean => {
  const host = hostname.toLowerCase().trim();
  return ALLOWED_MAGIC_LINK_DOMAINS.some(
    allowed => host === allowed || host.endsWith("." + allowed)
  );
};

export const MAX_MEMORY_RATE_LIMIT_ENTRIES = 10000;
const memoryRateLimits = new Map<string, { count: number; resetAtMs: number }>();

export const _resetOtpRateLimitsForTesting = () => {
  memoryRateLimits.clear();
};

export const _getMemoryRateLimitsSizeForTesting = () => {
  return memoryRateLimits.size;
};

export const cleanupMemoryRateLimits = (now: number = Date.now()) => {
  for (const [key, entry] of memoryRateLimits.entries()) {
    if (entry.resetAtMs <= now) {
      memoryRateLimits.delete(key);
    }
  }
  if (memoryRateLimits.size >= MAX_MEMORY_RATE_LIMIT_ENTRIES) {
    const excess = memoryRateLimits.size - MAX_MEMORY_RATE_LIMIT_ENTRIES + 100;
    let deleted = 0;
    for (const key of memoryRateLimits.keys()) {
      memoryRateLimits.delete(key);
      deleted++;
      if (deleted >= excess) break;
    }
  }
};

export const checkOtpRateLimit = async (
  env: AppHonoEnv["Bindings"],
  clientKey: string,
  maxAttempts: number = 10,
  windowSeconds: number = 60
): Promise<{ allowed: boolean; retryAfterSeconds?: number }> => {
  if (env?.FIXED_WINDOW_RATE_LIMITERS) {
    try {
      const res = await consumeFixedWindowRateLimit({
        namespace: env.FIXED_WINDOW_RATE_LIMITERS,
        key: `otp:${clientKey}`,
        windowSeconds,
        maxAttempts,
      });
      return res;
    } catch {
      // Fail-closed on Durable Object store outage / failure in distributed environment
      return { allowed: false, retryAfterSeconds: 60 };
    }
  }

  const now = Date.now();
  cleanupMemoryRateLimits(now);

  const entry = memoryRateLimits.get(clientKey);
  if (!entry || entry.resetAtMs <= now) {
    memoryRateLimits.set(clientKey, {
      count: 1,
      resetAtMs: now + windowSeconds * 1000,
    });
    return { allowed: true };
  }

  if (entry.count >= maxAttempts) {
    const retryAfter = Math.max(1, Math.ceil((entry.resetAtMs - now) / 1000));
    return { allowed: false, retryAfterSeconds: retryAfter };
  }

  entry.count++;
  return { allowed: true };
};

export const extractOtpAndLinks = (
  subject: string = "",
  bodyText: string = "",
  bodyHtml: string = ""
) => {
  // Strip tags from HTML to get clean text for regex scanning
  const htmlAsText = bodyHtml
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ");

  const combined = `${subject}\n${bodyText}\n${htmlAsText}`;

  // Priority regex patterns for Meta, Facebook, Instagram, Muse.ai, and standard OTPs
  const patterns = [
    // 1. Meta / Facebook code patterns: "FB-12345"
    /FB-([0-9]{5,6})\b/i,

    // 2. Keyword THEN digits: "Meta code: 123456", "Mã xác nhận Facebook là 123456", "Mã OTP Muse: 123456"
    /(?:meta|facebook|fb|instagram|muse)[^\d\n\r]{0,40}?(?:code|mã|xác nhận|otp|pin|passcode|security)[:\s*#]+([0-9]{4,8})\b/i,
    /(?:code|mã|xác nhận|otp|pin|passcode|security)[^\d\n\r]{0,40}?(?:meta|facebook|fb|instagram|muse)[:\s*#]+([0-9]{4,8})\b/i,

    // 3. Digits BEFORE keyword: "123456 is your Facebook confirmation code", "123456 là mã xác nhận"
    /\b([0-9]{4,8})\b[^\d\n\r]{0,40}?(?:is your|là mã|xác nhận|confirmation|verification|login code|security code)/i,

    // 4. Standard verification / confirmation keywords
    /(?:verification|confirmation|security|login|sign in|bảo mật|mã số|mã OTP)[:\s*#]+([0-9]{4,8})\b/i,
    /(?:code|mã|otp)[:\s*#]+([0-9]{4,8})\b/i,

    // 5. Spaced / grouped 6 digits like "123 456" or "123-456" (very common in Meta emails)
    /\b([0-9]{3}[-\s][0-9]{3})\b/,

    // 6. Standalone 6 digits
    /\b([0-9]{6})\b/,

    // 7. Standalone 4-8 digits
    /\b([0-9]{4,8})\b/,
  ];

  let otp: string | null = null;
  for (const pattern of patterns) {
    const match = combined.match(pattern);
    if (match) {
      otp = match[1].replace(/[-\s]/g, "");
      break;
    }
  }

  // Find magic links / activation buttons (e.g. Muse.ai / Meta verify links)
  // Only accept links from verified official domains (strict hostname allowlist)
  const fullContent = `${bodyText}\n${bodyHtml}`;
  const urlRegex = /https?:\/\/[^\s"'<>]+/gi;
  const linkMatches = fullContent.match(urlRegex);
  let magicLink: string | null = null;
  if (linkMatches) {
    for (const rawUrl of linkMatches) {
      const candidate = rawUrl.replace(/[.,;!]+$/, "");
      try {
        const parsedUrl = new URL(candidate);
        if (parsedUrl.protocol === "https:" || parsedUrl.protocol === "http:") {
          if (isAllowedMagicLinkHostname(parsedUrl.hostname)) {
            magicLink = candidate;
            break;
          }
        }
      } catch {}
    }
  }

  return { otp, magicLink };
};

export const createPublicOtpRouter = () => {
  const router = new Hono<AppHonoEnv>();

  // 1. Get available domains (includes Live Mail domains like maxxspace.com)
  router.get("/domains", async c => {
    const liveDomains = await getLiveMailDomains();
    const localAllowed = getAllowedDomains(c.env);
    
    // Put live receiving domains first so real emails are received immediately
    const domains = Array.from(new Set([...liveDomains, ...localAllowed, "spinupmail.dev"]));
    return c.json({ ok: true, domains, liveDomains });
  });

  // 2. Get OTP for a specific email & PIN (auto-syncs live email if registered on live domain)
  router.get("/otp", async c => {
    c.header("Cache-Control", "no-store");

    const rawEmail = c.req.query("email") ?? c.req.query("mail");
    const pin = c.req.query("pin")?.trim();

    if (!rawEmail || !rawEmail.trim()) {
      return c.json(
        { ok: false, error: "Vui lòng nhập địa chỉ email." },
        400
      );
    }

    if (!pin) {
      return c.json(
        { ok: false, error: "Vui lòng nhập mã PIN bảo mật." },
        400
      );
    }

    const email = rawEmail.trim().toLowerCase();

    // Rate limiting: Dual-budget protection
    // 1. Mailbox budget (10 req/min): protects target mailbox from distributed brute force
    // 2. Client IP budget (30 req/min): protects against wide credential-stuffing/address enumeration
    const clientIp =
      c.req.header("cf-connecting-ip") ||
      c.req.header("x-forwarded-for") ||
      "127.0.0.1";

    const mailboxLimit = await checkOtpRateLimit(c.env, `mail:${email}`, 10, 60);
    if (!mailboxLimit.allowed) {
      c.header("Retry-After", String(mailboxLimit.retryAfterSeconds ?? 60));
      return c.json(
        {
          ok: false,
          error: "Hộp thư đã vượt quá giới hạn thử OTP. Vui lòng thử lại sau.",
        },
        429
      );
    }

    const ipLimit = await checkOtpRateLimit(c.env, `ip:${clientIp}`, 30, 60);
    if (!ipLimit.allowed) {
      c.header("Retry-After", String(ipLimit.retryAfterSeconds ?? 60));
      return c.json(
        {
          ok: false,
          error: "Địa chỉ mạng đã vượt quá giới hạn thử OTP. Vui lòng thử lại sau.",
        },
        429
      );
    }

    const db = getDb(c.env);

    // Look up address in database
    const [addr] = await db
      .select({
        id: emailAddresses.id,
        address: emailAddresses.address,
        meta: emailAddresses.meta,
        createdAt: emailAddresses.createdAt,
      })
      .from(emailAddresses)
      .where(eq(emailAddresses.address, email))
      .limit(1);

    if (!addr) {
      return c.json(
        {
          ok: false,
          error: `Không tìm thấy email '${email}' trong hệ thống hoặc chưa được cấp quyền.`,
        },
        404
      );
    }

    // Validate PIN strictly: Fail-closed if no PIN configured on mailbox or PIN does not match
    const expectedPin = getMailboxPin(addr.meta);
    if (!expectedPin || pin !== expectedPin) {
      return c.json(
        {
          ok: false,
          error: "Mã PIN bảo mật không chính xác hoặc hộp thư chưa được thiết lập mã PIN.",
        },
        401
      );
    }

    // Parse meta to check if this is a live internet mailbox
    let metaObj: Record<string, unknown> = {};
    if (typeof addr.meta === "string") {
      try {
        metaObj = JSON.parse(addr.meta);
      } catch {}
    } else if (addr.meta && typeof addr.meta === "object") {
      metaObj = addr.meta as Record<string, unknown>;
    }

    // If live token exists, sync live messages from Mail.tm
    if (metaObj.liveToken && typeof metaObj.liveToken === "string") {
      try {
        const liveMsgs = await fetchLiveMailMessages(metaObj.liveToken);
        for (const msg of liveMsgs) {
          const [exists] = await db
            .select({ id: emails.id })
            .from(emails)
            .where(eq(emails.id, "live_" + msg.id))
            .limit(1);

          if (!exists) {
            await db.insert(emails).values({
              id: "live_" + msg.id,
              addressId: addr.id,
              sender: msg.from,
              from: msg.from,
              to: addr.address,
              subject: msg.subject,
              bodyText: msg.text,
              bodyHtml: msg.html,
              receivedAt: msg.receivedAt,
            });
          }
        }
      } catch (err) {
        console.error("Live Mail sync error:", err);
      }
    }

    // Find all recent emails for this address
    const recentEmails = await db
      .select({
        id: emails.id,
        sender: emails.sender,
        from: emails.from,
        subject: emails.subject,
        bodyText: emails.bodyText,
        bodyHtml: emails.bodyHtml,
        receivedAt: emails.receivedAt,
      })
      .from(emails)
      .where(eq(emails.addressId, addr.id))
      .orderBy(desc(emails.receivedAt))
      .limit(15);

    if (!recentEmails || recentEmails.length === 0) {
      const isLocalDevDomain = addr.address.endsWith("@spinupmail.dev");
      return c.json({
        ok: true,
        hasEmails: false,
        address: addr.address,
        isLocalDevDomain,
        message: isLocalDevDomain
          ? "Lưu ý: Bạn đang dùng đuôi '@spinupmail.dev' (tên miền thử nghiệm local)."
          : "Hòm thư hiện chưa có email nào. Hãy bấm 'Resend code' trên Muse.ai rồi bấm 'Làm mới' sau 2-3 giây.",
      });
    }

    const allOtps = recentEmails.map(item => {
      const { otp, magicLink } = extractOtpAndLinks(
        item.subject ?? "",
        item.bodyText ?? "",
        item.bodyHtml ?? ""
      );
      return {
        id: item.id,
        from: item.from,
        subject: item.subject,
        receivedAt: item.receivedAt ? item.receivedAt.toISOString() : null,
        otp,
        magicLink,
        bodyText: item.bodyText,
        bodyHtml: item.bodyHtml,
      };
    });

    const latest = allOtps[0];

    return c.json({
      ok: true,
      hasEmails: true,
      address: addr.address,
      latest,
      allOtps,
      totalEmails: recentEmails.length,
    });
  });

  return router;
};
