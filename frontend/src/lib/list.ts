"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type Page } from "./api";
import { useSession } from "./session";

/** Paginated list state for an API collection endpoint. */
export function useList<T>(path: string | null, filters: Record<string, unknown> = {}, pageSize = 20) {
  const { workspace } = useSession();
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: [path, workspace?.businessId, filters, page, pageSize],
    queryFn: () => api<Page<T>>(path!, { query: { ...filters, page, page_size: pageSize } }),
    enabled: !!path,
    placeholderData: keepPreviousData,
  });
  return { ...q, page, setPage: (p: number) => setPage(p), pageSize, reset: () => setPage(1) };
}

export function useApiQuery<T>(key: unknown[], path: string | null, query?: Record<string, unknown>) {
  const { workspace } = useSession();
  return useQuery({ queryKey: [...key, workspace?.businessId, query], queryFn: () => api<T>(path!, { query }), enabled: !!path });
}
