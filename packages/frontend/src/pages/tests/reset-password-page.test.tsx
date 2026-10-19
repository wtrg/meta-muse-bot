import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordPage } from "@/pages/reset-password-page";
import { useResetPasswordMutation } from "@/features/auth/hooks/use-auth-mutations";
import { renderWithRouter } from "@/test/router-utils";

vi.mock("@/features/auth/hooks/use-auth-mutations", () => ({
  useResetPasswordMutation: vi.fn(),
}));

const mockedUseResetPasswordMutation = vi.mocked(useResetPasswordMutation);

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseResetPasswordMutation.mockReturnValue({
      mutateAsync: vi.fn(),
      error: null,
      isPending: false,
    } as unknown as ReturnType<typeof useResetPasswordMutation>);
  });

  it("shows guidance when reset token is missing", () => {
    renderWithRouter({
      routes: [{ path: "/reset-password", element: <ResetPasswordPage /> }],
      initialEntries: ["/reset-password"],
    });

    expect(
      screen.getByText(
        "Reset token is missing. Request a new password reset link."
      )
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Update password" })
    ).toBeNull();
  });

  it("shows invalid-token message from query params", () => {
    renderWithRouter({
      routes: [{ path: "/reset-password", element: <ResetPasswordPage /> }],
      initialEntries: ["/reset-password?error=INVALID_TOKEN"],
    });

    expect(
      screen.getByText("This reset link is invalid or expired.")
    ).toBeTruthy();
  });

  it("submits with trimmed token and redirects after success", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ success: true });
    mockedUseResetPasswordMutation.mockReturnValue({
      mutateAsync,
      error: null,
      isPending: false,
    } as unknown as ReturnType<typeof useResetPasswordMutation>);

    const { router } = renderWithRouter({
      routes: [
        { path: "/reset-password", element: <ResetPasswordPage /> },
        { path: "/sign-in", element: <div>sign-in</div> },
      ],
      initialEntries: ["/reset-password?token=%20abc123%20"],
    });

    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "new-password-123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "new-password-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));

    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        token: "abc123",
        newPassword: "new-password-123",
      })
    );

    await waitFor(() =>
      expect(
        router.state.location.pathname + router.state.location.search
      ).toBe("/sign-in?passwordReset=success")
    );
  });

  it("surfaces mutation error message", () => {
    mockedUseResetPasswordMutation.mockReturnValue({
      mutateAsync: vi.fn(),
      error: new Error("Unable to reset password right now."),
      isPending: false,
    } as unknown as ReturnType<typeof useResetPasswordMutation>);

    renderWithRouter({
      routes: [{ path: "/reset-password", element: <ResetPasswordPage /> }],
      initialEntries: ["/reset-password?token=token-1"],
    });

    expect(
      screen.getByText("Unable to reset password right now.")
    ).toBeTruthy();
  });
});
