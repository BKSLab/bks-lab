import Link from "next/link";
import { ArrowRightIcon } from "@/components/ui/icons";

export function SectionHeading({
  title,
  href,
  linkText,
}: {
  title: string;
  href: string;
  linkText: string;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
      <h2 className="text-3xl font-bold">{title}</h2>
      <Link href={href} className="text-link">
        {linkText} <ArrowRightIcon className="h-4 w-4" />
      </Link>
    </div>
  );
}
