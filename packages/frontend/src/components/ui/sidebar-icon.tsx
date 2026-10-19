"use client";

import type { Transition } from "motion/react";
import { motion, useAnimation } from "motion/react";
import type { HTMLAttributes } from "react";
import { forwardRef, useCallback, useImperativeHandle, useRef } from "react";

import { cn } from "@/lib/utils";

export interface SidebarIconHandle {
  startAnimation: () => void;
  stopAnimation: () => void;
}

interface SidebarIconProps extends HTMLAttributes<HTMLDivElement> {
  size?: number;
  isCollapsed?: boolean;
}

const DEFAULT_TRANSITION: Transition = {
  times: [0, 0.4, 1],
  duration: 0.5,
};

const SidebarIcon = forwardRef<SidebarIconHandle, SidebarIconProps>(
  (
    {
      onMouseEnter,
      onMouseLeave,
      className,
      size = 28,
      isCollapsed = true,
      ...props
    },
    ref
  ) => {
    const controls = useAnimation();
    const isControlledRef = useRef(false);

    useImperativeHandle(ref, () => {
      isControlledRef.current = true;
      return {
        startAnimation: () => controls.start("animate"),
        stopAnimation: () => controls.start("normal"),
      };
    });

    const handleMouseEnter = useCallback(
      (e: React.MouseEvent<HTMLDivElement>) => {
        if (isControlledRef.current) {
          onMouseEnter?.(e);
        } else {
          controls.start("animate");
        }
      },
      [controls, onMouseEnter]
    );

    const handleMouseLeave = useCallback(
      (e: React.MouseEvent<HTMLDivElement>) => {
        if (isControlledRef.current) {
          onMouseLeave?.(e);
        } else {
          controls.start("normal");
        }
      },
      [controls, onMouseLeave]
    );

    const renderChevron = () => {
      if (isCollapsed) {
        // Points right to expand, sits inside the sidebar area
        return (
          <motion.path
            animate={controls}
            d="m5.5 9.5 2.5 2.5-2.5 2.5"
            stroke="currentColor"
            style={{ filter: "brightness(0.92)" }}
            transition={DEFAULT_TRANSITION}
            variants={{
              normal: { x: 0 },
              animate: { x: [0, 1.5, 0] }, // Reduced bounce to stay inside the sidebar
            }}
          />
        );
      } else {
        // Points left to collapse
        return (
          <motion.path
            animate={controls}
            d="m8.5 9.5-2.5 2.5 2.5 2.5"
            stroke="currentColor"
            transition={DEFAULT_TRANSITION}
            variants={{
              normal: { x: 0 },
              animate: { x: [0, -1.5, 0] },
            }}
          />
        );
      }
    };

    return (
      <div
        className={cn(className)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        {...props}
      >
        <svg
          fill="none"
          height={size}
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          viewBox="0 0 24 24"
          width={size}
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Wider, cleaner outer rectangle */}
          <rect x="2" y="4" width="20" height="16" rx="2" ry="2" />

          {/* Sidebar vertical separator line (moved further right to widen sidebar section) */}
          <line x1="12" y1="4" x2="12" y2="20" />

          {/* Animated chevron inside the sidebar */}
          {renderChevron()}
        </svg>
      </div>
    );
  }
);

SidebarIcon.displayName = "SidebarIcon";

export { SidebarIcon };
