import { createLiteRouter } from "./handler";

export {
  createLiteWebhookHeaders,
  signLiteWebhookBody,
  verifyLiteWebhookRequest,
  LITE_EVENT_ID_HEADER,
  LITE_NONCE_HEADER,
  LITE_SIGNATURE_HEADER,
  LITE_TIMESTAMP_HEADER,
} from "./auth";
export { createLiteRouter, handleLiteEmail } from "./handler";
export type {
  LiteEmailAttachmentMetadata,
  LiteEmailWebhookPayload,
  LiteRouterEnv,
  LiteRouterOptions,
} from "./types";

export default createLiteRouter();
