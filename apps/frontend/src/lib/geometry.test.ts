import { describe, expect, it } from "vitest";

import {
  dedupeConsecutive,
  formatArea,
  parseNumber,
  rectangleFromCorners,
  wrapLon,
} from "./geometry";

describe("geometry helpers", () => {
  it("normalises rectangle corners regardless of click order", () => {
    expect(rectangleFromCorners([10.2, 0.3], [10.0, 0.1])).toEqual({
      west: 10.0,
      south: 0.1,
      east: 10.2,
      north: 0.3,
    });
  });

  it.each([
    ["12.5", 12.5],
    [" -3,25 ", -3.25],
    ["1e2", 100],
    [".5", 0.5],
  ])("parses %j", (text, n) => expect(parseNumber(text)).toBe(n));

  it.each(["", "abc", "1.2.3", "NaN", "Infinity", "12abc", "--1"])("rejects %j", (text) =>
    expect(parseNumber(text)).toBeNull(),
  );

  it("wraps longitudes", () => {
    expect(wrapLon(190)).toBe(-170);
    expect(wrapLon(-190)).toBe(170);
    expect(wrapLon(45)).toBe(45);
  });

  it("formats areas", () => {
    expect(formatArea(0.0123)).toBe("0.012 km²");
    expect(formatArea(2.345)).toBe("2.35 km²");
    expect(formatArea(24.96)).toBe("25.0 km²");
  });

  it("removes consecutive duplicate vertices only", () => {
    expect(
      dedupeConsecutive([
        [1, 1],
        [1, 1],
        [2, 2],
        [1, 1],
      ]),
    ).toEqual([
      [1, 1],
      [2, 2],
      [1, 1],
    ]);
  });
});
