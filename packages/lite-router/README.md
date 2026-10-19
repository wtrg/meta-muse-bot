# @spinupmail/lite-router

Minimal Cloudflare Email Routing worker for forwarding inbound mail to a signed
JSON webhook. It is intentionally separate from the full SpinupMail backend and
does not require D1, KV, R2, Queues, Durable Objects, Better Auth, Hono, or a
dashboard.

## Install

```sh
pnpm add @spinupmail/lite-router
```

## Worker

```ts
export { default } from "@spinupmail/lite-router";
```

Copy `wrangler.toml.example` into your Worker project and configure the email
routing rule to send inbound mail to this Worker.

Required settings:

- `LITE_WEBHOOK_URL`: webhook receiver URL.
- `LITE_WEBHOOK_SECRET`: secret used to sign each request.

Optional settings:

- `LITE_WEBHOOK_BEARER_TOKEN`: adds `Authorization: Bearer <token>`.
- `LITE_ALLOWED_RECIPIENTS`: comma-separated recipient allowlist.
- `LITE_MAX_BYTES`: max raw MIME bytes, default `524288`.
- `LITE_BODY_MAX_BYTES`: max text/html body bytes in the JSON payload, default
  `65536`.
- `LITE_INCLUDE_RAW`: include raw MIME content, default `false`.
- `LITE_DELIVERY_TIMEOUT_MS`: webhook timeout, default `8000`.
- `LITE_REJECT_ON_FAILURE`: reject SMTP delivery on routing failure, default
  `true`.

## Generate Secrets

Do not commit `LITE_WEBHOOK_SECRET` or `LITE_WEBHOOK_BEARER_TOKEN` into
`wrangler.toml`, `.env`, source code, or docs. Store them as Wrangler secrets.

Generate a strong HMAC secret:

```sh
openssl rand -base64 32
```

Store it in the Worker:

```sh
pnpm exec wrangler secret put LITE_WEBHOOK_SECRET
```

Use the same value in your webhook receiver environment, for example as
`LITE_WEBHOOK_SECRET`.

The bearer token is optional. Use it when the receiver also wants a simple
authorization token before verifying the HMAC signature. Generate it separately:

```sh
openssl rand -base64 32
```

Store it in the Worker:

```sh
pnpm exec wrangler secret put LITE_WEBHOOK_BEARER_TOKEN
```

Use that same bearer token in the receiver environment, for example as
`LITE_WEBHOOK_BEARER_TOKEN`.

Rotate either secret by updating both sides. Update the receiver first if it can
accept old and new values during rollout; otherwise expect webhook delivery to
fail until both sides match.

## Webhook Authentication

Each request is signed with HMAC-SHA256 over:

```text
${timestamp}
${nonce}
${body}
```

Headers:

- `X-Spinupmail-Lite-Timestamp`
- `X-Spinupmail-Lite-Nonce`
- `X-Spinupmail-Lite-Event-Id`
- `X-Spinupmail-Lite-Signature` as `v1=<hex>`

Receiver example:

```ts
import { verifyLiteWebhookRequest } from "@spinupmail/lite-router";

export async function POST(request: Request) {
  const result = await verifyLiteWebhookRequest(
    request,
    process.env.LITE_WEBHOOK_SECRET!,
    {
      bearerToken: process.env.LITE_WEBHOOK_BEARER_TOKEN,
    }
  );

  if (!result.ok) {
    return new Response("invalid signature", { status: 401 });
  }

  const payload = JSON.parse(result.body);
  return Response.json({ received: payload.eventId });
}
```

## Delivery Model

Delivery is synchronous inside the `email()` handler. If the webhook endpoint is
missing, unavailable, times out, returns a non-2xx response, or the message is
over the configured size limit, the Worker rejects the inbound message by
default. There is no durable retry queue in this package; build persistence and
replay on the receiver side if you need guaranteed delivery.

## Attachments

This lite package does not support attachment file delivery, storage, download,
or replay. It only includes attachment metadata in the webhook payload:

- filename
- content type
- disposition
- content ID
- size

Attachment bytes are not forwarded. Large emails, including emails with large
attachments, are rejected when they exceed `LITE_MAX_BYTES`.

Use the full SpinupMail backend if you need attachment file support. The full
version stores attachments in R2 and exposes authenticated download flows.

## Receiver Safety

Treat every payload field derived from the email as untrusted. The lite router
caps metadata sizes, strips control characters from headers and attachment
metadata, and sanitizes attachment filenames, but it does not sanitize
`bodies.html`. If your receiver renders HTML, sanitize it in the receiver before
displaying it.
