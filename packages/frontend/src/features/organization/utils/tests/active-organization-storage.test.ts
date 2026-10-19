import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  clearLastActiveOrganizationId,
  getLastActiveOrganizationId,
  setLastActiveOrganizationId,
} from "../active-organization-storage";

describe("active organization storage", () => {
  const createStorage = () => {
    const map = new Map<string, string>();
    return {
      getItem: (key: string) => map.get(key) ?? null,
      setItem: (key: string, value: string) => {
        map.set(key, value);
      },
      removeItem: (key: string) => {
        map.delete(key);
      },
      clear: () => {
        map.clear();
      },
    };
  };

  beforeAll(() => {
    vi.stubGlobal("window", {
      localStorage: createStorage(),
    });
  });

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  it("stores organization ids per user", () => {
    setLastActiveOrganizationId("user-1", "org-1");
    setLastActiveOrganizationId("user-2", "org-2");

    expect(getLastActiveOrganizationId("user-1")).toBe("org-1");
    expect(getLastActiveOrganizationId("user-2")).toBe("org-2");
  });

  it("clears only target user entry", () => {
    setLastActiveOrganizationId("user-1", "org-1");
    setLastActiveOrganizationId("user-2", "org-2");

    clearLastActiveOrganizationId("user-1");

    expect(getLastActiveOrganizationId("user-1")).toBeNull();
    expect(getLastActiveOrganizationId("user-2")).toBe("org-2");
  });
});
