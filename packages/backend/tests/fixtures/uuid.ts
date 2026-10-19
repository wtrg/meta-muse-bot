import { vi } from "vitest";

type Uuid = ReturnType<typeof crypto.randomUUID>;

export const withMockedUuids = async <T>(
  uuids: Uuid[],
  fn: () => T | Promise<T>
) => {
  const queue = [...uuids];
  const fallbackUuid: Uuid = "00000000-0000-0000-0000-000000000000";
  const spy = vi.spyOn(crypto, "randomUUID").mockImplementation(() => {
    return queue.shift() ?? fallbackUuid;
  });

  try {
    return await fn();
  } finally {
    spy.mockRestore();
  }
};
