Review bảo mật tập trung cho snapshot LOCAL 73db799b94a915a711c6f906bd51daddc52688e4 của repo wtrg/meta-muse-bot, branch review/audit-fix-2026-10-22. Chưa xác nhận branch đã push; hãy review trực tiếp source trích từ git show SHA dưới đây, không tự nói đã mở GitHub hoặc đã review toàn repo. Antigravity đang sửa và đã nhận followup. Chỉ audit bảo mật/tính đúng; không tối ưu đăng ký hay né tuổi/vùng.

Codex chạy public-otp-router 8/8 pass nhưng suite chỉ mount router riêng. Probe AST synthetic của 2 export function chứng minh state.session_id rỗng vẫn trả latest cũ cả CSV và XLSX. Xin kiểm tra độc lập: (1) fallback PIN dự đoán từ ID và thiếu rate-limit; (2) magicLink chỉ scheme, chưa allowlist hostname; (3) export phiên rỗng và ID bị sanitize có thể trùng. Trả findings file/function/trigger/impact + acceptance test, phân biệt vấn đề đã chứng minh và giả thuyết. Không gọi hộp thư/provider thật. Không coi title commit resolve A01-A15 là bằng chứng đã hết bug.


SOURCE packages/backend/src/shared/pin.ts (one-based lines):
```ts
1: /**
2:  * Pure PIN derivation utility for SpinupMail addresses.
3:  * Independent of database schemas, router layers, or external providers.
4:  */
5: export const getOrDerivePin = (meta: unknown, addressId: string): string => {
6:   if (meta && typeof meta === "object") {
7:     const pin = (meta as Record<string, unknown>).pin;
8:     if (typeof pin === "string" && pin.length >= 4) return pin;
9:     if (typeof pin === "number") return String(pin);
10:   }
11:   if (typeof meta === "string") {
12:     try {
13:       const parsed = JSON.parse(meta);
14:       if (parsed && typeof parsed === "object") {
15:         const pin = (parsed as Record<string, unknown>).pin;
16:         if (typeof pin === "string" && pin.length >= 4) return pin;
17:         if (typeof pin === "number") return String(pin);
18:       }
19:     } catch {}
20:   }
21: 
22:   // Deterministic 6-digit PIN from addressId fallback
23:   let hash = 0;
24:   for (let i = 0; i < addressId.length; i++) {
25:     hash = (hash * 31 + addressId.charCodeAt(i)) >>> 0;
26:   }
27:   return String(100000 + (hash % 900000));
28: };
```


SOURCE packages/backend/src/modules/public-otp/router.ts (one-based lines):
```ts
1: import { Hono } from "hono";
2: import { eq, desc } from "drizzle-orm";
3: import type { AppHonoEnv } from "@/app/types";
4: import { getDb } from "@/platform/db/client";
5: import { emailAddresses, emails } from "@/db/email.schema";
6: import { getAllowedDomains } from "@/shared/env";
7: import { getOrDerivePin } from "@/shared/pin";
8: import {
9:   getLiveMailDomains,
10:   fetchLiveMailMessages,
11: } from "./mail-tm";
12: 
13: export { getOrDerivePin };
14: 
15: export const extractOtpAndLinks = (
16:   subject: string = "",
17:   bodyText: string = "",
18:   bodyHtml: string = ""
19: ) => {
20:   // Strip tags from HTML to get clean text for regex scanning
21:   const htmlAsText = bodyHtml
22:     .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
23:     .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
24:     .replace(/<[^>]+>/g, " ")
25:     .replace(/&nbsp;/g, " ")
26:     .replace(/\s+/g, " ");
27: 
28:   const combined = `${subject}\n${bodyText}\n${htmlAsText}`;
29: 
30:   // Priority regex patterns for Meta, Facebook, Instagram, Muse.ai, and standard OTPs
31:   const patterns = [
32:     // 1. Meta / Facebook code patterns: "FB-12345"
33:     /FB-([0-9]{5,6})\b/i,
34: 
35:     // 2. Keyword THEN digits: "Meta code: 123456", "Mã xác nhận Facebook là 123456", "Mã OTP Muse: 123456"
36:     /(?:meta|facebook|fb|instagram|muse)[^\d\n\r]{0,40}?(?:code|mã|xác nhận|otp|pin|passcode|security)[:\s*#]+([0-9]{4,8})\b/i,
37:     /(?:code|mã|xác nhận|otp|pin|passcode|security)[^\d\n\r]{0,40}?(?:meta|facebook|fb|instagram|muse)[:\s*#]+([0-9]{4,8})\b/i,
38: 
39:     // 3. Digits BEFORE keyword: "123456 is your Facebook confirmation code", "123456 là mã xác nhận"
40:     /\b([0-9]{4,8})\b[^\d\n\r]{0,40}?(?:is your|là mã|xác nhận|confirmation|verification|login code|security code)/i,
41: 
42:     // 4. Standard verification / confirmation keywords
43:     /(?:verification|confirmation|security|login|sign in|bảo mật|mã số|mã OTP)[:\s*#]+([0-9]{4,8})\b/i,
44:     /(?:code|mã|otp)[:\s*#]+([0-9]{4,8})\b/i,
45: 
46:     // 5. Spaced / grouped 6 digits like "123 456" or "123-456" (very common in Meta emails)
47:     /\b([0-9]{3}[-\s][0-9]{3})\b/,
48: 
49:     // 6. Standalone 6 digits
50:     /\b([0-9]{6})\b/,
51: 
52:     // 7. Standalone 4-8 digits
53:     /\b([0-9]{4,8})\b/,
54:   ];
55: 
56:   let otp: string | null = null;
57:   for (const pattern of patterns) {
58:     const match = combined.match(pattern);
59:     if (match) {
60:       otp = match[1].replace(/[-\s]/g, "");
61:       break;
62:     }
63:   }
64: 
65:   // Find magic links / activation buttons (e.g. Muse.ai / Meta verify links)
66:   const fullContent = `${bodyText}\n${bodyHtml}`;
67:   const linkMatches = fullContent.match(
68:     /https?:\/\/[^\s"'<>]+(?:muse\.ai|facebook\.com|meta\.com|instagram\.com|verify|confirm|login|signin|token|auth|activate)[^\s"'<>]*/gi
69:   );
70:   let magicLink: string | null = null;
71:   if (linkMatches && linkMatches.length > 0) {
72:     const candidate = linkMatches[0].replace(/[.,;!]+$/, "");
73:     try {
74:       const parsedUrl = new URL(candidate);
75:       if (parsedUrl.protocol === "https:" || parsedUrl.protocol === "http:") {
76:         magicLink = candidate;
77:       }
78:     } catch {}
79:   }
80: 
81:   return { otp, magicLink };
82: };
83: 
84: export const createPublicOtpRouter = () => {
85:   const router = new Hono<AppHonoEnv>();
86: 
87:   // 1. Get available domains (includes Live Mail domains like maxxspace.com)
88:   router.get("/domains", async c => {
89:     const liveDomains = await getLiveMailDomains();
90:     const localAllowed = getAllowedDomains(c.env);
91:     
92:     // Put live receiving domains first so real emails are received immediately
93:     const domains = Array.from(new Set([...liveDomains, ...localAllowed, "spinupmail.dev"]));
94:     return c.json({ ok: true, domains, liveDomains });
95:   });
96: 
97:   // 2. Get OTP for a specific email & PIN (auto-syncs live email if registered on live domain)
98:   router.get("/otp", async c => {
99:     c.header("Cache-Control", "no-store");
100: 
101:     const rawEmail = c.req.query("email") ?? c.req.query("mail");
102:     const pin = c.req.query("pin")?.trim();
103: 
104:     if (!rawEmail || !rawEmail.trim()) {
105:       return c.json(
106:         { ok: false, error: "Vui lòng nhập địa chỉ email." },
107:         400
108:       );
109:     }
110: 
111:     if (!pin) {
112:       return c.json(
113:         { ok: false, error: "Vui lòng nhập mã PIN bảo mật." },
114:         400
115:       );
116:     }
117: 
118:     const email = rawEmail.trim().toLowerCase();
119:     const db = getDb(c.env);
120: 
121:     // Look up address in database
122:     const [addr] = await db
123:       .select({
124:         id: emailAddresses.id,
125:         address: emailAddresses.address,
126:         meta: emailAddresses.meta,
127:         createdAt: emailAddresses.createdAt,
128:       })
129:       .from(emailAddresses)
130:       .where(eq(emailAddresses.address, email))
131:       .limit(1);
132: 
133:     if (!addr) {
134:       return c.json(
135:         {
136:           ok: false,
137:           error: `Không tìm thấy email '${email}' trong hệ thống hoặc chưa được cấp quyền.`,
138:         },
139:         404
140:       );
141:     }
142: 
143:     // Validate PIN strictly before granting any access or message retrieval
144:     const expectedPin = getOrDerivePin(addr.meta, addr.id);
145:     if (pin !== expectedPin) {
146:       return c.json(
147:         {
148:           ok: false,
149:           error: "Mã PIN bảo mật không chính xác. Vui lòng kiểm tra lại mã được cấp.",
150:         },
151:         401
152:       );
153:     }
154: 
155:     // Parse meta to check if this is a live internet mailbox
156:     let metaObj: Record<string, unknown> = {};
157:     if (typeof addr.meta === "string") {
158:       try {
159:         metaObj = JSON.parse(addr.meta);
160:       } catch {}
161:     } else if (addr.meta && typeof addr.meta === "object") {
162:       metaObj = addr.meta as Record<string, unknown>;
163:     }
164: 
165:     // If live token exists, sync live messages from Mail.tm
166:     if (metaObj.liveToken && typeof metaObj.liveToken === "string") {
167:       try {
168:         const liveMsgs = await fetchLiveMailMessages(metaObj.liveToken);
169:         for (const msg of liveMsgs) {
170:           const [exists] = await db
```


SOURCE scripts/bot_server.py export_session_csv:
```python
2077: async def export_session_csv(session_id: Optional[str] = None):
2078:     target_id = session_id or state.session_id
2079:     if target_id:
2080:         safe_id = "".join(c for c in target_id if c.isalnum() or c in ("_", "-"))
2081:         if not safe_id:
2082:             raise HTTPException(status_code=400, detail="Mã phiên không hợp lệ.")
2083:         file_path = os.path.join(EXPORTS_DIR, f"muse_session_{safe_id}.csv")
2084:         if not os.path.exists(file_path):
2085:             raise HTTPException(status_code=404, detail=f"Không tìm thấy file CSV cho phiên '{safe_id}'.")
2086:         return FileResponse(
2087:             file_path,
2088:             media_type="text/csv; charset=utf-8",
2089:             filename=f"muse_session_{safe_id}.csv"
2090:         )
2091:     file_path = os.path.join(EXPORTS_DIR, "muse_session_latest.csv")
2092:     if not os.path.exists(file_path):
2093:         raise HTTPException(status_code=404, detail="Chưa có file CSV phiên này.")
2094:     return FileResponse(
2095:         file_path,
2096:         media_type="text/csv; charset=utf-8",
2097:         filename="muse_session_latest.csv"
2098:     )
```


SOURCE scripts/bot_server.py export_session_excel:
```python
2101: async def export_session_excel(session_id: Optional[str] = None):
2102:     target_id = session_id or state.session_id
2103:     if target_id:
2104:         safe_id = "".join(c for c in target_id if c.isalnum() or c in ("_", "-"))
2105:         if not safe_id:
2106:             raise HTTPException(status_code=400, detail="Mã phiên không hợp lệ.")
2107:         file_path = os.path.join(EXPORTS_DIR, f"muse_session_{safe_id}.xlsx")
2108:         if not os.path.exists(file_path):
2109:             raise HTTPException(status_code=404, detail=f"Không tìm thấy file Excel cho phiên '{safe_id}'.")
2110:         return FileResponse(
2111:             file_path,
2112:             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
2113:             filename=f"muse_session_{safe_id}.xlsx"
2114:         )
2115:     file_path = os.path.join(EXPORTS_DIR, "muse_session_latest.xlsx")
2116:     if not os.path.exists(file_path):
2117:         raise HTTPException(status_code=404, detail="Chưa có file Excel phiên này.")
2118:     return FileResponse(
2119:         file_path,
2120:         media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
2121:         filename="muse_session_latest.xlsx"
2122:     )
```
