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

class ToastManager {
  private toasts: ToastProps[] = [];
  private listeners: Set<(toasts: ToastProps[]) => void> = new Set();
  
  public subscribe = (listener: (toasts: ToastProps[]) => void) => {
    this.listeners.add(listener);
    // Initial sync
    listener([...this.toasts]);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private broadcast = () => {
    this.listeners.forEach((listener) => listener([...this.toasts]));
  };

  public toast = (input: ToastInput) => {
    const id = Math.random().toString(36).substring(2, 9);
    const duration = input.duration ?? 5000;
    
    const newToast = { ...input, id, type: input.type || "info", duration };
    this.toasts = [...this.toasts, newToast];
    this.broadcast();

    if (duration > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, duration);
    }
    
    return id;
  };

  public dismiss = (id: string) => {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this.broadcast();
  };

  public clear = () => {
    this.toasts = [];
    this.broadcast();
  };
}

export const toastManager = new ToastManager();

export const toast = (input: ToastInput | string) => {
  if (typeof input === "string") {
    return toastManager.toast({ description: input, type: "info" });
  }
  return toastManager.toast(input);
};

export const useToast = () => {
  const [toasts, setToasts] = useState<ToastProps[]>([]);

  useEffect(() => {
    return toastManager.subscribe(setToasts);
  }, []);

  const dismissToast = useCallback((id: string) => {
    toastManager.dismiss(id);
  }, []);

  return { toasts, toast, dismiss: dismissToast };
};
