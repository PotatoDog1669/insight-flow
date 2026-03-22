import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

import { toastManager } from "@/hooks/use-toast";

afterEach(() => {
  cleanup();
  toastManager.clear();
});
