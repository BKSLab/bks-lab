import type { ReactNode } from "react";

interface ContainerProps {
  children: ReactNode;
  className?: string;
}

// Content width per design spec section 8: up to 1320 px working width,
// padding 16-20 px mobile, 24 px tablet, 32-48 px desktop.
export function Container({ children, className = "" }: ContainerProps) {
  return (
    <div
      className={`mx-auto w-full max-w-[1320px] px-4 md:px-6 desktop:px-10 ${className}`}
    >
      {children}
    </div>
  );
}
