import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "./App";

test("renders local-only Dillon Finances shell", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "Dillon Finances" })).toBeInTheDocument();
  expect(screen.getByText("Data: Local only")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Home" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sources" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Review" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Reports" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
});

test("renders settings tabs and source profile status", () => {
  render(<App />);

  expect(screen.getByText("DATA_ROOT: External mount required")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Data root" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Sources" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Thresholds" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Reports" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Privacy" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Future integrations" })).toBeInTheDocument();
  expect(screen.getByText("Alliant Checking")).toBeInTheDocument();
  expect(screen.getByText("Chase Prime Visa")).toBeInTheDocument();
});
