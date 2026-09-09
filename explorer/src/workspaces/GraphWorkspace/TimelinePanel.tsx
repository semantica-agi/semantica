import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { DataSet } from "vis-data";
import { Timeline } from "vis-timeline";
import type { TimelineOptions } from "vis-timeline";
import "vis-timeline/styles/vis-timeline-graph2d.css";
import { GRAPH_THEME } from "./graphTheme";
import { DEFAULT_MIN_DATE, resolvePlayStepMs, resolveScrubberBounds } from "./temporalScrubberBounds";

export interface TimelinePanelProps {
  onTimeChange: (time: Date) => void;
  minDate?: string;
  maxDate?: string;
}

const PLAYHEAD_ID = "playhead";
const PLAY_INTERVAL_MS = 500;
const ONE_DAY_MS = 1000 * 60 * 60 * 24;

const VIS_OVERRIDE_CSS = `
  .sem-timeline-wrap .vis-timeline { border: none !important; background: transparent !important; overflow: visible !important; }
  .sem-timeline-wrap .vis-panel.vis-background, .sem-timeline-wrap .vis-panel.vis-center { background: transparent !important; }
  .sem-timeline-wrap .vis-panel { border-color: ${GRAPH_THEME.ui.timeline.border} !important; }
  .sem-timeline-wrap .vis-time-axis .vis-text {
    color: ${GRAPH_THEME.ui.timeline.text} !important;
    font-size: 11px !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    padding-top: 3px !important;
  }
  .sem-timeline-wrap .vis-time-axis .vis-text.vis-major {
    color: ${GRAPH_THEME.ui.timeline.textStrong} !important;
    font-weight: 700 !important;
    font-size: 12px !important;
  }
  .sem-timeline-wrap .vis-time-axis .vis-grid.vis-minor { border-color: ${GRAPH_THEME.ui.timeline.gridMinor} !important; }
  .sem-timeline-wrap .vis-time-axis .vis-grid.vis-major { border-color: ${GRAPH_THEME.ui.timeline.gridMajor} !important; }
  .sem-timeline-wrap .vis-custom-time.${PLAYHEAD_ID} {
    background: ${GRAPH_THEME.ui.timeline.playheadSoft} !important;
    width: 2px !important;
    cursor: ew-resize !important;
    z-index: 5 !important;
  }
  .sem-timeline-wrap .vis-custom-time.${PLAYHEAD_ID} > .vis-custom-time-marker {
    background: ${GRAPH_THEME.ui.timeline.playhead} !important;
    color: ${GRAPH_THEME.ui.text.inverse} !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    border-radius: 3px !important;
    padding: 1px 5px !important;
    white-space: nowrap !important;
    box-shadow: 0 0 8px rgba(98, 226, 205, 0.45) !important;
  }
  .sem-timeline-wrap .vis-current-time { display: none !important; }
  .sem-timeline-wrap .vis-panel.vis-left { display: none !important; }
`;

function formatPlayheadLabel(value: Date): string {
  return `${value.getFullYear()}/${String(value.getMonth() + 1).padStart(2, "0")}`;
}

export function TimelinePanel({ onTimeChange, minDate, maxDate }: TimelinePanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<Timeline | null>(null);
  const playheadRef = useRef<Date>(DEFAULT_MIN_DATE);
  const playIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [displayDate, setDisplayDate] = useState(formatPlayheadLabel(DEFAULT_MIN_DATE));

  // Captured once per mount so re-renders keep the same reference and do not
  // retrigger the timeline effect below.
  const now = useMemo(() => new Date(), []);
  const { minBound, maxBound, defaultTime } = useMemo(
    () => resolveScrubberBounds({ minDate, maxDate, now }),
    [maxDate, minDate, now],
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const timeline = timelineRef.current;
    if (!timeline) {
      const items = new DataSet([]);
      const options: TimelineOptions = {
        height: "100%",
        min: minBound,
        max: maxBound,
        start: minBound,
        end: maxBound,
        showCurrentTime: false,
        zoomable: true,
        moveable: true,
        zoomMin: ONE_DAY_MS,
        zoomMax: 1000 * 60 * 60 * 24 * 365 * 80,
        showMajorLabels: true,
        showMinorLabels: true,
        orientation: { axis: "bottom" },
        margin: { item: 0, axis: 0 },
        selectable: false,
        stack: false,
      } as TimelineOptions;

      const nextTimeline = new Timeline(containerRef.current, items, options);
      timelineRef.current = nextTimeline;
      playheadRef.current = defaultTime;
      nextTimeline.addCustomTime(defaultTime, PLAYHEAD_ID);
      nextTimeline.on("timechange", (props: { id: string; time: Date }) => {
        if (props.id !== PLAYHEAD_ID) return;
        playheadRef.current = props.time;
        nextTimeline.setCustomTime(props.time, PLAYHEAD_ID);
        onTimeChange(props.time);
        setDisplayDate(formatPlayheadLabel(props.time));
      });
      onTimeChange(defaultTime);
      setDisplayDate(formatPlayheadLabel(defaultTime));
      return () => {
        nextTimeline.destroy();
        timelineRef.current = null;
      };
    }

    timeline.setOptions({ min: minBound, max: maxBound, start: minBound, end: maxBound });
    playheadRef.current = defaultTime;
    timeline.setCustomTime(defaultTime, PLAYHEAD_ID);
    onTimeChange(defaultTime);
    setDisplayDate(formatPlayheadLabel(defaultTime));
  }, [defaultTime, maxBound, minBound, onTimeChange]);

  const startPlay = useCallback(() => {
    if (playIntervalRef.current) return;
    playIntervalRef.current = setInterval(() => {
      const timeline = timelineRef.current;
      if (!timeline) return;
      const next = new Date(playheadRef.current.getTime() + resolvePlayStepMs(minBound, maxBound));
      if (next >= maxBound) {
        next.setTime(minBound.getTime());
      }
      playheadRef.current = next;
      timeline.setCustomTime(next, PLAYHEAD_ID);
      onTimeChange(next);
      setDisplayDate(formatPlayheadLabel(next));
    }, PLAY_INTERVAL_MS);
  }, [maxBound, minBound, onTimeChange]);

  const stopPlay = useCallback(() => {
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current);
      playIntervalRef.current = null;
    }
  }, []);

  const togglePlay = useCallback(() => {
    setIsPlaying((previous) => {
      if (previous) {
        stopPlay();
        return false;
      }
      startPlay();
      return true;
    });
  }, [startPlay, stopPlay]);

  useEffect(() => () => stopPlay(), [stopPlay]);

  return (
    <div style={{ position: "relative", width: "100%", height: "90px", borderTop: `1px solid ${GRAPH_THEME.ui.timeline.border}`, background: GRAPH_THEME.ui.timeline.background, backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", display: "flex", alignItems: "stretch", flexShrink: 0 }}>
      <style>{VIS_OVERRIDE_CSS}</style>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 4, padding: "0 16px", borderRight: `1px solid ${GRAPH_THEME.ui.timeline.border}`, minWidth: 80, flexShrink: 0 }}>
        <button
          id="temporal-play-btn"
          onClick={togglePlay}
          title={isPlaying ? "Pause Evolution" : "Play Evolution"}
          style={{ width: 34, height: 34, borderRadius: "50%", border: `1.5px solid ${isPlaying ? GRAPH_THEME.ui.control.activeBorder : GRAPH_THEME.ui.control.defaultBorder}`, background: isPlaying ? GRAPH_THEME.ui.timeline.playheadSoft : GRAPH_THEME.ui.control.defaultBg, color: GRAPH_THEME.ui.timeline.playhead, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s", boxShadow: isPlaying ? "0 0 10px rgba(98, 226, 205, 0.32)" : "none" }}
        >
          {isPlaying ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21" /></svg>
          )}
        </button>
        <span style={{ fontSize: 10, color: isPlaying ? GRAPH_THEME.ui.timeline.playhead : GRAPH_THEME.ui.timeline.text, fontFamily: "monospace", letterSpacing: "0.04em", transition: "color 0.2s" }}>
          {displayDate}
        </span>
      </div>

      <div style={{ position: "absolute", top: 5, left: 100, fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", color: GRAPH_THEME.ui.text.subtle, textTransform: "uppercase", pointerEvents: "none", zIndex: 2 }}>
        Temporal Scrubber · {minBound.getFullYear()}-{maxBound.getFullYear()}
      </div>

      <div className="sem-timeline-wrap" style={{ flex: 1, overflow: "hidden", position: "relative" }}>
        <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }} />
      </div>
    </div>
  );
}
