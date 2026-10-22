import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SignInForm } from "@/features/auth/components/sign-in-form";
import {
  useGoogleSignInMutation,
  useRequestPasswordResetMutation,
  useResendVerificationEmailMutation,
  useSignInMutation,
} from "@/features/auth/hooks/use-auth-mutations";

vi.mock("@/features/auth/hooks/use-auth-mutations", async importOriginal => {
  const actual =
    await importOriginal<
      typeof import("@/features/auth/hooks/use-auth-mutations")
    >();
  return {
    ...actual,
    useGoogleSignInMutation: vi.fn(),
    useRequestPasswordResetMutation: vi.fn(),
    useResendVerificationEmailMutation: vi.fn(),
    useSignInMutation: vi.fn(),
  };
});

vi.mock("@/features/auth/components/turnstile-widget", async () => {
  const React = await import("react");

  return {
    TurnstileWidget: React.forwardRef<
      HTMLDivElement,
      { onTokenChange?: (token: string | null) => void }
    >(function MockTurnstileWidget({ onTokenChange }, _ref) {
      React.useEffect(() => {
        onTokenChange?.("captcha-token");
      }, [onTokenChange]);

      return <div data-testid="turnstile-widget" />;
    }),
  };
});

describe("SignInForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useSignInMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useSignInMutation>);
    vi.mocked(useGoogleSignInMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useGoogleSignInMutation>);
    vi.mocked(useRequestPasswordResetMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useRequestPasswordResetMutation>);
    vi.mocked(useResendVerificationEmailMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useResendVerificationEmailMutation>);
  });

  it("links to /otp and does not link to deprecated /bulk or auto-login", () => {
    render(
      <MemoryRouter>
        <SignInForm
          isForgotPasswordMode={false}
          onForgotPasswordModeChange={vi.fn()}
        />
      </MemoryRouter>
    );

    const otpLink = screen.getByRole("link", { name: /Cổng Tra Cứu OTP/i });
    expect(otpLink.getAttribute("href")).toBe("/otp");

    // Must not contain references to deprecated anonymous endpoints
    expect(screen.queryByRole("link", { name: /bulk/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /auto-login/i })).toBeNull();
    expect(screen.queryByText(/auto-login/i)).toBeNull();
    expect(screen.queryByText(/1-Click Vào Reg Mail/i)).toBeNull();
  });
});
