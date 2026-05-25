import type { GraphBehavior } from "./types";

const SWEEP_TICKS = 6;
const SWEEP_INTERVAL_MS = 60;

export function createPathHighlightBehavior(): GraphBehavior {
  let lastPathSignature = "";
  let sweepTimer: ReturnType<typeof setTimeout> | null = null;
  let sweepGeneration = 0;

  function cancelSweep() {
    sweepGeneration++;
    if (sweepTimer !== null) {
      clearTimeout(sweepTimer);
      sweepTimer = null;
    }
  }

  function scheduleSweep(sigma: { refresh: () => void }, tick: number, gen: number) {
    if (tick >= SWEEP_TICKS) return;
    sweepTimer = setTimeout(() => {
      if (gen !== sweepGeneration) return;
      sigma.refresh();
      scheduleSweep(sigma, tick + 1, gen);
    }, SWEEP_INTERVAL_MS);
  }

  return {
    id: "path-highlight",
    attach: () => {},
    detach: (context) => {
      cancelSweep();
      lastPathSignature = "";
      context.sigma.refresh();
    },
    onStateChange: (context, interactionState) => {
      const nextPathSignature = interactionState.activePath.join("::");
      if (nextPathSignature === lastPathSignature) {
        return;
      }

      lastPathSignature = nextPathSignature;
      cancelSweep();
      context.sigma.refresh();

      // Animate intermediate nodes lighting up sequentially
      if (interactionState.activePath.length > 2) {
        scheduleSweep(context.sigma, 0, sweepGeneration);
      }
    },
  };
}
