import { describe, expect, it } from "vitest";
import { toFieldErrors } from "../forms/to-field-errors";

describe("toFieldErrors", () => {
  it("normalizes supported error shapes and drops invalid ones", () => {
    const result = toFieldErrors([
      "plain error",
      new Error("exception"),
      { message: "object message" },
      { message: 123 },
      null,
      undefined,
      "",
      { message: "" },
      { foo: "bar" },
    ]);

    expect(result).toEqual([
      { message: "plain error" },
      { message: "exception" },
      { message: "object message" },
    ]);
  });

  it("returns empty list for missing errors", () => {
    expect(toFieldErrors(undefined)).toEqual([]);
  });
});
