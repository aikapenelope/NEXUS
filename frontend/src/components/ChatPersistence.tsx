"use client";

/**
 * ChatPersistence: saves and restores CopilotKit chat messages to localStorage.
 *
 * Render this component inside the CopilotKit provider tree (it renders nothing).
 * On mount it restores any previously saved messages; on every change it
 * debounce-saves the current messages array to localStorage.
 */

import { useEffect, useRef, useCallback } from "react";
import { useCopilotMessagesContext } from "@copilotkit/react-core";

const STORAGE_KEY = "nexus-chat-messages";
const DEBOUNCE_MS = 500;

export function ChatPersistence() {
  const { messages, setMessages } = useCopilotMessagesContext();
  const restored = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Restore messages from localStorage on first mount
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;

    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (Array.isArray(saved) && saved.length > 0) {
          setMessages(saved);
        }
      }
    } catch {
      // Corrupted data — ignore and start fresh
    }
  }, [setMessages]);

  // Debounced save whenever messages change
  const saveMessages = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch {
        // Storage full or unavailable — silently fail
      }
    }, DEBOUNCE_MS);
  }, [messages]);

  useEffect(() => {
    // Skip saving during the initial restore cycle
    if (!restored.current) return;
    saveMessages();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [saveMessages]);

  // This component renders nothing — it's a side-effect-only hook wrapper
  return null;
}
