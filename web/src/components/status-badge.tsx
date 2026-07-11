import {
  CheckCircle2Icon,
  ClockIcon,
  Loader2Icon,
  XCircleIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ResearchStatus } from "@/lib/api";

const CONFIG: Record<
  ResearchStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline";
    icon: typeof ClockIcon;
    className?: string;
    spin?: boolean;
  }
> = {
  queued: { label: "Queued", variant: "secondary", icon: ClockIcon },
  running: {
    label: "Running",
    variant: "outline",
    icon: Loader2Icon,
    className: "border-primary/40 text-primary",
    spin: true,
  },
  done: {
    label: "Done",
    variant: "outline",
    icon: CheckCircle2Icon,
    className: "border-primary/40 text-primary",
  },
  failed: { label: "Failed", variant: "destructive", icon: XCircleIcon },
};

export function StatusBadge({
  status,
  className,
}: {
  status: ResearchStatus;
  className?: string;
}) {
  const cfg = CONFIG[status] ?? CONFIG.queued;
  const Icon = cfg.icon;
  return (
    <Badge variant={cfg.variant} className={cn(cfg.className, className)}>
      <Icon className={cn("size-3", cfg.spin && "animate-spin")} />
      {cfg.label}
    </Badge>
  );
}
