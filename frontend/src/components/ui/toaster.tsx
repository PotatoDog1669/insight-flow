"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-3 w-full max-w-[360px] pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((t) => {
          const type = t.type || "info";
          const Icon = {
            success: CheckCircle2,
            error: AlertCircle,
            info: Info,
            warning: AlertTriangle,
          }[type];

          const styleVariants = {
            success: "bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400 dark:bg-emerald-500/10 dark:border-emerald-500/30",
            error: "bg-rose-500/10 border-rose-500/20 text-rose-600 dark:text-rose-400 dark:bg-rose-500/10 dark:border-rose-500/30",
            info: "bg-blue-500/10 border-blue-500/20 text-blue-600 dark:text-blue-400 dark:bg-blue-500/10 dark:border-blue-500/30",
            warning: "bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400 dark:bg-amber-500/10 dark:border-amber-500/30",
          }[type];

          return (
            <motion.div
              layout
              key={t.id}
              initial={{ opacity: 0, y: 30, scale: 0.9, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, scale: 0.9, filter: "blur(4px)" }}
              transition={{ type: "spring", stiffness: 350, damping: 25 }}
              className={`pointer-events-auto rounded-xl border shadow-2xl backdrop-blur-xl ${styleVariants} overflow-hidden`}
            >
              <div className="flex items-start gap-4 p-4 bg-background/60 dark:bg-background/40">
                <Icon className={`w-5 h-5 shrink-0 mt-0.5`} />
                <div className="flex-1 space-y-1 mt-0.5">
                  {t.title && <p className="font-semibold text-sm leading-none text-foreground">{t.title}</p>}
                  {t.description && <div className="text-[13px] leading-relaxed text-foreground/80">{t.description}</div>}
                </div>
                <button 
                  onClick={() => dismiss(t.id)}
                  className="shrink-0 text-foreground/40 hover:text-foreground/80 transition-colors p-1 -m-1 rounded-md hover:bg-foreground/5 cursor-pointer"
                  aria-label="Dismiss notification"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
