import BusinessDetailPage from "./BusinessDetail";

export function generateStaticParams() {
  return [{ id: "_" }];
}

export default function Page() {
  return <BusinessDetailPage />;
}
