import type { QueryApiResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5001";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function queryApi(
  question: string,
  sessionId?: string,
): Promise<QueryApiResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
  } catch (e) {
    throw new ApiError(
      e instanceof Error ? e.message : "network request failed",
    );
  }

  if (!response.ok) {
    throw new ApiError(`HTTP ${response.status}`);
  }

  return (await response.json()) as QueryApiResponse;
}
