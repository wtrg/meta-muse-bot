const LAST_ACTIVE_ORGANIZATION_STORAGE_KEY =
  "spinupmail:last-active-organization-id-by-user";

const canUseStorage = () => typeof window !== "undefined";

const readStorageMap = () => {
  if (!canUseStorage()) return {};
  const rawValue = window.localStorage.getItem(
    LAST_ACTIVE_ORGANIZATION_STORAGE_KEY
  );
  if (!rawValue) return {};

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    return parsed as Record<string, string>;
  } catch {
    return {};
  }
};

const writeStorageMap = (value: Record<string, string>) => {
  if (!canUseStorage()) return;
  window.localStorage.setItem(
    LAST_ACTIVE_ORGANIZATION_STORAGE_KEY,
    JSON.stringify(value)
  );
};

export const getLastActiveOrganizationId = (
  userId: string | null | undefined
) => {
  if (!userId) return null;
  if (!canUseStorage()) return null;
  const map = readStorageMap();
  return map[userId] ?? null;
};

export const setLastActiveOrganizationId = (
  userId: string | null | undefined,
  organizationId: string
) => {
  if (!userId) return;
  if (!canUseStorage()) return;
  const map = readStorageMap();
  map[userId] = organizationId;
  writeStorageMap(map);
};

export const clearLastActiveOrganizationId = (userId?: string | null) => {
  if (!canUseStorage()) return;
  if (!userId) {
    window.localStorage.removeItem(LAST_ACTIVE_ORGANIZATION_STORAGE_KEY);
    return;
  }

  const map = readStorageMap();
  if (!(userId in map)) return;
  delete map[userId];

  if (Object.keys(map).length === 0) {
    window.localStorage.removeItem(LAST_ACTIVE_ORGANIZATION_STORAGE_KEY);
    return;
  }

  writeStorageMap(map);
};
