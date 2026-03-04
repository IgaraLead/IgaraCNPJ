import React from "react";
import logoSrc from "./logo.svg";

interface LogoProps {
  /** Width/height in pixels (square). Default 32 */
  size?: number;
  style?: React.CSSProperties;
  className?: string;
}

/**
 * IgaraLead brand logo.
 */
export default function Logo({ size = 32, style, className }: LogoProps) {
  return (
    <img
      src={logoSrc}
      alt="IgaraLead logo"
      width={size}
      height={size}
      className={className}
      style={{ display: "block", ...style }}
    />
  );
}
