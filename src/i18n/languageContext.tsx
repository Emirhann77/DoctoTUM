"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_LANG = "careconnect_language";

const ALLOWED = ["en", "de", "tr", "es", "fr"] as const;
export type CareLocale = (typeof ALLOWED)[number];

type Value = {
  locale: CareLocale;
  setLocale: (locale: CareLocale) => void;
};

const LanguageReactContext = createContext<Value | null>(null);

function normalize(locale: string | null): CareLocale {
  const code = (locale || "en").toLowerCase().split("-")[0];
  return (ALLOWED as readonly string[]).includes(code)
    ? (code as CareLocale)
    : "en";
}

/**
 * Syncs Next.js surfaces with static CareConnect prefs (`careconnect_language` localStorage).
 * Opt-in — wrap layouts only where needed.
 */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<CareLocale>("en");

  useEffect(() => {
    setLocaleState(normalize(localStorage.getItem(STORAGE_LANG)));
  }, []);

  const setLocale = useCallback((next: CareLocale) => {
    localStorage.setItem(STORAGE_LANG, next);
    if (typeof document !== "undefined") document.documentElement.lang = next;
    setLocaleState(next);
    window.dispatchEvent(new CustomEvent("careconnect:locale", { detail: { locale: next } }));
  }, []);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);

  return (
    <LanguageReactContext.Provider value={value}>{children}</LanguageReactContext.Provider>
  );
}

export function useLanguageContext(): Value {
  const ctx = useContext(LanguageReactContext);
  if (!ctx)
    throw new Error("useLanguageContext must be used inside LanguageProvider");
  return ctx;
}
