import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { CreateAddressForm } from "@/features/addresses/components/create-address-form";
import { useCreateAddressMutation } from "@/features/addresses/hooks/use-addresses";
import { renderWithAct, rerenderWithAct } from "@/test/render-with-act";

vi.mock("react-router", () => ({
  Link: ({ children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a {...props}>{children}</a>
  ),
}));

vi.mock("@/features/addresses/hooks/use-addresses", () => ({
  useCreateAddressMutation: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    promise: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockedUseCreateAddressMutation = vi.mocked(useCreateAddressMutation);
const mockedToastPromise = vi.mocked(toast.promise);

const createMutation = {
  isPending: false,
  mutateAsync: vi.fn(),
  reset: vi.fn(),
};

const telegramIntegration = {
  id: "integration-1",
  provider: "telegram" as const,
  name: "Ops alerts",
  status: "active" as const,
  supportedEventTypes: ["email.received" as const],
  mailboxCount: 2,
  lastValidatedAt: "2026-04-20T10:00:00.000Z",
  lastValidatedAtMs: 1_745_143_200_000,
  createdAt: "2026-04-20T10:00:00.000Z",
  createdAtMs: 1_745_143_200_000,
  updatedAt: "2026-04-20T10:00:00.000Z",
  updatedAtMs: 1_745_143_200_000,
  publicConfig: {
    telegramBotId: "123456",
    botUsername: "spinupmail_bot",
    chatId: "-1001234567890",
    chatLabel: "Product alerts",
  },
};

describe("CreateAddressForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createMutation.mutateAsync.mockReset();
    mockedUseCreateAddressMutation.mockReturnValue(
      createMutation as unknown as ReturnType<typeof useCreateAddressMutation>
    );
    mockedToastPromise.mockImplementation(((
      promise: PromiseLike<unknown> | (() => PromiseLike<unknown>)
    ) => ({
      unwrap: () =>
        typeof promise === "function"
          ? Promise.resolve(promise())
          : Promise.resolve(promise),
    })) as typeof toast.promise);
  });

  const submitMailbox = async (withPin: boolean) => {
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "owned-mailbox" },
    });
    fireEvent.click(screen.getByText("Delete all"));
    fireEvent.click(screen.getByRole("checkbox"));
    if (withPin)
      fireEvent.click(
        screen.getByRole("switch", { name: "Generate a mailbox PIN" })
      );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Create address" }));
    });
  };

  it("requests a PIN only when selected and shows/copies the top-level secret until dismissed", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    createMutation.mutateAsync.mockResolvedValue({
      address: "owned-mailbox@example.com",
      pin: "739281",
    });
    const view = await renderWithAct(
      <CreateAddressForm domains={["example.com"]} />
    );
    await submitMailbox(true);
    await waitFor(() =>
      expect(screen.getByLabelText("Mailbox PIN").textContent).toBe("739281")
    );
    expect(createMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ generatePin: true })
    );
    expect(createMutation.reset).toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy mailbox PIN" }));
    });
    expect(writeText).toHaveBeenCalledWith("739281");
    fireEvent.click(
      screen.getByRole("button", { name: "I've saved this PIN" })
    );
    expect(screen.queryByLabelText("Mailbox PIN")).toBeNull();
    await rerenderWithAct(
      view,
      <CreateAddressForm domains={["example.com"]} />
    );
    expect(screen.queryByText("739281")).toBeNull();
    view.unmount();
    await renderWithAct(<CreateAddressForm domains={["example.com"]} />);
    expect(screen.queryByText("739281")).toBeNull();
    expect(window.location.href).not.toContain("739281");
    expect(JSON.stringify(localStorage)).not.toContain("739281");
    expect(
      JSON.stringify(mockedToastPromise.mock.calls.map(call => call[1]))
    ).not.toContain("739281");
  });

  it("keeps PIN creation opt-in and never displays a metadata PIN", async () => {
    createMutation.mutateAsync.mockResolvedValue({
      address: "owned-mailbox@example.com",
      meta: { pin: "739281" },
    });
    await renderWithAct(<CreateAddressForm domains={["example.com"]} />);
    await submitMailbox(false);
    expect(createMutation.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ generatePin: false })
    );
    expect(screen.queryByLabelText("Mailbox PIN")).toBeNull();
  });

  it("preserves provisioned PIN of previous mailbox and blocks new submission until saved/dismissed", async () => {
    createMutation.mutateAsync
      .mockResolvedValueOnce({
        address: "mailbox-a@example.com",
        pin: "111222",
      })
      .mockRejectedValueOnce(new Error("Failed to create mailbox B"));

    await renderWithAct(<CreateAddressForm domains={["example.com"]} />);

    // Step 1: Create mailbox A with PIN
    await submitMailbox(true);
    await waitFor(() =>
      expect(screen.getByLabelText("Mailbox PIN").textContent).toBe("111222")
    );
    expect(createMutation.mutateAsync).toHaveBeenCalledTimes(1);

    // Step 2: Attempt to create mailbox B without dismissing PIN A
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "mailbox-b" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Create address" }));
    });

    // Step 3: Verify B was blocked and did NOT call mutateAsync, PIN A is still visible, and guidance was provided
    expect(createMutation.mutateAsync).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Mailbox PIN").textContent).toBe("111222");
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("save or dismiss")
    );

    // Step 4: Clipboard failure on copy does not dismiss PIN
    const failingClipboard = {
      writeText: vi.fn().mockRejectedValue(new Error("Clipboard denied")),
    };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: failingClipboard,
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy mailbox PIN" }));
    });
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Could not copy PIN")
    );
    expect(screen.getByLabelText("Mailbox PIN").textContent).toBe("111222");

    // Step 5: User explicitly dismisses PIN A
    fireEvent.click(
      screen.getByRole("button", { name: "I've saved this PIN" })
    );
    expect(screen.queryByLabelText("Mailbox PIN")).toBeNull();

    // Step 6: Now mailbox B can be submitted
    fireEvent.click(screen.getByText("Delete all"));
    fireEvent.click(screen.getByRole("checkbox"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Create address" }));
    });
    expect(createMutation.mutateAsync).toHaveBeenCalledTimes(2);
  });

  it("reports missing provisioned PIN instead of inventing a secret", async () => {
    createMutation.mutateAsync.mockResolvedValue({
      address: "owned-mailbox@example.com",
    });
    await renderWithAct(<CreateAddressForm domains={["example.com"]} />);
    await submitMailbox(true);
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("no mailbox PIN was returned")
    );
    expect(screen.queryByLabelText("Mailbox PIN")).toBeNull();
  });

  it("prefills max stored emails and updates it when the configured default arrives", async () => {
    const view = await renderWithAct(
      <CreateAddressForm domains={["example.com"]} />
    );

    expect(
      (screen.getByLabelText("Max stored emails") as HTMLInputElement).value
    ).toBe("100");
    expect(screen.getByText("Inbox Limits")).toBeTruthy();

    await rerenderWithAct(
      view,
      <CreateAddressForm
        domains={["example.com"]}
        maxReceivedEmailsPerAddress={250}
      />
    );

    await waitFor(() =>
      expect(
        (screen.getByLabelText("Max stored emails") as HTMLInputElement).value
      ).toBe("250")
    );
  });

  it("blocks submit until the limit action is selected explicitly", async () => {
    mockedUseCreateAddressMutation.mockReturnValue(
      createMutation as unknown as ReturnType<typeof useCreateAddressMutation>
    );

    await renderWithAct(<CreateAddressForm domains={["example.com"]} />);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "ops-team" },
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Create address" }));

    await waitFor(() =>
      expect(createMutation.mutateAsync).not.toHaveBeenCalled()
    );
    expect(
      screen.getByText("Choose what happens when the limit is reached")
    ).toBeTruthy();
  });

  it("submits with the only available domain when domains load after mount", async () => {
    createMutation.mutateAsync.mockResolvedValue({
      address: "mailbox01@spinupmail.dev",
    });

    const view = await renderWithAct(
      <CreateAddressForm domains={[]} isDomainsLoading />
    );

    await rerenderWithAct(
      view,
      <CreateAddressForm
        domains={["spinupmail.dev"]}
        isDomainsLoading={false}
      />
    );

    expect(
      (screen.getByDisplayValue("spinupmail.dev") as HTMLInputElement).disabled
    ).toBe(true);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "mailbox01" },
    });
    fireEvent.click(screen.getByText("Delete all"));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Create address" }));

    await waitFor(() =>
      expect(createMutation.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          localPart: "mailbox01",
          domain: "spinupmail.dev",
          maxReceivedEmailAction: "cleanAll",
          acceptedRiskNotice: true,
        })
      )
    );
    expect(screen.queryByText("Domain is required")).toBeNull();
    expect(
      screen.queryByText("Select one of the available domains")
    ).toBeNull();
  });

  it("shows provider radios only after integrations are enabled", async () => {
    await renderWithAct(
      <CreateAddressForm
        domains={["example.com"]}
        canManageIntegrations
        integrations={[telegramIntegration]}
      />
    );

    expect(
      screen.queryByRole("radio", {
        name: "Telegram",
      })
    ).toBeNull();
    expect(screen.queryByText("Ops alerts")).toBeNull();

    await act(async () => {
      fireEvent.click(
        screen.getByRole("switch", {
          name: "Enable integrations",
        })
      );
    });

    expect(screen.getByRole("radio", { name: "Telegram" })).toBeTruthy();
    expect(screen.getByText("Ops alerts")).toBeTruthy();
    expect(
      screen.getByText("Send emails to Telegram (Product alerts)")
    ).toBeTruthy();
  });

  it("updates the provider badge when a connection is selected", async () => {
    await renderWithAct(
      <CreateAddressForm
        domains={["example.com"]}
        canManageIntegrations
        integrations={[telegramIntegration]}
      />
    );

    await act(async () => {
      fireEvent.click(
        screen.getByRole("switch", {
          name: "Enable integrations",
        })
      );
    });

    expect(screen.getByText("0/1")).toBeTruthy();

    fireEvent.click(
      await screen.findByRole("checkbox", { name: "Ops alerts" })
    );

    expect(await screen.findByText("1/1")).toBeTruthy();
  });
});
