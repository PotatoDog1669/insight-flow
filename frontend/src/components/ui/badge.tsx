import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: "default" | "secondary" | "destructive" | "outline"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
    return (
        <div
            className={cn(
                "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                {
                    "border-transparent bg-foreground text-background shadow hover:bg-foreground/80": variant === "default",
                    "border-transparent bg-muted text-foreground hover:bg-muted/80": variant === "secondary",
                    "border-transparent bg-red-600 text-white hover:bg-red-600/80": variant === "destructive",
                    "text-foreground": variant === "outline",
                },
                className
            )}
            {...props}
        />
    )
}

export { Badge }
