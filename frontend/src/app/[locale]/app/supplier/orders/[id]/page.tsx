"use client";

import { use } from "react";
import { OrderDetail } from "@/components/app/orders";

export default function SupplierOrder({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <OrderDetail side="supplier" id={id} />;
}
