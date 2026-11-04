"use client";

import { use } from "react";
import { AuthorizationDetail } from "@/components/app/authorizations";

export default function RepAuthorization({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <AuthorizationDetail side="rep" id={id} />;
}
