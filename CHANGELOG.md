# Changelog

All notable changes to SpinupMail will be documented in this file.

The format is based on Keep a Changelog, and SpinupMail uses Semantic
Versioning for tagged releases.

## [Unreleased]

- No unreleased changes yet.

## [0.3.0](https://github.com/ridvan/spinupmail/releases/tag/v0.3.0) - 2026-04-25

### Added

- Added a delete-organization flow with backend access checks,
  rate-limiting, organization-switching safeguards, and settings-page UI.
  [`47d0958`](https://github.com/ridvan/spinupmail/commit/47d0958)
- Added paginated inbox loading across the backend API, contracts, SDK tests,
  and inbox UI, including a clearer empty-selection state.
  [`f8e791c`](https://github.com/ridvan/spinupmail/commit/f8e791c)

### Changed

- Refactored address management into hash-linked tabs and refreshed the create
  address form layout, address list actions, and related route tests.
  [`bdf5ec4`](https://github.com/ridvan/spinupmail/commit/bdf5ec4),
  [`512b809`](https://github.com/ridvan/spinupmail/commit/512b809)
- Renamed the max-received-email overflow action from `rejectNew` to `dropNew`
  across backend validation, contracts, frontend forms, and docs.
  [`fe6c06b`](https://github.com/ridvan/spinupmail/commit/fe6c06b)
- Refined the dashboard overview with a cleaner no-card layout, updated chart
  surfaces, and matching app background colors.
  [`8deb5ac`](https://github.com/ridvan/spinupmail/commit/8deb5ac),
  [`0fa5a07`](https://github.com/ridvan/spinupmail/commit/0fa5a07)
- Improved the route error view to better match the product UI.
  [`c4a68a8`](https://github.com/ridvan/spinupmail/commit/c4a68a8)

### Fixed

- Fixed settings hash tabs on smaller screens by making the shared tab shell
  horizontally scrollable without breaking desktop layout.
  [`4f61b4c`](https://github.com/ridvan/spinupmail/commit/4f61b4c)
- Fixed frontend component tests by avoiding Hugeicons barrel imports and
  wrapping ScrollArea interactions in the test act helper.
  [`647185d`](https://github.com/ridvan/spinupmail/commit/647185d),
  [`a1734fc`](https://github.com/ridvan/spinupmail/commit/a1734fc)
- Fixed the route error page test after the route error UI refresh.
  [`009cfa7`](https://github.com/ridvan/spinupmail/commit/009cfa7)

## [0.2.0](https://github.com/ridvan/spinupmail/releases/tag/v0.2.0) - 2026-04-24

### Added

- Added an organization-scoped integrations platform with encrypted provider
  secrets, address-level `email.received` subscriptions, queue-backed dispatch,
  retry/backoff handling, dispatch replay, and delivery-attempt tracking.
  [`bc02533`](https://github.com/ridvan/spinupmail/commit/bc02533)
- Added Telegram integrations for inbound-email notifications, including
  connection validation, saved-integration confirmation messages, bot/chat
  metadata, and email delivery messages with dashboard links when available.
  [`bc02533`](https://github.com/ridvan/spinupmail/commit/bc02533),
  [`01d36d7`](https://github.com/ridvan/spinupmail/commit/01d36d7)
- Added environment-backed integration limits: organizations default to 3
  integrations and 100 integration dispatch attempts per rolling day, with
  over-limit dispatches kept scheduled instead of dropped.
  [`f71f49f`](https://github.com/ridvan/spinupmail/commit/f71f49f)
- Added integration management UI in organization settings and compact
  provider-first integration selectors in the create/edit address flows.
  [`bc02533`](https://github.com/ridvan/spinupmail/commit/bc02533),
  [`3764485`](https://github.com/ridvan/spinupmail/commit/3764485)
- Added integrations documentation across the README, installation docs, API
  reference, Cloudflare resources, secrets, and limits/security pages.
  [`dbe73b0`](https://github.com/ridvan/spinupmail/commit/dbe73b0)

### Changed

- Refactored account settings into hash-linked tabs for Profile, Password,
  Two-Factor, and API Keys, with refreshed panels and shared tab layout
  primitives. [`71e0c95`](https://github.com/ridvan/spinupmail/commit/71e0c95)
- Refactored organization settings into hash-linked tabs for Profile, Members,
  Invitations, and Integrations, with more focused management panels.
  [`3dc1b86`](https://github.com/ridvan/spinupmail/commit/3dc1b86)
- Updated the landing page and docs navigation to surface integrations as a
  first-class product capability.
  [`dbe73b0`](https://github.com/ridvan/spinupmail/commit/dbe73b0)

### Fixed

- Fixed the integration dispatch queue binding name in Worker configuration.
  [`2cb7ff5`](https://github.com/ridvan/spinupmail/commit/2cb7ff5)

## [0.1.1](https://github.com/ridvan/spinupmail/releases/tag/v0.1.1) - 2026-04-19

- Fixed inbound email parsing in the backend Worker by replacing the broken
  `sanitize-html` lazy-load path with a Worker-safe dynamic import.
  [`6a1f59e`](https://github.com/ridvan/spinupmail/commit/6a1f59e)

## [0.1.0](https://github.com/ridvan/spinupmail/releases/tag/v0.1.0) - 2026-04-19

- Initial public SpinupMail release.
- Self-hosted temporary email platform on Cloudflare Workers, D1, KV, and R2.
- React dashboard, browser extension, and public TypeScript SDK support.
- Inbound email capture with organization-scoped inboxes, attachments, and API
  access.

## Release Tracks

- Repo releases use tags like `v0.1.0` and represent self-hosted SpinupMail
  product releases.
- SDK releases use tags like `sdk-v0.1.1` and publish the `spinupmail` npm
  package from `packages/sdk`.
