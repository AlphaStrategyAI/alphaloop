import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MetricNumber } from "../components/MetricNumber";

describe("MetricNumber", () => {
  it("renders the metric with 3 decimal places after rollup", async () => {
    render(<MetricNumber value={0.873} />);
    const el = await screen.findByTestId("metric-number");
    expect(el).toBeInTheDocument();
    await waitFor(
      () => {
        expect(el.textContent).toMatch(/0\.873/);
      },
      { timeout: 2000 },
    );
  });

  it("honors custom decimals", () => {
    render(<MetricNumber value={0.12345} decimals={2} />);
    const el = screen.getByTestId("metric-number");
    expect(el.textContent).toMatch(/0\.12/);
  });

  it("renders prefix and suffix", () => {
    render(<MetricNumber value={1.5} prefix="~" suffix=" USD" />);
    const el = screen.getByTestId("metric-number");
    expect(el.textContent).toContain("~");
    expect(el.textContent).toContain("USD");
  });

  it("renders with custom className", () => {
    render(<MetricNumber value={0.5} className="text-2xl" />);
    const el = screen.getByTestId("metric-number");
    expect(el.className).toContain("text-2xl");
  });

  it("supports different color props", () => {
    render(<MetricNumber value={0.5} color="stats" />);
    const el = screen.getByTestId("metric-number");
    expect(el.style.color).toBe("var(--color-stats)");
  });
});
