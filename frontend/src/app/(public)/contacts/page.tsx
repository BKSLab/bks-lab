import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { Container } from "@/components/layout/Container";
import { PublicForm } from "@/components/forms/PublicForm";
import { pageMetadata } from "@/lib/content";
import { contactEmail } from "@/lib/contact";

export const metadata = pageMetadata(
  "Контакты",
  "Как связаться с автором BKS Lab: обсудить проект, статью или идею.",
  "/contacts",
);

export default function ContactsPage() {
  const email = contactEmail();
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={[{ title: "Контакты" }]} />
      <div className="grid gap-12 desktop:grid-cols-2">
        <header>
          <p className="eyebrow mb-4">НАЧНЁМ С РАЗГОВОРА</p>
          <h1 className="page-title">Контакты</h1>
          <p className="mt-6 max-w-prose text-xl text-text-muted">
            Обсудить проект, задать вопрос о статье или поделиться идеей.
          </p>
          {email && (
            <p className="mt-6 max-w-prose text-text-muted">
              Напишите напрямую: <a className="break-all text-accent underline underline-offset-4" href={`mailto:${email}`}>{email}</a>.
            </p>
          )}
        </header>
        <section
          aria-labelledby="contact-title"
          className="rounded-card border border-border bg-surface p-6 md:p-8"
        >
          <h2 id="contact-title" className="mb-6 text-2xl font-semibold">
            Связаться
          </h2>
          <PublicForm kind="contact" />
        </section>
      </div>
    </Container>
  );
}
