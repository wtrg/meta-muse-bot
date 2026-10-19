import * as React from "react";
import { useMemo } from "react";
import { LogoutIcon, Mail01Icon } from "@/lib/hugeicons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { AppLogo } from "@/components/app-logo";
import { ModeToggle } from "@/components/mode-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  useAcceptInvitationMutation,
  useCreateOrganizationMutation,
  useOrganizationInvitationQuery,
  useOrganizationsQuery,
  useSetActiveOrganizationMutation,
  useUserInvitationsQuery,
} from "@/features/organization/hooks/use-organizations";

const safeNextPath = (value: string | null) => {
  if (!value) return "/";
  if (!value.startsWith("/")) return "/";
  if (value.startsWith("//")) return "/";
  return value;
};

export const OrganizationOnboardingPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { activeOrganizationId, refreshSession, signOut, isSigningOut } =
    useAuth();

  const invitationId = searchParams.get("invitationId");
  const invitationQuery = useOrganizationInvitationQuery(invitationId);
  const userInvitationsQuery = useUserInvitationsQuery();
  const organizationsQuery = useOrganizationsQuery();
  const createOrganizationMutation = useCreateOrganizationMutation();
  const setActiveOrganizationMutation = useSetActiveOrganizationMutation();
  const acceptInvitationMutation = useAcceptInvitationMutation();

  const [organizationName, setOrganizationName] = React.useState("");
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const nextPath = useMemo(
    () => safeNextPath(searchParams.get("next")),
    [searchParams]
  );

  const handleComplete = async () => {
    await refreshSession();
    await navigate(nextPath, { replace: true });
  };

  const handleCreateOrganization = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrorMessage(null);

    try {
      await createOrganizationMutation.mutateAsync(organizationName);
      await handleComplete();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  const handleAcceptInvitation = async (id: string) => {
    setErrorMessage(null);

    try {
      await acceptInvitationMutation.mutateAsync(id);
      await handleComplete();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  const handleSignOut = async () => {
    setErrorMessage(null);

    try {
      await signOut();
      await navigate("/", { replace: true });
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  const isBusy =
    createOrganizationMutation.isPending ||
    acceptInvitationMutation.isPending ||
    setActiveOrganizationMutation.isPending ||
    isSigningOut;

  const organizations = organizationsQuery.data ?? [];

  const pendingInvitations = (userInvitationsQuery.data ?? []).filter(
    invitation => invitation.status === "pending"
  );

  const handleUseExistingOrganization = async (organizationId: string) => {
    setErrorMessage(null);

    try {
      await setActiveOrganizationMutation.mutateAsync(organizationId);
      await handleComplete();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="mx-auto flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <AppLogo className="mx-auto" textClassName="text-[15px]" />
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-balance">
              Let's get started
            </h1>
            <p className="text-sm text-muted-foreground text-balance">
              Create a new organization or join an existing one to start
              managing shared inboxes with your team.
            </p>
          </div>
        </div>

        <Card className="border-border/70 bg-card/60">
          <CardHeader>
            <CardTitle className="text-xl">Create an organization</CardTitle>
            <p className="text-sm text-muted-foreground">
              You will be able to update the organization name and invite team
              members later.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <form className="space-y-3" onSubmit={handleCreateOrganization}>
              <Input
                value={organizationName}
                onChange={event => setOrganizationName(event.target.value)}
                placeholder="E-Corp"
                aria-label="Organization name"
                minLength={2}
                required
              />
              <Button
                className="w-full cursor-pointer"
                disabled={isBusy}
                type="submit"
              >
                {createOrganizationMutation.isPending
                  ? "Creating..."
                  : "Create organization"}
              </Button>
            </form>

            {!activeOrganizationId && organizations.length > 0 ? (
              <div className="space-y-2 rounded-md border border-border/70 p-3">
                <p className="text-xs text-muted-foreground">
                  Already have organizations?
                </p>
                {organizations.map(organization => (
                  <div
                    className="flex items-center justify-between gap-2"
                    key={organization.id}
                  >
                    <p className="truncate text-sm font-medium">
                      {organization.name}
                    </p>
                    <Button
                      disabled={isBusy}
                      onClick={() =>
                        void handleUseExistingOrganization(organization.id)
                      }
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      Use
                    </Button>
                  </div>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/60">
          <CardHeader>
            <CardTitle className="text-xl">Join an organization</CardTitle>
            <p className="text-sm text-muted-foreground">
              Join using an invitation link. Pending invitations for your email
              are listed below.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {invitationId ? (
              invitationQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">
                  Loading invitation...
                </p>
              ) : invitationQuery.error ? (
                <p className="text-sm text-destructive">
                  {invitationQuery.error.message}
                </p>
              ) : invitationQuery.data ? (
                <div className="space-y-2 rounded-md border border-border/70 p-3">
                  <p className="text-sm font-medium">
                    {invitationQuery.data.organizationName}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Invited by {invitationQuery.data.inviterEmail}
                  </p>
                  <Button
                    className="w-full"
                    disabled={isBusy}
                    onClick={() =>
                      void handleAcceptInvitation(invitationQuery.data!.id)
                    }
                    type="button"
                  >
                    Accept invite
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Invitation not found.
                </p>
              )
            ) : null}

            {userInvitationsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">
                Checking pending invitations...
              </p>
            ) : pendingInvitations.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/80 bg-muted/25 p-5">
                <div className="flex flex-row items-center justify-center gap-3 text-center">
                  <div className="flex size-11 items-center justify-center rounded-full border border-border/70 shadow-sm">
                    <HugeiconsIcon
                      icon={Mail01Icon}
                      className="h-5 w-5 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground font-medium">
                      No pending invitations
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {pendingInvitations.map(invitation => (
                  <div
                    className="flex items-center justify-between rounded-md border border-border/70 p-3"
                    key={invitation.id}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {invitation.organizationName}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        Role: {invitation.role}
                      </p>
                    </div>
                    <Button
                      disabled={isBusy}
                      onClick={() => void handleAcceptInvitation(invitation.id)}
                      size="sm"
                      type="button"
                      variant="outline"
                      className="cursor-pointer"
                    >
                      Join
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col items-center justify-between gap-3 border-t border-border/70 pt-2 text-sm text-muted-foreground sm:flex-row">
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
            <Link
              className="transition-colors hover:text-foreground"
              target="_blank"
              to="/terms"
            >
              Terms
            </Link>
            <Link
              className="transition-colors hover:text-foreground"
              target="_blank"
              to="/privacy"
            >
              Privacy Policy
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <Tooltip>
              <TooltipTrigger render={<div className="flex" />}>
                <ModeToggle />
              </TooltipTrigger>
              <TooltipContent side="top">Theme</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="cursor-pointer border-border/50 bg-transparent hover:border-border/60 dark:border-input/50 dark:hover:border-input/60"
                    aria-label="Logout"
                    onClick={() => void handleSignOut()}
                    disabled={isBusy}
                  />
                }
              >
                <HugeiconsIcon
                  icon={LogoutIcon}
                  strokeWidth={2}
                  className="h-4 w-4"
                />
              </TooltipTrigger>
              <TooltipContent side="top">Logout</TooltipContent>
            </Tooltip>
          </div>
        </div>
      </div>

      {errorMessage ? (
        <p className="fixed right-4 bottom-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
};
