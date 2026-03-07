import {
  HeroSection,
  HenryParadoxSection,
  ProblemsSection,
  FeatureShowcaseSection,
  ComparisonTable,
  VoicesSection,
  WaitlistSection,
  Footer,
} from "@/components/landing";

export default function LandingPage() {
  return (
    <div className="min-h-screen font-sans bg-card">
      <HeroSection />
      <HenryParadoxSection />
      <ProblemsSection />
      <FeatureShowcaseSection />
      <ComparisonTable />
      <VoicesSection />
      <WaitlistSection />
      <Footer />
    </div>
  );
}
