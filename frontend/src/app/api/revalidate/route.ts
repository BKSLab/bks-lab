import { createHash, timingSafeEqual } from "node:crypto";
import { revalidatePath, revalidateTag } from "next/cache";

export const runtime = "nodejs";

const headers = { "Cache-Control": "no-store" };

/** An operator webhook; credentials stay out of URLs, logs and public bundles. */
export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret || secret.length < 32) {
    return Response.json({ detail: "Revalidation is not configured" }, { status: 503, headers });
  }
  const authorization = request.headers.get("authorization") ?? "";
  const supplied = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
  const digest = (value: string) => createHash("sha256").update(value).digest();
  if (!supplied || !timingSafeEqual(digest(secret), digest(supplied))) {
    return Response.json({ detail: "Unauthorized" }, { status: 401, headers });
  }
  for (const tag of ["articles", "notes", "projects"]) {
    revalidateTag(tag, { expire: 0 });
  }
  revalidatePath("/", "layout");
  revalidatePath("/sitemap.xml");
  return Response.json({ revalidated: true }, { headers });
}
