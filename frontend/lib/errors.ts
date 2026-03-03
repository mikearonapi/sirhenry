/**
 * Shared error handling utilities.
 * Use `getErrorMessage(e)` in catch blocks instead of `(e: any) => e.message`.
 */

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "An unexpected error occurred";
}
