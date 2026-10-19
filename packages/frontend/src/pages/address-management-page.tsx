import { MailAdd01Icon, LeftToRightListDashIcon } from "@/lib/hugeicons";
import { Link, useLocation } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { HashTabsPage } from "@/components/layout/hash-tabs-page";
import { AddressList } from "@/features/addresses/components/address-list";
import { CreateAddressForm } from "@/features/addresses/components/create-address-form";
import { useDomainsQuery } from "@/features/addresses/hooks/use-addresses";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useActiveOrganizationQuery } from "@/features/organization/hooks/use-organizations";
import { useIntegrationsQuery } from "@/features/organization/hooks/use-integrations";

export const AddressManagementPage = () => {
  const location = useLocation();
  const { user, activeOrganizationId } = useAuth();
  const domainsQuery = useDomainsQuery();
  const activeOrganizationQuery = useActiveOrganizationQuery();
  const activeOrganization = activeOrganizationQuery.data;
  const currentMember =
    activeOrganization?.members.find(member => member.user.id === user?.id) ??
    null;
  const canManageIntegrations =
    currentMember?.role === "owner" || currentMember?.role === "admin";
  const integrationsQuery = useIntegrationsQuery(canManageIntegrations);
  const integrations = canManageIntegrations
    ? (integrationsQuery.data ?? [])
    : [];
  const isEditRoute = location.pathname.startsWith("/addresses/edit/");
  const defaultSection = isEditRoute ? "addresses-list" : "create-address";

  const createAddressForm = (
    <section
      id="create-address"
      className="max-w-3xl rounded-lg border border-border/70 p-4 sm:p-5"
      aria-label="Create email address"
    >
      <CreateAddressForm
        key={activeOrganization?.id ?? activeOrganizationId ?? ""}
        domains={domainsQuery.data?.items ?? []}
        isDomainsLoading={domainsQuery.isLoading}
        forcedLocalPartPrefix={domainsQuery.data?.forcedLocalPartPrefix}
        maxReceivedEmailsPerOrganization={
          domainsQuery.data?.maxReceivedEmailsPerOrganization
        }
        maxReceivedEmailsPerAddress={
          domainsQuery.data?.maxReceivedEmailsPerAddress
        }
        canManageIntegrations={canManageIntegrations}
        integrations={integrations}
      />
    </section>
  );
  const addressesList = (
    <section id="addresses-list" aria-label="Addresses list">
      <AddressList
        domains={domainsQuery.data?.items ?? []}
        forcedLocalPartPrefix={domainsQuery.data?.forcedLocalPartPrefix}
        maxReceivedEmailsPerAddress={
          domainsQuery.data?.maxReceivedEmailsPerAddress
        }
        canManageIntegrations={canManageIntegrations}
        integrations={integrations}
      />
    </section>
  );

  return (
    <div className="space-y-4">
      {domainsQuery.error ? (
        <p className="text-sm text-destructive">{domainsQuery.error.message}</p>
      ) : null}
      {canManageIntegrations && integrationsQuery.error ? (
        <p className="text-sm text-destructive">
          {integrationsQuery.error.message}
        </p>
      ) : null}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-lg bg-primary/10 border border-primary/20 max-w-3xl">
        <div>
          <div className="text-sm font-semibold text-primary">⚡ Tạo Email Hàng Loạt & Quét OTP Muse.ai / Meta</div>
          <div className="text-xs text-muted-foreground">Tạo nhanh 5–50 mail kèm mã PIN riêng và bảng trích xuất OTP tự động.</div>
        </div>
        <Link to="/bulk" className={buttonVariants({ size: "sm", className: "shrink-0" })}>
          Mở Trang Reg Mail (/bulk) ↗
        </Link>
      </div>

      <HashTabsPage
        ariaLabel="Address sections"
        defaultSection={defaultSection}
        forcedSection={isEditRoute ? "addresses-list" : undefined}
        tabsHeaderClassName="max-w-3xl"
        sections={[
          {
            id: "create-address",
            label: "Create New",
            icon: MailAdd01Icon,
            content: createAddressForm,
          },
          {
            id: "addresses-list",
            label: "Address List",
            icon: LeftToRightListDashIcon,
            content: addressesList,
          },
        ]}
      />
    </div>
  );
};
