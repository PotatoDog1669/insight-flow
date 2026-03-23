"use client";

import { useState, useEffect, useCallback } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastProps {
  id: string;
  title?: string;
  description?: React.ReactNode;
  type?: ToastType;
  duration?: number;
}

type ToastInput = Omit<ToastProps, "id">;

const TOAST_EVENT_NAME = "insight_flow_toast_event";
const TOAST_DISMISS_EVENT_NAME = "insight_flow_toast_dismiss_event";

export const toast = (input: ToastInput | string) => {
  if (typeof window === "undefined") return "0";
  const id = Math.random().toString(36).substring(2, 9);
  const duration = typeof input === "object" ? (input.duration ?? 5000) : 5000;
  
  const payload: ToastProps = typeof input === "string" 
    ? { id, description: input, type: "info", duration }
    : { ...input, id, type: input.type || "info", duration };

  window.dispatchEvent(new CustomEvent(TOAST_EVENT_NAME, { detail: payload }));
  
  if (payload.duration! > 0) {
    setTimeout(() => {
      dismissToast(id);
    }, payload.duration);
  }
  return id;
};

export const dismissToast = (id: string) => {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(TOAST_DISMISS_EVENT_NAME, { detail: id }));
  }
};

export const useToast = () => {
  const [toasts, setToasts] = useState<ToastProps[]>([]);

  useEffect(() => {
    const handleAdd = (e: Event) => {
      const customEvent = e as CustomEvent<ToastProps>;
      setToasts((prev) => [...prev, customEvent.detail]);
    };
    
    const handleDismiss = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      setToasts((prev) => prev.filter((t) => t.id !== customEvent.detail));
    };

    window.addEventListener(TOAST_EVENT_NAME, handleAdd);
    window.addEventListener(TOAST_DISMISS_EVENT_NAME, handleDismiss);
    
    return () => {
      window.removeEventListener(TOAST_EVENT_NAME, handleAdd);
      window.removeEventListener(TOAST_DISMISS_EVENT_NAME, handleDismiss);
    };
  }, []);

  return { toasts, toast, dismiss: dismissToast };
};
