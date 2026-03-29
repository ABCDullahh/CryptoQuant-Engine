"use client";

import {
  type ButtonHTMLAttributes,
  type ReactNode,
  forwardRef,
} from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: [
    "bg-[#00F0FF] text-[#002022] font-bold",
    "hover:opacity-90 active:opacity-80",
  ].join(" "),

  secondary: [
    "bg-[#2A2A2A] text-[#E5E2E1]",
    "hover:bg-[#353534] hover:text-[#E5E2E1]",
  ].join(" "),

  danger: [
    "bg-[#93000A]/20 text-[#FFB4AB]",
    "border border-[#93000A]/30",
    "hover:bg-[#93000A]/30",
  ].join(" "),

  ghost: [
    "bg-transparent text-[#B9CACB]",
    "hover:text-[#E5E2E1] hover:bg-[#201F1F]",
  ].join(" "),
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs rounded-sm gap-1.5",
  md: "px-4 py-2 text-sm rounded-sm gap-2",
  lg: "px-6 py-3 text-base rounded-sm gap-2.5",
};

const disabledClasses = "opacity-40 cursor-not-allowed pointer-events-none";

function Spinner({ size }: { size: ButtonSize }) {
  const dim = size === "sm" ? "h-3 w-3" : size === "lg" ? "h-5 w-5" : "h-4 w-4";
  return (
    <svg
      className={`${dim} animate-spin`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { variant = "primary", size = "md", loading = false, disabled, className = "", children, ...rest },
    ref
  ) {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={`
          inline-flex items-center justify-center font-medium
          transition-all duration-150 select-none
          ${variantClasses[variant]}
          ${sizeClasses[size]}
          ${isDisabled ? disabledClasses : "cursor-pointer"}
          ${className}
        `}
        {...rest}
      >
        {loading && <Spinner size={size} />}
        {children}
      </button>
    );
  }
);
