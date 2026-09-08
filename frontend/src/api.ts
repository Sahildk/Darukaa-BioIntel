/**
 * API client module for Darukaa BioIntel backend communication.
 * Communicates through explicit HTTP contracts without client-side reasoning.
 */

import {
  ChatRequest,
  ChatResponse,
  DemoScenario,
  EnvironmentalState,
  HealthStatus,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

export class ApiError extends Error {
  public statusCode: number;
  public details?: unknown;

  constructor(message: string, statusCode: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.details = details;
  }
}

/**
 * Sends a chat message with optional structured data to POST /api/chat.
 */
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      if (response.status >= 500) {
        throw new ApiError(
          "The ecological assessment service is temporarily unavailable.",
          response.status
        );
      }

      let errorDetail = "Invalid request or validation failure.";
      try {
        const errorJson = await response.json();
        if (typeof errorJson.detail === "string") {
          errorDetail = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail
            .map((e: { loc?: string[]; msg?: string }) => `${e.loc?.join(".") || "field"}: ${e.msg || "invalid"}`)
            .join("; ");
        }
      } catch {
        // use default error detail
      }
      throw new ApiError(errorDetail, response.status);
    }

    const data: ChatResponse = await response.json();
    return data;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    // Network failure or connection refused
    throw new ApiError(
      "Unable to connect to Darukaa BioIntel backend. Please ensure the server is running on port 8000.",
      0
    );
  }
}

/**
 * Retrieves the consolidated environmental state from GET /api/conversations/{id}.
 */
export async function fetchConversationState(
  conversationId: string
): Promise<EnvironmentalState> {
  try {
    const response = await fetch(`${API_BASE}/conversations/${encodeURIComponent(conversationId)}`);
    if (!response.ok) {
      throw new ApiError("Failed to fetch conversation state.", response.status);
    }
    return await response.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Network error while retrieving environmental state.", 0);
  }
}

/**
 * Inspects system health and readiness from GET /api/health.
 */
export async function fetchHealthStatus(): Promise<HealthStatus> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) {
      throw new ApiError("Health check failed.", response.status);
    }
    return await response.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Backend unreachable.", 0);
  }
}

/**
 * Retrieves canonical evaluator scenarios from GET /api/demo/scenarios.
 */
export async function fetchDemoScenarios(): Promise<DemoScenario[]> {
  try {
    const response = await fetch(`${API_BASE}/demo/scenarios`);
    if (!response.ok) {
      throw new ApiError("Failed to load demo scenarios.", response.status);
    }
    return await response.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Network error loading scenarios.", 0);
  }
}
