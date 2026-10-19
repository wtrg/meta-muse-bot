# SpinupMail SDK

[SpinupMail](https://spinupmail.com) TypeScript SDK for creating and reading temporary email addresses.

## Install

```bash
pnpm install spinupmail
```

## Usage

```ts
import { SpinupMail } from "spinupmail";

const spinupmail = new SpinupMail();

const address = await spinupmail.addresses.create({
  acceptedRiskNotice: true,
});

const email = await spinupmail.inboxes.waitForEmail({
  addressId: address.id,
  after: new Date(),
  subjectIncludes: "verify",
  timeoutMs: 30_000,
});

console.log(email.subject);
```

`new SpinupMail()` defaults to:

- `process.env.SPINUPMAIL_API_KEY`
- `process.env.SPINUPMAIL_BASE_URL` or `https://api.spinupmail.com`
- `process.env.SPINUPMAIL_ORGANIZATION_ID` or `process.env.SPINUPMAIL_ORG_ID`

You can override any of them:

```ts
import { SpinupMail } from "spinupmail";

const spinupmail = new SpinupMail({
  apiKey: "spin_other_key",
  organizationId: "org_123",
});
```

If you omit `localPart`, the SDK generates a random valid inbox name before sending the request.

Use `search` to match recent emails by indexed content:

```ts
const email = await spinupmail.inboxes.waitForEmail({
  addressId: address.id,
  search: "verify",
  timeoutMs: 30_000,
});

const emails = await spinupmail.emails.list({
  addressId: address.id,
  search: "verify",
});
```

List inbox emails with pagination:

```ts
const page = await spinupmail.emails.list({
  addressId: address.id,
  page: 1,
  pageSize: 25,
});
```

Use `after` with local filters to wait for a specific email after a timestamp:

```ts
const runStartedAt = new Date();

const email = await spinupmail.inboxes.waitForEmail({
  addressId: address.id,
  after: runStartedAt,
  subjectIncludes: "verify",
  bodyIncludes: "654321",
  timeoutMs: 30_000,
});

console.log(email.text);
```

Manage organization integrations:

```ts
const integrations = await spinupmail.integrations.list();

const dispatches = await spinupmail.integrations.listDispatches(
  integrations.items[0].id,
  { page: 1, pageSize: 20 }
);
```
