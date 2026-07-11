import { cn } from "@/lib/utils";

/** Minimal, dependency-free progress bar (0-100). */
export function ProgressBar({
  value,
  className,
  indeterminate = false,
}: {
  value: number;
  className?: string;
  indeterminate?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={indeterminate ? undefined : clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full bg-primary shadow-[0_0_8px_oklch(0.723_0.219_149.579_/_0.4)] transition-[width] duration-500 ease-out",
          indeterminate && "w-1/3 animate-[progress-indeterminate_1.4s_ease-in-out_infinite]",
        )}
        style={indeterminate ? undefined : { width: `${clamped}%` }}
      />
    </div>
  );
}
