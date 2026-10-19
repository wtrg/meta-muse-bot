import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useIsMobile } from "@/hooks/use-mobile";

describe("useIsMobile", () => {
  let listeners: Set<() => void>;
  let matches = false;
  let mediaQueryList: MediaQueryList;
  let matchMediaMock: ReturnType<typeof vi.fn>;

  const emitChange = () => {
    for (const listener of listeners) {
      listener();
    }
  };

  beforeEach(() => {
    listeners = new Set();
    matches = false;
    mediaQueryList = {
      get matches() {
        return matches;
      },
      media: "(max-width: 767px)",
      onchange: null,
      addEventListener: vi.fn((_type: string, listener: EventListener) => {
        listeners.add(listener as () => void);
      }),
      removeEventListener: vi.fn((_type: string, listener: EventListener) => {
        listeners.delete(listener as () => void);
      }),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } as unknown as MediaQueryList;

    matchMediaMock = vi.fn(() => mediaQueryList);
    vi.stubGlobal("matchMedia", matchMediaMock);
  });

  it("returns current media query snapshot on mount", () => {
    matches = true;

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(true);
  });

  it("updates when matchMedia change events fire", () => {
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    act(() => {
      matches = true;
      emitChange();
    });

    expect(result.current).toBe(true);
  });

  it("removes the media query listener on unmount", () => {
    const { unmount } = renderHook(() => useIsMobile());
    const listener = (
      mediaQueryList.addEventListener as ReturnType<typeof vi.fn>
    ).mock.calls[0]?.[1];

    unmount();

    expect(mediaQueryList.removeEventListener).toHaveBeenCalledWith(
      "change",
      listener
    );
  });
});
