export interface ScrubberBoundsInput {
  minDate?: string;
  maxDate?: string;
  now: Date;
}

export interface ScrubberBounds {
  minBound: Date;
  maxBound: Date;
  defaultTime: Date;
}

export const DEFAULT_MIN_DATE = new Date("1970-01-01T00:00:00Z");
const ONE_DAY_MS = 1000 * 60 * 60 * 24;
const PLAY_FRAMES = 60;

function parseBound(value: string | undefined, fallback: Date): Date {
  if (!value) return fallback;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? fallback : parsed;
}

function clamp(value: Date, minBound: Date, maxBound: Date): Date {
  if (value < minBound) return minBound;
  if (value > maxBound) return maxBound;
  return value;
}

/**
 * `/api/temporal/bounds` reports `max: null` for graphs whose nodes carry
 * `valid_from` instants and no `valid_until`, which is the common case rather
 * than malformed data. Such a graph is known up to the present and no further,
 * so `now` is the honest upper bound and the honest starting playhead.
 */
export function resolveScrubberBounds({ minDate, maxDate, now }: ScrubberBoundsInput): ScrubberBounds {
  const minBound = parseBound(minDate, DEFAULT_MIN_DATE);
  const maxBound = parseBound(maxDate, now);
  const orderedMax = maxBound > minBound ? maxBound : minBound;
  return { minBound, maxBound: orderedMax, defaultTime: clamp(now, minBound, orderedMax) };
}

/** Keeps a play-through at ~PLAY_FRAMES steps whatever the span, with a one-day floor. */
export function resolvePlayStepMs(minBound: Date, maxBound: Date): number {
  const span = maxBound.getTime() - minBound.getTime();
  return Math.max(ONE_DAY_MS, Math.round(span / PLAY_FRAMES));
}
