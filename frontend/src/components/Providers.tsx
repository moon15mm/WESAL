"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";
import { ApiError } from "@/lib/api";
import { SessionProvider } from "@/lib/session";

export function Providers({ children, dir }: { children: React.ReactNode; dir: "rtl" | "ltr" }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <SessionProvider>{children}</SessionProvider>
      <Toaster position={dir === "rtl" ? "top-left" : "top-right"} richColors closeButton dir={dir} toastOptions={{ style: { fontFamily: "var(--wesal-font)" } }} />
    </QueryClientProvider>
  );
}
