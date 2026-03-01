"use client";

import { useState } from "react";
import { Play, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TriggerButtonProps {
    sourceId: string;
}

export function TriggerButton({ sourceId: _sourceId }: TriggerButtonProps) {
    void _sourceId;
    const [status, setStatus] = useState<"idle" | "loading" | "success">("idle");

    const handleTrigger = async () => {
        setStatus("loading");
        // Simulate delay
        setTimeout(() => {
            setStatus("success");
            setTimeout(() => setStatus("idle"), 2000);
        }, 1500);
    };

    return (
        <Button
            variant="secondary"
            size="sm"
            onClick={handleTrigger}
            disabled={status !== "idle"}
            className="w-24 mt-2 h-8 text-xs font-semibold"
        >
            {status === "idle" && <><Play className="w-3 h-3 mr-1" /> Run</>}
            {status === "loading" && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
            {status === "success" && <><CheckCircle2 className="w-3 h-3 mr-1 text-green-600 dark:text-green-400" /> Done</>}
        </Button>
    );
}
