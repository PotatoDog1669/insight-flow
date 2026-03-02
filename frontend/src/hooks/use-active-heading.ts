"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export function useActiveHeading(ids: string[]): string | null {
  const idsKey = useMemo(() => Array.from(new Set(ids.filter(Boolean))).join("|"), [ids]);
  const stableIds = useMemo(() => (idsKey ? idsKey.split("|") : []), [idsKey]);
  const [activeId, setActiveId] = useState<string | null>(stableIds[0] ?? null);
  const visibleByIdRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    if (stableIds.length === 0) return;
    if (typeof window === "undefined") return;
    if (!("IntersectionObserver" in window)) return;

    visibleByIdRef.current.clear();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.id;
          if (!id) continue;
          if (entry.isIntersecting) {
            visibleByIdRef.current.set(id, entry.boundingClientRect.top);
          } else {
            visibleByIdRef.current.delete(id);
          }
        }

        const visible = Array.from(visibleByIdRef.current.entries()).sort((a, b) => a[1] - b[1]);
        const next = visible[0]?.[0] ?? null;
        if (!next) return;
        setActiveId((prev) => (prev === next ? prev : next));
      },
      {
        rootMargin: "-20% 0px -65% 0px",
        threshold: [0, 1],
      }
    );

    stableIds.forEach((id) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });

    return () => {
      observer.disconnect();
    };
  }, [idsKey, stableIds]);

  if (!activeId || !stableIds.includes(activeId)) {
    return stableIds[0] ?? null;
  }
  return activeId;
}
