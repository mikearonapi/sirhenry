import type { BenchmarkData, FOOStep } from "@/types/api";
import { request } from "./api-client";

export function getBenchmarkSnapshot(): Promise<BenchmarkData> {
  return request("/benchmarks/snapshot");
}

export function getOrderOfOperations(): Promise<FOOStep[]> {
  return request("/benchmarks/order-of-operations");
}
