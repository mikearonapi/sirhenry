"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function TaxRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/tax-documents"); }, [router]);
  return null;
}
