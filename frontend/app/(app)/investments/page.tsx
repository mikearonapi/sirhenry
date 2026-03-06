"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function InvestmentsRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/portfolio"); }, [router]);
  return null;
}
