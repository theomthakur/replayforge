import { fireEvent, render, screen } from "@testing-library/react";

import { Presentation } from "../src/features/explain/Presentation";
import { SystemDesign } from "../src/features/explain/SystemDesign";

describe("judge-facing explainers", () => {
  it("moves through the presentation with the keyboard", () => {
    render(<Presentation />);
    expect(screen.getByText(/Will it survive a model migration/)).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText(/Static benchmarks miss/)).toBeInTheDocument();
  });

  it("shows authority and failure boundaries in system design", () => {
    render(<SystemDesign />);
    expect(screen.getByRole("heading", { name: "System design" })).toBeInTheDocument();
    expect(screen.getByText("Deterministic evidence")).toBeInTheDocument();
    expect(screen.getByText("Unknown fixture or model")).toBeInTheDocument();
  });
});
