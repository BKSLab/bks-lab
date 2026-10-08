import { redirect } from "next/navigation";
import { requireAdmin } from "@/lib/admin-api";

export const dynamic = "force-dynamic";

export default async function NewsPage() {
  await requireAdmin();
  redirect("/admin/news/items");
}
