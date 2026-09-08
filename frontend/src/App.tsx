import React, { useState } from "react";
import { Header } from "./components/Header";
import { ConversationPane } from "./components/ConversationPane";
import { EnvironmentalProfile } from "./components/EnvironmentalProfile";
import { sendChatMessage } from "./api";
import {
  ChatRequest,
  ConversationTurn,
  EnvironmentalState,
  StructuredInput,
} from "./types";
import "./styles.css";

export const App: React.FC = () => {
  const [conversationId, setConversationId] = useState<string>(() => `conv-${Date.now().toString(36)}`);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [environmentalState, setEnvironmentalState] = useState<EnvironmentalState | null>(null);

  const [inputMessage, setInputMessage] = useState<string>("");
  const [structuredInput, setStructuredInput] = useState<StructuredInput>({});
  const [showStructuredDrawer, setShowStructuredDrawer] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const handleResetSession = () => {
    setConversationId(`conv-${Date.now().toString(36)}`);
    setTurns([]);
    setEnvironmentalState(null);
    setInputMessage("");
    setStructuredInput({});
    setShowStructuredDrawer(false);
    setErrorBanner(null);
  };

  const executeChatRequest = async (request: ChatRequest) => {
    if (isLoading) return;

    setIsLoading(true);
    setErrorBanner(null);

    // Append user message to stream
    const userTurn: ConversationTurn = {
      id: `turn-user-${Date.now()}`,
      sender: "user",
      timestamp: new Date().toISOString(),
      request,
    };
    setTurns((prev) => [...prev, userTurn]);

    try {
      const response = await sendChatMessage(request);

      // Backend is authoritative: update session ID and state directly from response
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }
      if (response.environmental_state) {
        setEnvironmentalState(response.environmental_state);
      }

      // Append assistant response to stream
      const assistantTurn: ConversationTurn = {
        id: `turn-assistant-${Date.now()}`,
        sender: "assistant",
        timestamp: new Date().toISOString(),
        response,
      };
      setTurns((prev) => [...prev, assistantTurn]);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "An unexpected communication error occurred.";
      setErrorBanner(errorMsg);
      // Notice: conversation history and current environmental state remain completely intact
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = () => {
    if (!inputMessage.trim() && Object.keys(structuredInput).length === 0) return;

    // Filter out empty structured values
    const cleanStructured: StructuredInput = {};
    let hasStructured = false;
    for (const [k, v] of Object.entries(structuredInput)) {
      if (v !== null && v !== undefined && v !== "") {
        (cleanStructured as Record<string, unknown>)[k] = v;
        hasStructured = true;
      }
    }

    const payload: ChatRequest = {
      conversation_id: conversationId,
      message: inputMessage.trim() || "Environmental assessment request with structured parameters.",
      structured_input: hasStructured ? cleanStructured : null,
    };

    setInputMessage("");
    executeChatRequest(payload);
  };

  const handleSelectScenario = (sampleRequest: ChatRequest) => {
    // Populate form fields for transparency and execute query through live backend
    setInputMessage(sampleRequest.message);
    if (sampleRequest.structured_input) {
      setStructuredInput(sampleRequest.structured_input);
      setShowStructuredDrawer(true);
    } else {
      setStructuredInput({});
      setShowStructuredDrawer(false);
    }

    executeChatRequest({
      ...sampleRequest,
      conversation_id: conversationId,
    });
  };

  return (
    <div className="app-container">
      <Header onSelectScenario={handleSelectScenario} isLoading={isLoading} />

      <main className="main-workspace">
        <ConversationPane
          turns={turns}
          inputMessage={inputMessage}
          setInputMessage={setInputMessage}
          structuredInput={structuredInput}
          setStructuredInput={setStructuredInput}
          showStructuredDrawer={showStructuredDrawer}
          setShowStructuredDrawer={setShowStructuredDrawer}
          isLoading={isLoading}
          errorBanner={errorBanner}
          onDismissError={() => setErrorBanner(null)}
          onSendMessage={handleSendMessage}
          onResetSession={handleResetSession}
        />

        <EnvironmentalProfile
          state={environmentalState}
          conversationId={conversationId}
          onResetSession={handleResetSession}
        />
      </main>
    </div>
  );
};
