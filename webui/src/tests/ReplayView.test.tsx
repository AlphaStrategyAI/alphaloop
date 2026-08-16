import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ReplayView from "../views/ReplayView";
import { mockReplay } from "./handlers";

vi.mock("../api/client", () => ({
  apiClient: {
    getReplay: vi.fn(() => Promise.resolve(mockReplay)),
  },
}));

describe("ReplayView", () => {
  it("renders the title", async () => {
    render(
      <MemoryRouter initialEntries={["/replay/test-rid"]}>
        <Routes>
          <Route path="/replay/:rid" element={<ReplayView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Replay/)).toBeInTheDocument();
    });
  });

  it("renders the Play button", async () => {
    render(
      <MemoryRouter initialEntries={["/replay/test-rid"]}>
        <Routes>
          <Route path="/replay/:rid" element={<ReplayView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("play-btn")).toBeInTheDocument();
    });
  });

  it("renders the progress bar", async () => {
    render(
      <MemoryRouter initialEntries={["/replay/test-rid"]}>
        <Routes>
          <Route path="/replay/:rid" element={<ReplayView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("progress-bar")).toBeInTheDocument();
    });
  });

  it("renders the DAG with 6 nodes", async () => {
    render(
      <MemoryRouter initialEntries={["/replay/test-rid"]}>
        <Routes>
          <Route path="/replay/:rid" element={<ReplayView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("dag-graph")).toBeInTheDocument();
    });
    expect(screen.getByTestId("dag-node-n1_load_data")).toBeInTheDocument();
    expect(screen.getByTestId("dag-node-n3_execute")).toBeInTheDocument();
    expect(screen.getByTestId("dag-node-n6_commit")).toBeInTheDocument();
  });

  it("renders the timing section", async () => {
    render(
      <MemoryRouter initialEntries={["/replay/test-rid"]}>
        <Routes>
          <Route path="/replay/:rid" element={<ReplayView />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Timing/)).toBeInTheDocument();
    });
  });
});
