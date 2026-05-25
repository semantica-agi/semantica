import type { CSSProperties, ReactNode } from "react";

type SurfaceTone = "default" | "subtle" | "accent";
type SurfacePadding = "default" | "tight" | "none";
type ChipTone = "default" | "warm" | "success";

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function WorkspaceFrame({
  kicker,
  title,
  subtitle,
  actions,
  children,
}: {
  kicker?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="sem-workspace-frame">
      <header className="sem-workspace-hero">
        <div>
          {kicker ? <div className="sem-workspace-kicker">{kicker}</div> : null}
          <h2 className="sem-workspace-title">{title}</h2>
          {subtitle ? <p className="sem-workspace-subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="sem-workspace-actions">{actions}</div> : null}
      </header>
      {children}
    </div>
  );
}

export function SurfaceCard({
  children,
  tone = "default",
  padding = "default",
  className,
  style,
}: {
  children: ReactNode;
  tone?: SurfaceTone;
  padding?: SurfacePadding;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={cx("sem-surface", tone !== "default" && `sem-surface--${tone}`, className)} style={style}>
      {padding === "none" ? children : <div className={cx("sem-surface-body", padding === "tight" && "sem-surface-body--tight")}>{children}</div>}
    </div>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="sem-section-header">
      <div>
        {eyebrow ? <div className="sem-section-eyebrow">{eyebrow}</div> : null}
        <h3 className="sem-section-title">{title}</h3>
        {description ? <p className="sem-section-copy">{description}</p> : null}
      </div>
      {actions ? <div className="sem-command-group">{actions}</div> : null}
    </div>
  );
}

export function MetricChip({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: ChipTone;
}) {
  return <span className={cx("sem-chip", tone !== "default" && `sem-chip--${tone}`)}>{children}</span>;
}

export function CommandBar({
  left,
  right,
}: {
  left?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="sem-command-bar">
      <div className="sem-command-group">{left}</div>
      <div className="sem-command-group">{right}</div>
    </div>
  );
}

export function InspectorPanel({
  children,
  open = true,
  className,
}: {
  children: ReactNode;
  open?: boolean;
  className?: string;
}) {
  return (
    <SurfaceCard className={cx("sem-inspector", className)} padding="none" style={{ display: open ? "block" : "none" }}>
      {children}
    </SurfaceCard>
  );
}

export function EmptyState({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <div className="sem-empty-state">
      {icon}
      <div className="sem-empty-state-title">{title}</div>
      <div className="sem-empty-state-copy">{description}</div>
    </div>
  );
}

export function LoadingState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="sem-loading-state">
      <div className="animate-spin" style={{
        width: 24,
        height: 24,
        borderRadius: "999px",
        border: "2px solid rgba(103, 182, 255, 0.18)",
        borderTopColor: "rgba(158, 217, 255, 0.92)",
        marginBottom: 12,
      }} />
      <div className="sem-loading-state-title">{title}</div>
      <div className="sem-loading-state-copy">{description}</div>
    </div>
  );
}

export function SegmentedControl({
  children,
}: {
  children: ReactNode;
}) {
  return <div className="sem-segmented">{children}</div>;
}
