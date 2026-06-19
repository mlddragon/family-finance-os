import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

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

test("saves a classification decision from the review panel", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        transactions: [
          {
            id: "tx-1",
            raw_description: "SYNTHETIC GROCERY",
            amount: "12.34",
            category_current: "Food",
            review_status: "unreviewed",
            validation_status: "ready_for_review",
          },
        ],
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        event: { id: "event-1" },
        current_state: { category_current: "Groceries" },
      }),
    });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect((await screen.findAllByText("SYNTHETIC GROCERY")).length).toBeGreaterThan(0);
  fireEvent.change(screen.getByLabelText("Approved category"), {
    target: { value: "Groceries" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/decision-events",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });
  expect(await screen.findByText("Decision saved")).toBeInTheDocument();
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
    target_type: "canonical_transaction",
    target_id: "tx-1",
    decision_type: "category_change",
    field_name: "category",
    approved_value: "Groceries",
    explicit_user_action: true,
  });
});
