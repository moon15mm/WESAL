"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ApiError } from "./api";

/** Small helper: run an async submit, expose loading + field errors, toast general errors. */
export function useApiAction() {
  const [loading, setLoading] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  async function run<T>(fn: () => Promise<T>, opts: { success?: string; silent?: boolean } = {}): Promise<T | undefined> {
    setLoading(true);
    setFields({});
    setError(null);
    try {
      const out = await fn();
      if (opts.success) toast.success(opts.success);
      return out;
    } catch (e) {
      if (e instanceof ApiError) {
        setFields(e.fields || {});
        setError(e.message);
        if (!opts.silent) toast.error(e.message);
      } else {
        setError(String(e));
        if (!opts.silent) toast.error(String(e));
      }
      return undefined;
    } finally {
      setLoading(false);
    }
  }
  return { loading, fields, error, run, setError };
}
