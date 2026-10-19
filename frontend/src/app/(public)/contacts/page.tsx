import { ArrowUpRight, Mail, Phone } from "lucide-react";

import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { Container } from "@/components/layout/Container";
import { PublicForm } from "@/components/forms/PublicForm";
import { pageMetadata } from "@/lib/content";

export const metadata = pageMetadata(
  "Контакты",
  "Как связаться с автором BKS Lab: обсудить проект, статью или идею.",
  "/contacts",
);

const socialLinks = [
  {
    title: "ВКонтакте",
    description: "Личная страница",
    href: "https://vk.com/id30907580",
  },
  {
    title: "GitHub",
    description: "Код и проекты",
    href: "https://github.com/BKSLab",
  },
  {
    title: "Дзен",
    description: "Мой блог",
    href: "https://dzen.ru/bks_daily",
  },
];

export default function ContactsPage() {
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={[{ title: "Контакты" }]} />
      <div className="grid items-start gap-12 desktop:grid-cols-2 desktop:gap-16">
        <div className="min-w-0">
          <header>
            <p className="eyebrow mb-4">НАЧНЁМ С РАЗГОВОРА</p>
            <h1 className="page-title">Контакты</h1>
            <p className="mt-6 max-w-prose text-xl text-text-muted">
              Обсудить проект, задать вопрос о статье или поделиться идеей —
              выберите удобный способ связи или напишите через форму.
            </p>
          </header>

          <section aria-labelledby="contact-author" className="mt-8 border-t border-border pt-8">
            <h2 id="contact-author" className="text-2xl font-semibold tracking-tight">
              Кирилл Барабанщиков
            </h2>
            <p className="mt-2 text-text-muted">Автор BKS Lab</p>
            <address className="mt-5 not-italic">
              <ul className="space-y-3">
                <li>
                  <a href="tel:+79124646606" className="text-link">
                    <Phone size={20} strokeWidth={1.75} aria-hidden="true" focusable="false" className="shrink-0" />
                    <span><span className="sr-only">Телефон: </span>+7 (912) 464-66-06</span>
                  </a>
                </li>
                <li>
                  <a href="mailto:bks2408@mail.ru" className="text-link">
                    <Mail size={20} strokeWidth={1.75} aria-hidden="true" focusable="false" className="shrink-0" />
                    <span className="break-all"><span className="sr-only">Email: </span>bks2408@mail.ru</span>
                  </a>
                </li>
              </ul>

              <p className="mt-6 text-sm text-text-muted">Соцсети и проекты · ссылки откроются в новой вкладке</p>
              <ul className="mt-3 grid gap-3">
                {socialLinks.map((social) => (
                  <li key={social.href} className="min-w-0">
                    <a
                      href={social.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex min-h-[72px] items-center justify-between gap-3 rounded-card border border-border bg-surface px-5 py-3 hover:border-accent"
                    >
                      <span className="min-w-0">
                        <span className="block font-semibold">{social.title}</span>
                        <span className="block text-sm text-text-muted">{social.description}</span>
                        <span className="sr-only"> (в новой вкладке)</span>
                      </span>
                      <ArrowUpRight size={20} strokeWidth={1.75} aria-hidden="true" focusable="false" className="shrink-0 text-accent" />
                    </a>
                  </li>
                ))}
              </ul>
            </address>
          </section>
        </div>
        <section
          aria-labelledby="contact-title"
          className="min-w-0 rounded-card border border-border bg-surface p-6 md:p-8"
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
