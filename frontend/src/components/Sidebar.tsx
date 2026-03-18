"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Telescope, Activity, Library, Globe, Menu, Settings, LogOut, User, Zap, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

const NAV_ITEMS = [
    { href: "/", label: "报告", icon: Telescope },
    { href: "/monitors", label: "任务", icon: Activity },
    { href: "/library", label: "归档", icon: Library },
    { href: "/sources", label: "信息源", icon: Globe },
    { href: "/providers", label: "模型配置", icon: Bot },
    { href: "/destinations", label: "输出配置", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

    // Mock auth state
    const [isLoggedIn, setIsLoggedIn] = useState(true);

    return (
        <>
            {/* Mobile top bar */}
            <div className="md:hidden flex items-center justify-between p-4 border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
                <div className="font-semibold tracking-tight text-lg flex items-center gap-2">
                    <div className="w-6 h-6 rounded-md bg-foreground flex items-center justify-center">
                        <span className="text-background text-xs font-bold leading-none">I</span>
                    </div>
                    Insight Flow
                </div>
                <button
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    className="p-2 text-muted-foreground hover:bg-muted rounded-md"
                >
                    <Menu className="w-5 h-5" />
                </button>
            </div>

            {/* Sidebar background overlay for mobile */}
            {isMobileMenuOpen && (
                <div
                    className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
                    onClick={() => setIsMobileMenuOpen(false)}
                />
            )}

            {/* Main Sidebar */}
            <aside className={cn(
                "fixed md:sticky top-0 left-0 z-50 w-64 h-screen border-r border-border/40 bg-background md:bg-transparent transition-transform duration-300 ease-in-out md:translate-x-0 flex flex-col",
                isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
            )}>
                <div className="flex flex-col h-full py-6 px-4 relative">

                    {/* Logo */}
                    <div className="hidden md:flex items-center gap-2 px-2 pb-8">
                        <div className="w-7 h-7 rounded-lg bg-foreground flex items-center justify-center shadow-sm">
                            <span className="text-background text-sm font-bold leading-none tracking-tighter">I</span>
                        </div>
                        <span className="font-semibold tracking-tight text-lg">Insight Flow</span>
                    </div>

                    {/* Navigation Links */}
                    <nav className="space-y-1 flex-1">
                        {NAV_ITEMS.map((item) => {
                            const Icon = item.icon;
                            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));

                            return (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    onClick={() => setIsMobileMenuOpen(false)}
                                    className={cn(
                                        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group",
                                        isActive
                                            ? "bg-secondary text-secondary-foreground"
                                            : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                                    )}
                                >
                                    <Icon className={cn(
                                        "w-4 h-4 transition-colors",
                                        isActive ? "text-foreground" : "text-muted-foreground group-hover:text-foreground"
                                    )} />
                                    {item.label}
                                </Link>
                            );
                        })}
                    </nav>

                    {/* User Settings Popover overlay (click outside to close) */}
                    {isUserMenuOpen && (
                        <div className="fixed inset-0 z-40" onClick={() => setIsUserMenuOpen(false)} />
                    )}

                    {/* User Menu Popover */}
                    <div className={cn(
                        "absolute bottom-20 left-4 right-4 bg-popover text-popover-foreground border border-border shadow-md rounded-xl p-1 z-50 transform transition-all duration-200 origin-bottom",
                        isUserMenuOpen ? "scale-100 opacity-100" : "scale-95 opacity-0 pointer-events-none"
                    )}>
                        {isLoggedIn ? (
                            <div className="space-y-1">
                                <div className="px-3 py-2 text-xs text-muted-foreground border-b border-border/50 mb-1">
                                    Signed in as <strong>admin@lexmount.com</strong>
                                </div>
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm text-foreground rounded-md hover:bg-muted transition-colors">
                                    <User className="w-4 h-4 text-muted-foreground" />
                                    Profile
                                </button>
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm text-foreground rounded-md hover:bg-muted transition-colors">
                                    <Zap className="w-4 h-4 text-orange-500" />
                                    API Keys & Quota
                                </button>
                                <button className="w-full flex items-center gap-3 px-3 py-2 text-sm text-foreground rounded-md hover:bg-muted transition-colors">
                                    <Settings className="w-4 h-4 text-muted-foreground" />
                                    Global Settings
                                </button>
                                <div className="h-px bg-border/50 my-1" />
                                <button
                                    onClick={() => {
                                        setIsLoggedIn(false);
                                        setIsUserMenuOpen(false);
                                    }}
                                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                                >
                                    <LogOut className="w-4 h-4" />
                                    Sign out
                                </button>
                            </div>
                        ) : (
                            <div className="p-3 text-center space-y-3">
                                <p className="text-sm font-medium">Access your personal monitors.</p>
                                <button
                                    onClick={() => {
                                        setIsLoggedIn(true);
                                        setIsUserMenuOpen(false);
                                    }}
                                    className="w-full bg-foreground text-background hover:bg-foreground/90 py-2 rounded-md text-sm font-medium transition-colors"
                                >
                                    Log In
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Bottom Identity / Settings trigger */}
                    <div className="mt-auto pt-4 border-t border-border/40 relative z-30">
                        {isLoggedIn ? (
                            <button
                                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                                className="w-full flex items-center gap-3 py-2 px-3 hover:bg-muted/60 hover:shadow-[0_2px_10px_rgba(0,0,0,0.04)] active:scale-[0.98] rounded-xl transition-all duration-200 text-left group border border-transparent hover:border-border/60"
                            >
                                <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900 border border-blue-200 dark:border-blue-800 flex items-center justify-center shrink-0 group-hover:scale-105 group-hover:shadow-sm transition-all duration-200">
                                    <User className="w-4 h-4 text-blue-700 dark:text-blue-300 group-hover:text-blue-800 dark:group-hover:text-blue-200 transition-colors" />
                                </div>
                                <div className="flex-1 overflow-hidden transition-transform duration-200 group-hover:translate-x-0.5">
                                    <p className="font-semibold text-sm text-foreground truncate transition-colors group-hover:text-blue-600 dark:group-hover:text-blue-400">Lex Researcher</p>
                                    <p className="text-xs text-muted-foreground truncate">Free Plan</p>
                                </div>
                            </button>
                        ) : (
                            <button
                                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                                className="w-full flex items-center gap-3 py-2 px-2 hover:bg-secondary/60 rounded-lg transition-colors text-left"
                            >
                                <div className="w-8 h-8 rounded-full bg-muted border border-border/50 flex items-center justify-center shrink-0">
                                    <User className="w-4 h-4 text-muted-foreground" />
                                </div>
                                <div className="flex-1 overflow-hidden">
                                    <p className="font-medium text-sm text-foreground truncate">Guest Account</p>
                                    <p className="text-xs text-muted-foreground truncate">Sign in to save tasks</p>
                                </div>
                            </button>
                        )}
                    </div>

                </div>
            </aside>
        </>
    );
}
