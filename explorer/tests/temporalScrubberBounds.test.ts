import test from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_MIN_DATE,
  resolvePlayStepMs,
  resolveScrubberBounds,
} from "../src/workspaces/GraphWorkspace/temporalScrubberBounds.ts";

const NOW = new Date("2026-09-09T10:30:00Z");

// ── resolveScrubberBounds ────────────────────────────────────────────────────

test("scrubber bounds: open max ends the window at now, not at a future year", () => {
  const { minBound, maxBound } = resolveScrubberBounds({ minDate: "2026-01-15T00:00:00Z", now: NOW });

  assert.equal(minBound.toISOString(), "2026-01-15T00:00:00.000Z");
  assert.equal(
    maxBound.getTime(),
    NOW.getTime(),
    "a graph carrying only valid_from instants is known up to the present and no further",
  );
});

test("scrubber bounds: playhead starts at now so the first snapshot describes the present", () => {
  const { defaultTime } = resolveScrubberBounds({ minDate: "2026-01-15T00:00:00Z", now: NOW });

  assert.equal(defaultTime.getTime(), NOW.getTime());
});

test("scrubber bounds: playhead is not the midpoint of the range", () => {
  const { minBound, maxBound, defaultTime } = resolveScrubberBounds({
    minDate: "2020-01-01T00:00:00Z",
    maxDate: "2030-01-01T00:00:00Z",
    now: NOW,
  });
  const midpoint = Math.round((minBound.getTime() + maxBound.getTime()) / 2);

  assert.notEqual(defaultTime.getTime(), midpoint, "the midpoint was the source of the future start time");
  assert.equal(defaultTime.getTime(), NOW.getTime());
});

test("scrubber bounds: reported max is honoured when the data supplies one", () => {
  const { maxBound } = resolveScrubberBounds({
    minDate: "2020-01-01T00:00:00Z",
    maxDate: "2030-06-01T00:00:00Z",
    now: NOW,
  });

  assert.equal(maxBound.toISOString(), "2030-06-01T00:00:00.000Z");
});

test("scrubber bounds: playhead clamps into a range that ends before now", () => {
  const { maxBound, defaultTime } = resolveScrubberBounds({
    minDate: "2019-01-01T00:00:00Z",
    maxDate: "2020-01-01T00:00:00Z",
    now: NOW,
  });

  assert.equal(defaultTime.getTime(), maxBound.getTime());
});

test("scrubber bounds: playhead clamps into a range that starts after now", () => {
  const { minBound, defaultTime } = resolveScrubberBounds({
    minDate: "2030-01-01T00:00:00Z",
    maxDate: "2031-01-01T00:00:00Z",
    now: NOW,
  });

  assert.equal(defaultTime.getTime(), minBound.getTime());
});

test("scrubber bounds: min ahead of an open max keeps the window ordered", () => {
  const { minBound, maxBound } = resolveScrubberBounds({ minDate: "2031-01-01T00:00:00Z", now: NOW });

  assert.ok(maxBound >= minBound, "vis-timeline requires min <= max");
});

test("scrubber bounds: malformed and missing dates fall back without producing Invalid Date", () => {
  const { minBound, maxBound } = resolveScrubberBounds({ minDate: "not-a-date", maxDate: "also-bad", now: NOW });

  assert.equal(minBound.getTime(), DEFAULT_MIN_DATE.getTime());
  assert.equal(maxBound.getTime(), NOW.getTime());
});

// ── resolvePlayStepMs ────────────────────────────────────────────────────────

test("play step: a one-year span advances in ~60 frames, not 2", () => {
  const minBound = new Date("2026-01-01T00:00:00Z");
  const maxBound = new Date("2027-01-01T00:00:00Z");
  const span = maxBound.getTime() - minBound.getTime();

  const frames = span / resolvePlayStepMs(minBound, maxBound);

  assert.ok(frames > 50 && frames < 70, `expected ~60 frames, got ${frames}`);
});

test("play step: a decade-long span also advances in ~60 frames", () => {
  const minBound = new Date("2016-01-01T00:00:00Z");
  const maxBound = new Date("2026-01-01T00:00:00Z");
  const span = maxBound.getTime() - minBound.getTime();

  const frames = span / resolvePlayStepMs(minBound, maxBound);

  assert.ok(frames > 50 && frames < 70, `expected ~60 frames, got ${frames}`);
});

test("play step: a span of hours still advances by at least a day", () => {
  const minBound = new Date("2026-09-09T00:00:00Z");
  const maxBound = new Date("2026-09-09T06:00:00Z");

  assert.equal(resolvePlayStepMs(minBound, maxBound), 1000 * 60 * 60 * 24);
});
