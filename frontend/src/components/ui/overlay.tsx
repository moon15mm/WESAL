"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as DM from "@radix-ui/react-dropdown-menu";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { cx } from "@/lib/format";
import { Button, Field, Textarea } from "./primitives";

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const t = useTranslations("common");
  const w = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[size];
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-navy-900/40 backdrop-blur-[2px] animate-fade-in" />
        <Dialog.Content
          className={cx(
            "fixed inset-x-0 bottom-0 z-50 max-h-[92vh] overflow-y-auto rounded-t-xl bg-white p-5 shadow-[var(--shadow-pop)] animate-slide-up",
            "sm:inset-auto sm:start-1/2 sm:top-1/2 sm:w-full sm:-translate-y-1/2 sm:rounded-xl sm:p-6 rtl:sm:translate-x-1/2 ltr:sm:-translate-x-1/2",
            w,
          )}
        >
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold text-navy-700">{title}</Dialog.Title>
              {description ? <Dialog.Description className="mt-1 text-sm text-muted">{description}</Dialog.Description> : <Dialog.Description className="sr-only">{String(title)}</Dialog.Description>}
            </div>
            <Dialog.Close asChild>
              <button className="rounded-md p-1 text-muted hover:bg-navy-50 hover:text-ink" aria-label={t("close")}>
                <X className="h-5 w-5" />
              </button>
            </Dialog.Close>
          </div>
          {children}
          {footer && <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">{footer}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** Confirmation with an optional mandatory reason (for rejections, cancellations, suspensions...). */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  tone = "primary",
  requireReason,
  onConfirm,
  loading,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  confirmLabel?: React.ReactNode;
  tone?: "primary" | "danger" | "success";
  requireReason?: boolean;
  onConfirm: (reason: string) => void | Promise<void>;
  loading?: boolean;
}) {
  const t = useTranslations("common");
  const [reason, setReason] = useState("");
  const valid = !requireReason || reason.trim().length >= 3;
  return (
    <Modal
      open={open}
      onOpenChange={(v) => {
        if (!v) setReason("");
        onOpenChange(v);
      }}
      title={title}
      description={description}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("cancel")}
          </Button>
          <Button variant={tone} loading={loading} disabled={!valid} onClick={() => onConfirm(reason.trim())}>
            {confirmLabel || t("confirm")}
          </Button>
        </>
      }
    >
      {requireReason && (
        <Field label={t("reason")} required>
          {(id) => <Textarea id={id} value={reason} onChange={(e) => setReason(e.target.value)} rows={3} autoFocus />}
        </Field>
      )}
    </Modal>
  );
}

export function Dropdown({ trigger, items, align = "end" }: { trigger: React.ReactNode; items: ({ label: React.ReactNode; onSelect: () => void; icon?: React.ReactNode; danger?: boolean } | "sep")[]; align?: "start" | "end" }) {
  return (
    <DM.Root>
      <DM.Trigger asChild>{trigger}</DM.Trigger>
      <DM.Portal>
        <DM.Content align={align} sideOffset={6} className="z-50 min-w-48 rounded-md border border-line bg-white p-1 shadow-[var(--shadow-pop)] animate-fade-in">
          {items.map((it, i) =>
            it === "sep" ? (
              <DM.Separator key={i} className="my-1 h-px bg-line" />
            ) : (
              <DM.Item
                key={i}
                onSelect={it.onSelect}
                className={cx(
                  "flex cursor-pointer items-center gap-2 rounded-sm px-3 py-2 text-sm outline-none data-[highlighted]:bg-navy-50",
                  it.danger ? "text-danger" : "text-ink",
                )}
              >
                {it.icon}
                {it.label}
              </DM.Item>
            ),
          )}
        </DM.Content>
      </DM.Portal>
    </DM.Root>
  );
}
