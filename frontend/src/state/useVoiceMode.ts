import { useCallback, useEffect, useState } from "react";

const KEY = "screenrag:voice-mode";

/**
 * Voice interview mode: the interviewer reads each question aloud with the
 * browser's speech synthesis; the answer box can then start listening.
 */
export function useVoiceMode() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [enabled, setEnabled] = useState<boolean>(() => {
    try {
      return localStorage.getItem(KEY) === "1";
    } catch {
      return false;
    }
  });
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, enabled ? "1" : "0");
    } catch {
      /* ignore */
    }
    if (!enabled && supported) window.speechSynthesis.cancel();
  }, [enabled, supported]);

  useEffect(() => () => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);

  const speak = useCallback(
    (text: string, onEnd?: () => void) => {
      if (!supported) return;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-US";
      u.rate = 1.02;
      const voice = window.speechSynthesis
        .getVoices()
        .find((v) => v.lang.startsWith("en") && /natural|google|samantha|daniel/i.test(v.name));
      if (voice) u.voice = voice;
      u.onstart = () => setSpeaking(true);
      u.onend = () => {
        setSpeaking(false);
        onEnd?.();
      };
      u.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(u);
    },
    [supported],
  );

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [supported]);

  return { supported, enabled, setEnabled, speaking, speak, stop };
}
