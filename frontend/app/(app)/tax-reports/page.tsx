"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function TaxReportsRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/tax-documents"); }, [router]);
  return null;
}
