import Link from "next/link";

import { Container } from "@/components/layout/Container";

export function NotFoundContent() {
  return (
    <Container className="py-16">
      <h1 className="text-4xl font-bold md:text-5xl">Страница не найдена</h1>
      <p className="mt-4 max-w-prose text-text-muted">
        Такой страницы нет. Возможно, ссылка устарела или в адресе опечатка.
      </p>
      <p className="mt-6">
        <Link href="/" className="text-accent underline underline-offset-4">
          Перейти на главную
        </Link>
      </p>
    </Container>
  );
}
