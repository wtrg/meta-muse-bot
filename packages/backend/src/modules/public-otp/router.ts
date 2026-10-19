import { Hono } from "hono";
import { eq, desc } from "drizzle-orm";
import type { AppHonoEnv } from "@/app/types";
import { getDb } from "@/platform/db/client";
import { emailAddresses, emails } from "@/db/email.schema";
import { users, organizations, members } from "@/db/auth.schema";
import { getAllowedDomains } from "@/shared/env";
import {
  getLiveMailDomains,
  createLiveMailAccount,
  fetchLiveMailMessages,
} from "./mail-tm";

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
  const fullContent = `${bodyText}\n${bodyHtml}`;
  const linkMatches = fullContent.match(
    /https?:\/\/[^\s"'<>]+(?:muse\.ai|facebook\.com|meta\.com|instagram\.com|verify|confirm|login|signin|token|auth|activate)[^\s"'<>]*/gi
  );
  const magicLink =
    linkMatches && linkMatches.length > 0
      ? linkMatches[0].replace(/[.,;!]+$/, "")
      : null;

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
      // Check MTempMail API for clean tempmail accounts created by the Muse bot
      try {
        const mtempApiKey = "pub_nRn1hUwpdmZvxQNVWDfoXgKyF7dIm9nRIIIt1qDw";
        const mtempRes = await fetch(
          `https://mtempmail.com/api/messages/${mtempApiKey}/${encodeURIComponent(email)}`,
          { headers: { "User-Agent": "Mozilla/5.0" } }
        );
        if (mtempRes.ok) {
          const mtempData = (await mtempRes.json()) as any;
          const msgs = mtempData.messages ?? mtempData.data ?? [];
          if (Array.isArray(msgs) && msgs.length > 0) {
            const sorted = [...msgs].sort((a: any, b: any) => {
              const tA = new Date(a.receivedAt || a.created_at || 0).getTime();
              const tB = new Date(b.receivedAt || b.created_at || 0).getTime();
              return tB - tA;
            });
            let chosenMsg = sorted[0];
            let foundOtp: string | null = null;
            let foundLink: string | null = null;
            for (const m of sorted) {
              const c = m.content || m.body || m.snippet || "";
              const res = extractOtpAndLinks(m.subject || "", c, c);
              const subj = (m.subject || "").toLowerCase();
              if (res.otp && (subj.includes("confirm") || subj.includes("code") || subj.includes("meta") || subj.includes("xác nhận") || subj.includes("otp"))) {
                chosenMsg = m;
                foundOtp = res.otp;
                foundLink = res.magicLink;
                break;
              }
            }
            if (!foundOtp) {
              const c = chosenMsg.content || chosenMsg.body || chosenMsg.snippet || "";
              const res = extractOtpAndLinks(chosenMsg.subject || "", c, c);
              foundOtp = res.otp;
              foundLink = res.magicLink;
            }

            const chosenContent = chosenMsg.content || chosenMsg.body || chosenMsg.snippet || "";
            return c.json({
              ok: true,
              hasEmails: true,
              address: email,
              totalEmails: msgs.length,
              latest: {
                id: String(chosenMsg.id || "mtemp_latest"),
                from: chosenMsg.from || chosenMsg.from_email || "Meta",
                sender: chosenMsg.from || "Meta Security",
                subject: chosenMsg.subject || "Xác thực tài khoản",
                receivedAt: chosenMsg.receivedAt || new Date().toISOString(),
                otp: foundOtp,
                magicLink: foundLink,
                bodyText: chosenContent.replace(/<[^>]+>/g, " ").slice(0, 800),
                bodyHtml: chosenContent,
              },
            });
          } else {
            return c.json({
              ok: true,
              hasEmails: false,
              address: email,
              message: "Chưa nhận được email hoặc mã OTP mới. Vui lòng bấm gửi mã trên Muse.ai.",
              totalEmails: 0,
            });
          }
        }
      } catch (err) {
        console.error("MTempMail fallback error:", err);
      }

      return c.json(
        {
          ok: false,
          error: `Không tìm thấy email '${email}' trong hệ thống.`,
        },
        404
      );
    }

    // Validate PIN
    const expectedPin = getOrDerivePin(addr.meta, addr.id);
    if (pin !== expectedPin) {
      return c.json(
        {
          ok: false,
          error: "Mã PIN bảo mật không chính xác. Vui lòng kiểm tra lại mã được cấp.",
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
        console.log("[sync-debug] fetching live messages with token for:", addr.address);
        const liveMsgs = await fetchLiveMailMessages(metaObj.liveToken);
        console.log("[sync-debug] liveMsgs found:", liveMsgs.length);
        for (const msg of liveMsgs) {
          const [exists] = await db
            .select({ id: emails.id })
            .from(emails)
            .where(eq(emails.id, "live_" + msg.id))
            .limit(1);

          if (!exists) {
            console.log("[sync-debug] inserting new email:", msg.subject);
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
        console.error("[sync-debug] sync failed:", err);
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
          ? "Lưu ý: Bạn đang dùng đuôi '@spinupmail.dev' (tên miền thử nghiệm local). Để Muse.ai gửi được email thật từ internet, hãy tạo email với đuôi thật như '@maxxspace.com' tại trang /bulk."
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

  // 3. Scan all inboxes across system for recent OTPs (Live OTP Scanner)
  router.get("/recent-otps", async c => {
    const db = getDb(c.env);

    // Sync up to 15 recent live addresses
    const recentLiveAddresses = await db
      .select({
        id: emailAddresses.id,
        address: emailAddresses.address,
        meta: emailAddresses.meta,
      })
      .from(emailAddresses)
      .orderBy(desc(emailAddresses.createdAt))
      .limit(15);

    await Promise.allSettled(
      recentLiveAddresses.map(async addr => {
        let metaObj: Record<string, unknown> = {};
        if (typeof addr.meta === "string") {
          try {
            metaObj = JSON.parse(addr.meta);
          } catch {}
        } else if (addr.meta && typeof addr.meta === "object") {
          metaObj = addr.meta as Record<string, unknown>;
        }

        if (metaObj.liveToken && typeof metaObj.liveToken === "string") {
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
        }
      })
    );

    // Fetch recent emails across all addresses
    const recentEmails = await db
      .select({
        id: emails.id,
        addressId: emails.addressId,
        from: emails.from,
        subject: emails.subject,
        bodyText: emails.bodyText,
        bodyHtml: emails.bodyHtml,
        receivedAt: emails.receivedAt,
        address: emailAddresses.address,
        meta: emailAddresses.meta,
      })
      .from(emails)
      .leftJoin(emailAddresses, eq(emails.addressId, emailAddresses.id))
      .orderBy(desc(emails.receivedAt))
      .limit(40);

    const items = recentEmails.map(row => {
      const { otp, magicLink } = extractOtpAndLinks(
        row.subject ?? "",
        row.bodyText ?? "",
        row.bodyHtml ?? ""
      );
      const pin = row.addressId ? getOrDerivePin(row.meta, row.addressId) : "";
      return {
        id: row.id,
        address: row.address ?? "unknown",
        pin,
        from: row.from,
        subject: row.subject,
        otp,
        magicLink,
        receivedAt: row.receivedAt ? row.receivedAt.toISOString() : null,
      };
    });

    return c.json({
      ok: true,
      count: items.length,
      items,
    });
  });

  // 4. Bulk Create Email Addresses (Auto-creates real live public mailbox if live domain)
  router.post("/bulk-create", async c => {
    const db = getDb(c.env);
    const body = await c.req.json().catch(() => ({}));

    const prefix = (body.prefix || "muse")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]/g, "");
    const count = Math.min(Math.max(Number(body.count) || 10, 1), 50);

    const liveDomains = await getLiveMailDomains();
    const allowedDomains = getAllowedDomains(c.env);
    const allAvailable = Array.from(new Set([...liveDomains, ...allowedDomains, "spinupmail.dev"]));

    const domain = body.domain && allAvailable.includes(body.domain)
      ? body.domain
      : allAvailable[0] || "maxxspace.com";

    const isLiveDomain = liveDomains.includes(domain);

    // Ensure default user and org exist
    const defaultEmail = "tranvantruong12123@gmail.com";
    let [targetUser] = await db
      .select()
      .from(users)
      .where(eq(users.email, defaultEmail))
      .limit(1);

    if (!targetUser) {
      const uid = "usr_truong";
      await db.insert(users).values({
        id: uid,
        name: "TRAN TRUONG",
        email: defaultEmail,
        emailVerified: true,
        role: "admin",
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      [targetUser] = await db
        .select()
        .from(users)
        .where(eq(users.email, defaultEmail))
        .limit(1);
    }

    let [targetOrg] = await db
      .select()
      .from(organizations)
      .where(eq(organizations.slug, "muse-team"))
      .limit(1);

    if (!targetOrg) {
      const oid = "org_muse_team";
      await db.insert(organizations).values({
        id: oid,
        name: "Muse Team",
        slug: "muse-team",
        createdAt: new Date(),
      });
      [targetOrg] = await db
        .select()
        .from(organizations)
        .where(eq(organizations.slug, "muse-team"))
        .limit(1);
    }

    const createdItems: Array<{
      address: string;
      pin: string;
      otpUrl: string;
      formatted: string;
      isLive: boolean;
    }> = [];

    const now = Date.now();
    for (let i = 1; i <= count; i++) {
      const randSuffix = Math.random().toString(36).substring(2, 6);
      const localPart = `${prefix}_${i < 10 ? "0" + i : i}_${randSuffix}`;
      const address = `${localPart}@${domain}`;
      const pin = Math.floor(100000 + Math.random() * 900000).toString();
      const id = crypto.randomUUID();

      let liveToken: string | undefined = undefined;
      let livePassword: string | undefined = undefined;

      if (isLiveDomain) {
        livePassword = `Pass_${randSuffix}_${pin}!`;
        const token = await createLiveMailAccount(address, livePassword);
        if (token) {
          liveToken = token;
        }
        if (i < count) {
          await new Promise(r => setTimeout(r, 1200));
        }
      }

      const meta = JSON.stringify({
        pin,
        liveToken,
        livePassword,
        isLiveMail: Boolean(liveToken),
      });

      await db.insert(emailAddresses).values({
        id,
        organizationId: targetOrg.id,
        userId: targetUser.id,
        address,
        localPart,
        domain,
        meta,
        createdAt: new Date(now + i),
      });

      const otpUrl = `http://127.0.0.1:5173/otp?mail=${encodeURIComponent(address)}&pin=${encodeURIComponent(pin)}`;
      const formatted = `${address} | PIN: ${pin} | ${otpUrl}`;

      createdItems.push({
        address,
        pin,
        otpUrl,
        formatted,
        isLive: Boolean(liveToken),
      });
    }

    const allFormatted = createdItems.map(item => item.formatted).join("\n");

    return c.json({
      ok: true,
      count: createdItems.length,
      items: createdItems,
      allFormatted,
      isLiveDomain,
      domain,
    });
  });

  // 5. Instant 1-Click Auto Login for Development -> Direct to /bulk
  router.get("/auto-login", async c => {
    const auth = c.get("auth");
    const email = "tranvantruong12123@gmail.com";
    const password = "Password123!";

    try {
      const signInRes = await auth.api.signInEmail({
        body: {
          email,
          password,
        },
        asResponse: true,
      });

      const setCookies = signInRes.headers.getSetCookie
        ? signInRes.headers.getSetCookie()
        : [signInRes.headers.get("set-cookie")].filter(Boolean) as string[];

      for (const cookie of setCookies) {
        c.header("Set-Cookie", cookie, { append: true });
      }

      return c.redirect("http://127.0.0.1:5173/bulk", 302);
    } catch {
      // Fallback redirect to /bulk
      return c.redirect("http://127.0.0.1:5173/bulk", 302);
    }
  });

  return router;
};
