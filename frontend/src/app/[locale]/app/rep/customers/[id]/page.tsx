"use client";

import { use } from "react";
import { CustomerDetail } from "@/components/app/crm";

export default function RepCustomer({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <CustomerDetail side="rep" id={id} />;
}
