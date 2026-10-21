Review bảo mật/tính đúng tiếp theo cho SHA 44521e7b2e6de028d9104b819814d467e04e6c97, đã xác nhận origin review/audit-fix-2026-10-22 cùng SHA. URL: https://github.com/wtrg/meta-muse-bot/commit/44521e7b2e6de028d9104b819814d467e04e6c97. Không coi packet agent là bằng chứng tự chạy test. Codex đã tự chạy 43/43 test OTP+mailbox service, Python 71/71 và 4/4 probe resolved. R03 export reserved alias/DO outage/Math.random/dead callers đã có code và tests phù hợp. Chưa chứng nhận full repo/E2E.

Xin review tập trung contract hộp thư có auth: createEmailAddress mới hỗ trợ meta.generatePin=true/meta.pin=auto nhưng response tạo mới dùng DTO xóa pin, chủ hộp thư không nhận được PIN tự sinh. Probe fixture bổ sung assert JSON.stringify(result.body).includes(savedMeta.pin) FAILED false vs true; file probe tạm đã xóa, không dùng secret thật. Top-level generatePin không có trong Zod schema dù service kiểm field đó. POST response hiện cache private,max-age=15; nếu trả secret một lần thì phải no-store. Chỉ trả findings thực có evidence và acceptance tests; không mở endpoint xem lại toàn bộ PIN, không bỏ check PIN, không cải thiện tự tạo tài khoản/vượt tuổi/vùng. Đây là review source trích dưới đây, không giả vờ đã chạy tests.


SOURCE packages/backend/src/shared/pin.ts
```ts
1: /**
2:  * Pure PIN validation and secure generation utilities for SpinupMail addresses.
3:  * Independent of database schemas, router layers, or external providers.
4:  */
5: 
6: /**
7:  * Retrieves the configured PIN from mailbox metadata.
8:  * Fails closed (returns undefined) if no valid PIN string is explicitly present.
9:  * Does NOT generate pseudo-secrets from address IDs, nor accept numeric types.
10:  */
11: export const getMailboxPin = (meta: unknown): string | undefined => {
12:   if (meta && typeof meta === "object") {
13:     const pin = (meta as Record<string, unknown>).pin;
14:     if (typeof pin === "string" && pin.trim().length >= 4) {
15:       return pin.trim();
16:     }
17:   }
18:   if (typeof meta === "string") {
19:     try {
20:       const parsed = JSON.parse(meta);
21:       if (parsed && typeof parsed === "object") {
22:         const pin = (parsed as Record<string, unknown>).pin;
23:         if (typeof pin === "string" && pin.trim().length >= 4) {
24:           return pin.trim();
25:         }
26:       }
27:     } catch {}
28:   }
29:   return undefined;
30: };
31: 
32: /**
33:  * Backward compatibility helper that preserves the function name
34:  * but enforces fail-closed semantics (returns undefined when no PIN is configured).
35:  */
36: export const getOrDerivePin = (
37:   meta: unknown,
38:   _addressId?: string
39: ): string | undefined => {
40:   return getMailboxPin(meta);
41: };
42: 
43: /**
44:  * Generates a cryptographically secure 6-digit PIN using CSPRNG.
45:  * Fails closed by throwing if CSPRNG is unavailable (no insecure pseudo-random fallback).
46:  */
47: export const generateSecurePin = (): string => {
48:   if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
49:     const buf = new Uint32Array(1);
50:     crypto.getRandomValues(buf);
51:     return String(100000 + (buf[0] % 900000));
52:   }
53:   throw new Error(
54:     "CSPRNG_UNAVAILABLE: Cryptographically secure random number generator is required to generate PIN."
55:   );
56: };
```

SOURCE packages/backend/src/modules/email-addresses/dto.ts
```ts
1: import {
2:   getAllowedFromDomainsFromMeta,
3:   getBlockedSenderDomainsFromMeta,
4:   getInboundRatePolicyFromMeta,
5:   getMaxReceivedEmailActionFromMeta,
6:   getMaxReceivedEmailCountFromMeta,
7:   parseAddressMeta,
8: } from "@/shared/validation";
9: import type { AddressIntegration } from "@spinupmail/contracts";
10: 
11: export const toEmailAddressListItem = (row: {
12:   id: string;
13:   address: string;
14:   localPart: string;
15:   domain: string;
16:   meta: string | null;
17:   integrations?: AddressIntegration[];
18:   emailCount: number;
19:   createdAt: Date;
20:   expiresAt: Date | null;
21:   lastReceivedAt: Date | null;
22: }) => {
23:   const parsedMeta = parseAddressMeta(row.meta);
24:   const safeMeta =
25:     parsedMeta && typeof parsedMeta === "object"
26:       ? Object.fromEntries(
27:           Object.entries(parsedMeta).filter(
28:             ([key]) =>
29:               !["pin", "liveToken", "livePassword", "password"].includes(key)
30:           )
31:         )
32:       : parsedMeta;
33:   const allowedFromDomains = getAllowedFromDomainsFromMeta(parsedMeta);
34:   const blockedSenderDomains = getBlockedSenderDomainsFromMeta(parsedMeta);
35:   const inboundRatePolicy = getInboundRatePolicyFromMeta(parsedMeta);
36:   const maxReceivedEmailCount = getMaxReceivedEmailCountFromMeta(parsedMeta);
37:   const maxReceivedEmailAction =
38:     maxReceivedEmailCount === null
39:       ? null
40:       : getMaxReceivedEmailActionFromMeta(parsedMeta);
41: 
42:   return {
43:     id: row.id,
44:     address: row.address,
45:     localPart: row.localPart,
46:     domain: row.domain,
47:     meta: safeMeta,
48:     emailCount: row.emailCount,
49:     allowedFromDomains,
50:     blockedSenderDomains,
51:     inboundRatePolicy,
52:     maxReceivedEmailCount,
53:     maxReceivedEmailAction,
54:     integrations: row.integrations ?? [],
55:     createdAt: row.createdAt ? row.createdAt.toISOString() : null,
56:     createdAtMs: row.createdAt ? row.createdAt.getTime() : null,
57:     expiresAt: row.expiresAt ? row.expiresAt.toISOString() : null,
58:     expiresAtMs: row.expiresAt ? row.expiresAt.getTime() : null,
59:     lastReceivedAt: row.lastReceivedAt
60:       ? row.lastReceivedAt.toISOString()
61:       : null,
62:     lastReceivedAtMs: row.lastReceivedAt ? row.lastReceivedAt.getTime() : null,
63:   };
64: };
```

SOURCE packages/backend/src/modules/email-addresses/schemas.ts
```ts
90: export const createEmailAddressBodySchema = z
91:   .object({
92:     localPart: z
93:       .string()
94:       .trim()
95:       .min(1)
96:       .max(ADDRESS_LOCAL_PART_MAX_LENGTH)
97:       .regex(ADDRESS_LOCAL_PART_REGEX),
98:     ttlMinutes: z
99:       .number()
100:       .int()
101:       .positive()
102:       .max(ADDRESS_TTL_MAX_MINUTES)
103:       .optional(),
104:     meta: z.unknown().optional(),
105:     domain: z.string().optional(),
106:     allowedFromDomains: z
107:       .union([allowedFromDomainsSchema, z.string()])
108:       .optional(),
109:     blockedSenderDomains: z
110:       .union([blockedSenderDomainsSchema, z.string()])
111:       .optional(),
112:     inboundRatePolicy: inboundRatePolicySchema.optional(),
113:     maxReceivedEmailCount: z
114:       .number()
115:       .int()
116:       .positive()
117:       .max(ADDRESS_MAX_RECEIVED_EMAIL_COUNT_MAX)
118:       .optional(),
119:     maxReceivedEmailAction: z
120:       .enum(ADDRESS_MAX_RECEIVED_EMAIL_ACTIONS)
121:       .optional(),
122:     integrationSubscriptions: integrationSubscriptionsSchema.optional(),
123:     acceptedRiskNotice: z.boolean().refine(value => value, {
124:       message: "acceptedRiskNotice must be true",
125:     }),
126:   })
127:   .passthrough();
128: 
129: export const listEmailAddressesQuerySchema = z
```

SOURCE packages/backend/src/modules/email-addresses/service.ts
```ts
570:     });
571:   if (!integrationSubscriptionsValidation.ok) {
572:     return integrationSubscriptionsValidation.response;
573:   }
574: 
575:   let rawMetaObj: Record<string, unknown> = {};
576:   if (body.meta && typeof body.meta === "object") {
577:     rawMetaObj = { ...(body.meta as Record<string, unknown>) };
578:   } else if (typeof body.meta === "string") {
579:     try {
580:       const p = JSON.parse(body.meta);
581:       if (p && typeof p === "object") rawMetaObj = { ...p };
582:     } catch {}
583:   }
584: 
585:   // Secure PIN provisioning & validation (Blocker 3 / P2)
586:   if (
587:     (body as Record<string, unknown>).generatePin === true ||
588:     rawMetaObj.generatePin === true ||
589:     rawMetaObj.pin === "auto"
590:   ) {
591:     rawMetaObj.pin = generateSecurePin();
592:     delete rawMetaObj.generatePin;
593:   }
594: 
595:   if (rawMetaObj.pin !== undefined) {
596:     if (typeof rawMetaObj.pin !== "string" || rawMetaObj.pin.trim().length < 4) {
597:       return {
598:         status: 400 as const,
599:         body: {
600:           error: "PIN must be a string with at least 4 characters",
601:         },
602:       };
603:     }
604:     rawMetaObj.pin = rawMetaObj.pin.trim();
605:   }
606: 
607:   const baseMeta = buildAddressMetaForStorage(rawMetaObj, {
608:     allowedFromDomains,
609:     blockedSenderDomains,
610:     inboundRatePolicy: inboundRatePolicyResult.policy,
611:   });
612:   if (baseMeta === null) {
613:     return {
614:       status: 400 as const,
615:       body: {
616:         error:
617:           "address policy controls require meta to be an object (or JSON object string)",
740:           ? null
741:           : JSON.stringify(responseMeta ?? null),
742:       integrations: integrationsByAddressId.get(id) ?? [],
743:       emailCount: 0,
744:       createdAt: new Date(now),
745:       expiresAt: expiresAt ?? null,
746:       lastReceivedAt: null,
747:     }),
748:   };
749: };
750: 
751: export const deleteEmailAddress = async ({
752:   env,
753:   organizationId,
754:   addressId,
755: }: {
756:   env: CloudflareBindings;
757:   organizationId: string;
758:   addressId: string;
759: }) => {
760:   const db = getDb(env);
761:   const addressRow = await findAddressByIdAndOrganization(
762:     db,
763:     addressId,
764:     organizationId
765:   );
766: 
767:   if (!addressRow) {
768:     return {
769:       status: 404 as const,
770:       body: { error: "address not found" },
771:     };
772:   }
773: 
774:   if (env.R2_BUCKET) {
775:     try {
776:       await Promise.all([
777:         deleteR2ObjectsByPrefix({
```

SOURCE packages/backend/src/modules/email-addresses/router.ts
```ts
55:   router.post(
56:     "/email-addresses",
57:     zValidator("json", createEmailAddressBodySchema, (result, c) => {
58:       if (!result.success) {
59:         return c.json({ error: "invalid request body" }, 400);
60:       }
61:       return undefined;
62:     }),
63:     async c => {
64:       const session = c.get("session");
65:       const organizationId = c.get("organizationId");
66:       const payload = c.req.valid("json");
67: 
68:       const result = await createEmailAddress({
69:         env: c.env,
70:         session,
71:         organizationId,
72:         payload,
73:       });
74: 
75:       return c.json(result.body, result.status, {
76:         "Cache-Control": "private, max-age=15",
77:       });
78:     }
79:   );
80: 
81:   router.get("/email-addresses/:id", async c => {
82:     const organizationId = c.get("organizationId");
83:     const addressId = c.req.param("id");
84: 
85:     const result = await getEmailAddress({
```