import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import HoursBanner from "./HoursBanner";

describe("HoursBanner", () => {
  it("shows live-hours notice", () => {
    render(<HoursBanner />);
    expect(
      screen.getByText(/live daily from 7:00 AM to 9:00 PM Eastern Time/i),
    ).toBeTruthy();
  });
});
