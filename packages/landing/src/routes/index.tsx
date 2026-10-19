import { createFileRoute } from "@tanstack/react-router";
import { ApiShowcase } from "@/components/landing/api-showcase";
import { CtaSection } from "@/components/landing/cta-section";
import { Features } from "@/components/landing/features";
import { Footer } from "@/components/landing/footer";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Nav } from "@/components/landing/nav";
import { TrustPipeline } from "@/components/landing/trust-pipeline";
import { landingLinks } from "@/lib/links";
import { siteConfig } from "@/lib/site";

const websiteStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: siteConfig.siteName,
  alternateName: [siteConfig.alternateSiteName],
  url: siteConfig.homeUrl,
};

const organizationStructuredData = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: siteConfig.siteName,
  alternateName: siteConfig.alternateSiteName,
  url: siteConfig.homeUrl,
  logo: siteConfig.logoUrl,
  sameAs: [landingLinks.github],
};

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      {
        title: siteConfig.title,
      },
      {
        name: "description",
        content: siteConfig.description,
      },
      {
        property: "og:title",
        content: siteConfig.title,
      },
      {
        property: "og:description",
        content: siteConfig.description,
      },
      {
        property: "og:type",
        content: "website",
      },
      {
        property: "og:url",
        content: siteConfig.homeUrl,
      },
      {
        property: "og:site_name",
        content: siteConfig.siteName,
      },
      {
        property: "og:locale",
        content: siteConfig.locale,
      },
      {
        property: "og:image",
        content: siteConfig.ogImageUrl,
      },
      {
        property: "og:image:secure_url",
        content: siteConfig.ogImageUrl,
      },
      {
        property: "og:image:type",
        content: "image/jpeg",
      },
      {
        property: "og:image:alt",
        content: siteConfig.ogImageAlt,
      },
      {
        name: "twitter:card",
        content: "summary_large_image",
      },
      {
        name: "twitter:title",
        content: siteConfig.title,
      },
      {
        name: "twitter:description",
        content: siteConfig.description,
      },
      {
        name: "twitter:image",
        content: siteConfig.ogImageUrl,
      },
      {
        name: "twitter:image:alt",
        content: siteConfig.ogImageAlt,
      },
      {
        "script:ld+json": websiteStructuredData,
      },
      {
        "script:ld+json": organizationStructuredData,
      },
    ],
    links: [
      {
        rel: "canonical",
        href: siteConfig.homeUrl,
      },
    ],
  }),
  component: HomePage,
});

export function HomePage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Nav />
      <main>
        <Hero />
        <Features />
        <TrustPipeline />
        <HowItWorks />
        <ApiShowcase />
        <CtaSection />
      </main>
      <Footer />
    </div>
  );
}
