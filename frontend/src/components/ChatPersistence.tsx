"use client";

/**
 * ChatPersistence: saves and restores CopilotKit chat messages to PostgreSQL.
 *
 * Render this component inside the CopilotKit provider tree (it renders nothing).
 * - When activeConversationId changes, loads messages from DB and calls setMessages().
 * - When messages change, saves new ones to DB via addMessageApi().
 * - Auto-creates a conversation on the first user message if none is selected.
 * - Auto-titles the conversation from the first user message.
 */

import { useEffect, useRef, useCallback } from "react";
import { useCopilotMessagesContext } from "@copilotkit/react-core";
import {
  TextMessage,
  MessageStatusCode,
  MessageRole,
} from "@copilotkit/runtime-client-gql";
import {
  fetchMessages,
  addMessageApi,
  createConversationApi,
  updateConversationTitle,
} from "@/lib/api";

const DEBOUNCE_MS = 600;

interface ChatPersistenceProps {
  /** Currently active conversation ID (null = new/unsaved chat). */
  activeConversationId: string | null;
  /** Called when a new conversation is auto-created. */
  onConversationCreated: (id: string) => void;
  /** Called after messages are saved to trigger sidebar refresh. */
  onMessagesChanged: () => void;
}

export function ChatPersistence({
  activeConversationId,
  onConversationCreated,
  onMessagesChanged,
}: ChatPersistenceProps) {
  const { messages, setMessages } = useCopilotMessagesContext();

  // Track which message IDs have already been persisted to avoid duplicates
  const savedIdsRef = useRef<Set<string>>(new Set());
  // Prevent save during load
  const loadingRef = useRef(false);
  // Timer for debounced save
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track the conversation ID we're currently working with
  const convIdRef = useRef<string | null>(activeConversationId);
  // Track if auto-title has been set for this conversation
  const titledRef = useRef(false);

  // Keep convIdRef in sync
  useEffect(() => {
    convIdRef.current = activeConversationId;
  }, [activeConversationId]);

  // ── Load messages when conversation changes ─────────────────────
  useEffect(() => {
    if (!activeConversationId) {
      // New chat: clear messages
      loadingRef.current = true;
      savedIdsRef.current = new Set();
      titledRef.current = false;
      setMessages([]);
      // Use a microtask to reset loading flag after React processes the state update
      queueMicrotask(() => {
        loadingRef.current = false;
      });
      return;
    }

    let cancelled = false;
    loadingRef.current = true;
    savedIdsRef.current = new Set();
    titledRef.current = false;

    (async () => {
      try {
        const dbMessages = await fetchMessages(activeConversationId);
        if (cancelled) return;

        // Convert DB messages to CopilotKit TextMessage instances
        const copilotMessages = dbMessages
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map(
            (m) =>
              new TextMessage({
                id: m.id,
                role:
                  m.role === "user" ? MessageRole.User : MessageRole.Assistant,
                content: m.content,
                createdAt: new Date(m.created_at),
                status: { code: MessageStatusCode.Success },
              })
          );

        // Mark all loaded messages as already saved
        for (const m of copilotMessages) {
          savedIdsRef.current.add(m.id);
        }
        // Check if conversation already has a title
        titledRef.current = dbMessages.length > 0;

        setMessages(copilotMessages);
      } catch {
        // Failed to load — start with empty chat
      } finally {
        if (!cancelled) {
          // Delay resetting loading flag to avoid immediate save trigger
          setTimeout(() => {
            loadingRef.current = false;
          }, 100);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeConversationId, setMessages]);

  // ── Save new messages to DB ─────────────────────────────────────
  const saveNewMessages = useCallback(async () => {
    if (loadingRef.current) return;

    // Find TextMessages that haven't been saved yet
    const unsaved = messages.filter(
      (m) =>
        m.isTextMessage() &&
        m.id &&
        !savedIdsRef.current.has(m.id) &&
        (m.role === MessageRole.User || m.role === MessageRole.Assistant) &&
        m.content.length > 0
    );

    if (unsaved.length === 0) return;

    let conversationId = convIdRef.current;

    // Auto-create conversation if needed
    if (!conversationId) {
      try {
        const conv = await createConversationApi();
        conversationId = conv.id;
        convIdRef.current = conversationId;
        onConversationCreated(conversationId);
      } catch {
        return; // Can't save without a conversation
      }
    }

    // Save each unsaved message
    for (const msg of unsaved) {
      if (!msg.isTextMessage()) continue;
      const role = msg.role === MessageRole.User ? "user" : "assistant";
      try {
        await addMessageApi(conversationId, role, msg.content);
        savedIdsRef.current.add(msg.id);
      } catch {
        // Failed to save this message — will retry on next change
        break;
      }
    }

    // Auto-title from first user message
    if (!titledRef.current && conversationId) {
      const firstUser = messages.find(
        (m) =>
          m.isTextMessage() &&
          m.role === MessageRole.User &&
          m.content.length > 0
      );
      if (firstUser && firstUser.isTextMessage()) {
        const content = firstUser.content;
        const title =
          content.length > 60 ? content.slice(0, 57) + "..." : content;
        try {
          await updateConversationTitle(conversationId, title);
          titledRef.current = true;
        } catch {
          // Non-critical
        }
      }
    }

    onMessagesChanged();
  }, [messages, onConversationCreated, onMessagesChanged]);

  // Debounced save effect
  const saveRef = useRef(saveNewMessages);
  useEffect(() => {
    saveRef.current = saveNewMessages;
  }, [saveNewMessages]);

  useEffect(() => {
    if (loadingRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void saveRef.current();
    }, DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [messages]);

  return null;
}
