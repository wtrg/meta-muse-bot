import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { BulkCreatePage } from "@/pages/bulk-create-page";

describe("BulkCreatePage", () => {
  it("provides links to authenticated /addresses and PIN-protected /otp routes", () => {
    render(
      <MemoryRouter>
        <BulkCreatePage />
      </MemoryRouter>
    );

    const addressesLinks = screen.getAllByRole("link", {
      name: /Quản Lý Hộp Thư/i,
    });
    expect(addressesLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of addressesLinks) {
      expect(link.getAttribute("href")).toBe("/addresses");
    }

    const otpLinks = screen.getAllByRole("link", {
      name: /Cổng Tra Cứu OTP/i,
    });
    expect(otpLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of otpLinks) {
      expect(link.getAttribute("href")).toBe("/otp");
    }
  });
});
