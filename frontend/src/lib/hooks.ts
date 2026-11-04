"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type City = { id: number; code: string; name: string; region_id: number; lat?: number; lng?: number };
export type Category = { id: number; slug: string; name: string; icon: string | null; names: Record<string, string> };

export function useCities() {
  return useQuery({ queryKey: ["ref", "cities"], queryFn: () => api<City[]>("/ref/cities"), staleTime: 3600_000 });
}
export function useCategories() {
  return useQuery({ queryKey: ["ref", "categories"], queryFn: () => api<Category[]>("/ref/categories"), staleTime: 3600_000 });
}
