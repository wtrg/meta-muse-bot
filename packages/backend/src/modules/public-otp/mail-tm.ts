const MAIL_TM_BASE = "https://api.mail.tm";

export async function getLiveMailDomains(): Promise<string[]> {
  try {
    const res = await fetch(`${MAIL_TM_BASE}/domains`, {
      headers: {
        Accept: "application/json",
        "User-Agent": "SpinupMail/1.0",
      },
    });
    if (!res.ok) return ["maxxspace.com"];
    const data = (await res.json()) as {
      "hydra:member"?: Array<{ domain: string; isActive: boolean }>;
    };
    const fetched =
      data["hydra:member"]
        ?.filter(d => d.isActive)
        .map(d => d.domain) ?? [];
    return fetched.length > 0 ? fetched : ["maxxspace.com"];
  } catch (err) {
    console.error("[mail-tm] getLiveMailDomains error:", err);
    return ["maxxspace.com"];
  }
}

export async function createLiveMailAccount(
  address: string,
  password: string,
  retries = 2
): Promise<string | null> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // 1. Create account
      const accRes = await fetch(`${MAIL_TM_BASE}/accounts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "User-Agent": "SpinupMail/1.0",
        },
        body: JSON.stringify({ address, password }),
      });

      if (accRes.status === 429 && attempt < retries) {
        await new Promise(r => setTimeout(r, 1600));
        continue;
      }

      if (!accRes.ok && accRes.status !== 409) {
        console.warn("[mail-tm] create account failed:", accRes.status);
        return null;
      }

      // Small pause before obtaining token
      await new Promise(r => setTimeout(r, 400));

      // 2. Obtain token
      const tokenRes = await fetch(`${MAIL_TM_BASE}/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "User-Agent": "SpinupMail/1.0",
        },
        body: JSON.stringify({ address, password }),
      });

      if (!tokenRes.ok) {
        console.warn("[mail-tm] get token failed:", tokenRes.status);
        return null;
      }
      const tokenData = (await tokenRes.json()) as { token?: string };
      return tokenData.token ?? null;
    } catch (err) {
      if (attempt < retries) {
        await new Promise(r => setTimeout(r, 1000));
      } else {
        console.error("[mail-tm] createLiveMailAccount error:", err);
      }
    }
  }
  return null;
}

export async function fetchLiveMailMessages(token: string): Promise<
  Array<{
    id: string;
    from: string;
    subject: string;
    text: string;
    html: string;
    receivedAt: Date;
  }>
> {
  try {
    const listRes = await fetch(`${MAIL_TM_BASE}/messages`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
        "User-Agent": "SpinupMail/1.0",
      },
    });

    console.log("[mail-tm] listRes status:", listRes.status);
    const rawText = await listRes.text();
    console.log("[mail-tm] raw response:", rawText.substring(0, 300));
    let listData: any = {};
    try {
      listData = JSON.parse(rawText);
    } catch {}

    const members: any[] = Array.isArray(listData)
      ? listData
      : (listData["hydra:member"] ?? []);
    console.log("[mail-tm] parsed members count:", members.length);
    if (members.length === 0) return [];

    const results = [];
    for (const msg of members.slice(0, 5)) {
      try {
        const detailRes = await fetch(`${MAIL_TM_BASE}/messages/${msg.id}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/json",
            "User-Agent": "SpinupMail/1.0",
          },
        });

        if (detailRes.ok) {
          const detail = (await detailRes.json()) as {
            id: string;
            from?: { address?: string; name?: string };
            subject?: string;
            text?: string;
            html?: string | string[];
            createdAt?: string;
          };
          const htmlContent = Array.isArray(detail.html)
            ? detail.html.join("")
            : detail.html ?? "";
          const fromStr = detail.from?.name
            ? `${detail.from.name} <${detail.from.address}>`
            : detail.from?.address ?? "unknown";

          results.push({
            id: detail.id,
            from: fromStr,
            subject: detail.subject ?? "(No Subject)",
            text: detail.text ?? "",
            html: htmlContent,
            receivedAt: detail.createdAt
              ? new Date(detail.createdAt)
              : new Date(),
          });
        }
      } catch {
        // Individual message fetch failure fallback
      }
    }
    return results;
  } catch (err) {
    console.error("[mail-tm] fetchLiveMailMessages error:", err);
    return [];
  }
}
