"use client";

import { Loader2 } from "lucide-react";
import { forwardRef, useId } from "react";
import { cx } from "@/lib/format";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline" | "success";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-navy-700 text-white hover:bg-navy-600 active:bg-navy-800 shadow-sm",
  secondary: "bg-teal-500 text-white hover:bg-teal-600 shadow-sm",
  success: "bg-success text-white hover:brightness-95 shadow-sm",
  outline: "border border-line bg-white text-ink hover:border-navy-200 hover:bg-navy-50",
  ghost: "text-ink hover:bg-navy-50",
  danger: "bg-danger text-white hover:brightness-95 shadow-sm",
};
const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm gap-1.5 rounded-sm",
  md: "h-10 px-4 text-sm gap-2 rounded-md",
  lg: "h-12 px-6 text-base gap-2 rounded-md",
  icon: "h-9 w-9 rounded-md",
};

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cx(
        "inline-flex select-none items-center justify-center font-medium whitespace-nowrap transition-all duration-150",
        "disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

const fieldBase =
  "w-full rounded-md border border-line bg-white px-3 text-sm text-ink placeholder:text-muted/70 transition " +
  "focus:border-teal-400 focus:shadow-[var(--shadow-focus)] focus:outline-none disabled:bg-page disabled:text-muted";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return <input ref={ref} className={cx(fieldBase, "h-10", invalid && "border-danger", className)} aria-invalid={invalid || undefined} {...rest} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }>(
  function Textarea({ className, invalid, rows = 3, ...rest }, ref) {
    return <textarea ref={ref} rows={rows} className={cx(fieldBase, "py-2", invalid && "border-danger", className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }>(
  function Select({ className, invalid, children, ...rest }, ref) {
    return (
      <select ref={ref} className={cx(fieldBase, "h-10 pe-8", invalid && "border-danger", className)} {...rest}>
        {children}
      </select>
    );
  },
);

export function Field({
  label,
  hint,
  error,
  children,
  required,
  className,
}: {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  children: (id: string) => React.ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
          {required && <span className="text-danger ms-0.5">*</span>}
        </label>
      )}
      {children(id)}
      {error ? <p className="text-xs text-danger">{error}</p> : hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function Checkbox({ label, className, ...rest }: React.InputHTMLAttributes<HTMLInputElement> & { label: React.ReactNode }) {
  return (
    <label className={cx("inline-flex cursor-pointer items-start gap-2 text-sm text-ink", className)}>
      <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 rounded border-line accent-teal-500" {...rest} />
      <span>{label}</span>
    </label>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: React.ReactNode; disabled?: boolean }) {
  return (
    <label className={cx("inline-flex items-center gap-3 text-sm", disabled ? "opacity-50" : "cursor-pointer")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx("relative h-6 w-11 rounded-full transition", checked ? "bg-teal-500" : "bg-navy-100")}
      >
        <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all", checked ? "start-[22px]" : "start-0.5")} />
      </button>
      {label}
    </label>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx("h-5 w-5 animate-spin text-teal-500", className)} aria-hidden />;
}
