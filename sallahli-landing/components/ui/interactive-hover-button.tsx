import React from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface InteractiveHoverButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  text?: string;
}

const InteractiveHoverButton = React.forwardRef<
  HTMLButtonElement,
  InteractiveHoverButtonProps
>(({ text = "Button", className, ...props }, ref) => {
  return (
    <button
      ref={ref}
      className={cn(
        "group relative w-auto flex items-center justify-center gap-2 px-10 py-2 cursor-pointer overflow-hidden rounded-full border bg-background font-semibold transition-all duration-300",
        className,
      )}
      {...props}
    >
      {/* Idle State (Reserves space for both text AND arrow) */}
      <div className="flex items-center gap-2 transition-all duration-300 group-hover:translate-x-12 group-hover:opacity-0 font-semibold text-foreground">
        <span>{text}</span>
        <ArrowRight className="w-4 h-4 opacity-0" />
      </div>

      {/* Hover State (Fades in over the circle) */}
      <div className="absolute inset-0 z-10 flex h-full w-full items-center justify-center gap-2 text-primary-foreground opacity-0 transition-all duration-300 group-hover:opacity-100 font-semibold pr-4">
        <span>{text}</span>
        <ArrowRight className="w-4 h-4 ml-2" />
      </div>

      {/* Expansion Circle */}
      <div className="absolute left-4 top-1/2 -translate-y-1/2 h-2 w-2 scale-[1] rounded-lg bg-[#C08552] transition-all duration-300 group-hover:left-[0%] group-hover:top-[0%] group-hover:h-full group-hover:w-full group-hover:scale-[1.8] group-hover:translate-y-0 group-hover:bg-[#C08552]"></div>
    </button>
  );
});

InteractiveHoverButton.displayName = "InteractiveHoverButton";

export { InteractiveHoverButton };
