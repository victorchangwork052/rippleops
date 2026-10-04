// Small shadcn/ui-style primitives (MIT patterns, written in-repo to keep the
// dependency surface small).
import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, CircleCheck, CircleDashed, LoaderCircle, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { APPROVAL_LABEL } from "@/lib/format";
import type { ApprovalStatus, RiskLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-[18px] [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-white shadow-sm hover:bg-primary-hover",
        secondary: "border border-border-strong bg-surface text-text shadow-sm hover:bg-surface-muted",
        ghost: "text-muted hover:bg-surface-muted hover:text-text",
        soft: "bg-primary-soft text-primary hover:bg-[#e0e7ff]",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-9 px-3.5",
        lg: "h-11 px-5 text-[15px]",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export function Button({
  className,
  variant,
  size,
  ...props
}: ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export function Card({ className, ...props }: ComponentProps<"section">) {
  return <section className={cn("rounded-xl border border-border bg-surface shadow-[0_1px_2px_rgba(16,24,40,0.04)]", className)} {...props} />;
}

export function CardHeader({
  title,
  description,
  icon: Icon,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  icon?: LucideIcon;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3 border-b border-border px-5 py-3.5", className)}>
      <div className="flex min-w-0 items-start gap-2.5">
        {Icon && <Icon className="mt-0.5 size-[18px] shrink-0 text-subtle" aria-hidden />}
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-text">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-subtle">{description}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5">{eyebrow}</div>}
        <h1 className="text-[28px] font-semibold tracking-tight text-text">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-[15px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium [&_svg]:size-3.5",
  {
    variants: {
      tone: {
        neutral: "border-border bg-surface-muted text-muted",
        primary: "border-primary-border bg-primary-soft text-primary",
        critical: "border-critical-border bg-critical-soft text-critical",
        high: "border-high-border bg-high-soft text-high",
        warning: "border-warning-border bg-warning-soft text-warning",
        success: "border-success-border bg-success-soft text-success",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export const RISK_META: Record<RiskLevel, { label: string; tone: "critical" | "high" | "warning" | "success"; icon: LucideIcon; color: string }> = {
  CRITICAL: { label: "Critical", tone: "critical", icon: CircleAlert, color: "var(--critical)" },
  HIGH: { label: "High", tone: "high", icon: TriangleAlert, color: "var(--high)" },
  MEDIUM: { label: "Medium", tone: "warning", icon: CircleDashed, color: "var(--warning)" },
  LOW: { label: "Low", tone: "success", icon: CircleCheck, color: "var(--success)" },
};

/** Risk is always shown with an icon and a word, never color alone. */
export function RiskBadge({ level, suffix = "" }: { level: RiskLevel; suffix?: string }) {
  const m = RISK_META[level];
  return (
    <Badge tone={m.tone}>
      <m.icon aria-hidden />
      {m.label}
      {suffix}
    </Badge>
  );
}

export function ApprovalBadge({ status }: { status: ApprovalStatus | null | undefined }) {
  const s = status ?? "NONE";
  const tone = s === "APPROVED" ? "success" : s === "VALIDATION_REQUIRED" ? "warning" : "critical";
  const Icon = s === "APPROVED" ? CircleCheck : s === "VALIDATION_REQUIRED" ? TriangleAlert : CircleAlert;
  return (
    <Badge tone={tone}>
      <Icon aria-hidden />
      {APPROVAL_LABEL[s]}
    </Badge>
  );
}

export function KpiCard({
  label,
  value,
  context,
  icon: Icon,
  tone = "neutral",
  className,
}: {
  label: string;
  value: ReactNode;
  context: ReactNode;
  icon: LucideIcon;
  tone?: "neutral" | "critical" | "warning" | "primary";
  className?: string;
}) {
  const iconTone = {
    neutral: "bg-surface-muted text-muted",
    critical: "bg-critical-soft text-critical",
    warning: "bg-warning-soft text-warning",
    primary: "bg-primary-soft text-primary",
  }[tone];
  return (
    <div className={cn("rounded-xl border border-border bg-surface p-4", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-muted">{label}</span>
        <span className={cn("grid size-7 place-items-center rounded-md", iconTone)}>
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <div className="num mt-2 text-[30px] font-semibold leading-none tracking-tight text-text">{value}</div>
      <div className="mt-2 text-[12.5px] text-subtle">{context}</div>
    </div>
  );
}

export function LoadingState({ label, className }: { label: string; className?: string }) {
  return (
    <div role="status" className={cn("flex items-center justify-center gap-2.5 py-16 text-sm text-muted", className)}>
      <LoaderCircle className="size-5 animate-spin text-primary" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-critical-border bg-critical-soft p-4">
      <CircleAlert className="mt-0.5 size-5 shrink-0 text-critical" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-critical">{title}</p>
        <p className="mt-0.5 text-sm text-text">{message}</p>
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="grid size-11 place-items-center rounded-xl bg-primary-soft text-primary">
        <Icon className="size-5" aria-hidden />
      </span>
      <h3 className="mt-4 text-base font-semibold text-text">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted">{description}</p>
      {actions && <div className="mt-5 flex flex-wrap justify-center gap-2">{actions}</div>}
    </div>
  );
}

export function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-text">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-subtle">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "h-9 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-text shadow-sm placeholder:text-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20";

export function DefinitionList({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="space-y-3">
      {items.map((it) => (
        <div key={it.label}>
          <dt className="text-xs font-medium text-subtle">{it.label}</dt>
          <dd className="mt-0.5 text-sm text-text">{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
