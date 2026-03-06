import EntityExpensesPage from "./BusinessExpenses";

export function generateStaticParams() {
  return [{ id: "_" }];
}

export default function Page() {
  return <EntityExpensesPage />;
}
