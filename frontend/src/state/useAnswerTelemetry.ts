import { useCallback, useEffect, useRef } from "react";

export interface AnswerTelemetry {
  pasted_chars: number;
  paste_events: number;
  voice_chars: number;
  keystrokes: number;
  active_typing_ms: number | null;
  focus_losses: number;
}

const IDLE_GAP_MS = 4000; // pauses longer than this are thinking time, not typing time

/**
 * Collects lightweight, non-invasive signals while a candidate answers:
 * paste volume, keystrokes, active typing time and how often the window
 * lost focus. Nothing is recorded about *what* was typed beyond the answer itself.
 */
export function useAnswerTelemetry() {
  const data = useRef<AnswerTelemetry>({
    pasted_chars: 0,
    paste_events: 0,
    voice_chars: 0,
    keystrokes: 0,
    active_typing_ms: 0,
    focus_losses: 0,
  });
  const lastKey = useRef<number | null>(null);

  useEffect(() => {
    const onBlur = () => {
      data.current.focus_losses += 1;
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") data.current.focus_losses += 1;
    };
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const onKeyDown = useCallback(() => {
    const now = performance.now();
    data.current.keystrokes += 1;
    if (lastKey.current != null) {
      const gap = now - lastKey.current;
      if (gap < IDLE_GAP_MS) data.current.active_typing_ms = (data.current.active_typing_ms ?? 0) + gap;
    }
    lastKey.current = now;
  }, []);

  const onPaste = useCallback((e: React.ClipboardEvent) => {
    data.current.paste_events += 1;
    data.current.pasted_chars += e.clipboardData.getData("text").length;
  }, []);

  const addVoice = useCallback((chars: number) => {
    data.current.voice_chars += chars;
  }, []);

  const snapshot = useCallback((): AnswerTelemetry => {
    const d = data.current;
    return { ...d, active_typing_ms: d.keystrokes > 5 ? Math.round(d.active_typing_ms ?? 0) : null };
  }, []);

  return { onKeyDown, onPaste, addVoice, snapshot };
}
