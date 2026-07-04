import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ResearchForm from "./ResearchForm";

describe("ResearchForm", () => {
  it("submits trimmed values and omits empty optionals", () => {
    const onSubmit = vi.fn();
    render(<ResearchForm onSubmit={onSubmit} busy={false} />);

    fireEvent.change(screen.getByLabelText(/Company name/), {
      target: { value: "  Acme Robotics  " },
    });
    fireEvent.change(screen.getByLabelText(/Ticker/), { target: { value: "ACME" } });
    fireEvent.click(screen.getByRole("button", { name: "Research" }));

    expect(onSubmit).toHaveBeenCalledWith({
      company: "Acme Robotics",
      website: undefined,
      ticker: "ACME",
    });
  });

  it("disables submission while a job is running", () => {
    const onSubmit = vi.fn();
    render(<ResearchForm onSubmit={onSubmit} busy={true} />);

    const button = screen.getByRole("button", { name: "Researching…" });

    expect(button.hasAttribute("disabled")).toBe(true);
  });

  it("does not submit an empty company name", () => {
    const onSubmit = vi.fn();
    render(<ResearchForm onSubmit={onSubmit} busy={false} />);

    const button = screen.getByRole("button", { name: "Research" });

    expect(button.hasAttribute("disabled")).toBe(true);
  });
});
