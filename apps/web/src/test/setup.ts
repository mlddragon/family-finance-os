import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

function createLocalStorageMock() {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
}

Object.defineProperty(globalThis, "localStorage", {
  value: createLocalStorageMock(),
  configurable: true,
});

afterEach(() => {
  cleanup();
  globalThis.localStorage.clear();
});
