import { existsSync } from "node:fs";
import { join } from "node:path";

import { ArrowUpRight, Mail, Phone } from "lucide-react";
import Link from "next/link";
import { AboutPhoto } from "@/components/content/AboutPhoto";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { Container } from "@/components/layout/Container";
import { pageMetadata } from "@/lib/content";

export const metadata = pageMetadata(
  "Обо мне",
  "Кирилл Барабанщиков: путь от юридической практики к разработке, проект «Работа для всех» с помощником «Верой» и размышления о пользе ИИ.",
  "/about",
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

export default function AboutPage() {
  const hasPortrait = existsSync(
    join(process.cwd(), "public", "images", "author.jpg"),
  );

  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={[{ title: "Обо мне" }]} />
      <article className="mx-auto max-w-6xl">
        <header className="mb-8 md:mb-10">
          <p className="eyebrow mb-4">КИРИЛЛ БАРАБАНЩИКОВ</p>
          <h1 className="page-title">Обо мне</h1>
        </header>

        <div className="space-y-14 md:space-y-20">
          <div
            className={`grid items-start gap-8 md:gap-12 desktop:gap-16 ${hasPortrait ? "md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)]" : ""}`}
          >
            {hasPortrait && (
              <AboutPhoto
                src="/images/author.jpg"
                alt="Кирилл Барабанщиков идёт по городской улице"
                width={3072}
                height={4080}
                sizes="(min-width: 1280px) 467px, (min-width: 768px) 40vw, calc(100vw - 32px)"
                eager
              />
            )}
            <div className="min-w-0 max-w-3xl">
              <p className="text-xl leading-relaxed">
                Меня зовут <strong className="font-semibold">Кирилл Барабанщиков</strong>.
                Я разрабатываю цифровые продукты, автоматизирую бизнес-процессы
                и изучаю, как искусственный интеллект может помогать людям.
                К этой работе я пришёл через юридическую практику, работу
                с бизнесом и многолетнюю мечту о программировании.
              </p>

              <section aria-labelledby="about-path" className="mt-8 border-t border-border pt-8">
                <h2 id="about-path" className="text-2xl font-semibold tracking-tight md:text-3xl">
                  Путь к разработке
                </h2>
                <div className="mt-5 space-y-4 text-text-muted">
                  <p>
                    С рождения у меня слабое зрение. В начале двухтысячных доступ
                    к ассистивным технологиям и информации о них был для меня
                    ограничен, а круг возможных профессий казался небольшим.
                    Среда, в которой я рос, тоже не подталкивала к техническому
                    образованию. Я выбрал гуманитарное направление и окончил
                    юридический факультет Удмуртского государственного
                    университета в Ижевске.
                  </p>
                  <p>
                    Уже на втором курсе я узнал о программах экранного доступа,
                    которые позволяют людям с нарушением зрения пользоваться
                    компьютером. Тогда появилась мысль изменить направление
                    учёбы, но решиться на такой поворот я не смог. Продолжил
                    образование, начал работать, а мечту о разработке отложил.
                  </p>
                  <p>
                    За пятнадцать лет юридической практики я занимался вопросами
                    B2B, договорами и интеллектуальной собственностью. Параллельно
                    вёл направление коммерческой аренды: искал арендаторов,
                    проводил переговоры, согласовывал условия, сопровождал
                    отношения и разрешал споры. Эта работа помогла мне понять,
                    как устроен бизнес, как принимаются решения и что происходит
                    за формальными требованиями и документами.
                  </p>
                  <p>
                    Попытки вернуться к программированию были и в те годы.
                    Я начинал с C++, который оказался для меня слишком сложным
                    на том этапе. До смены профессии эти попытки не довели,
                    но интерес сохранился.
                  </p>
                </div>
              </section>
            </div>
          </div>

          <section aria-labelledby="about-new-start" className="border-t border-border pt-8 md:pt-10">
            <div className="grid items-start gap-8 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.9fr)] md:gap-12 desktop:gap-16">
              <div className="min-w-0">
                <h2 id="about-new-start" className="text-2xl font-semibold tracking-tight md:text-3xl">
                  Возвращение к мечте
                </h2>
                <div className="mt-5 space-y-4 text-text-muted">
                  <p>
                    Всё изменилось в 2022 году, когда я узнал о возможности
                    бесплатно пройти обучение разработке по программе для людей
                    с инвалидностью. В сентябре подал заявление и оказался
                    на курсе Python-разработчика в Яндекс Практикуме.
                  </p>
                  <p>
                    Девять месяцев учёбы стали одним из самых сложных
                    и интересных периодов моей жизни. К концу курса я уже
                    понимал, что хочу продолжать, и решил сразу начать
                    собственный проект. Так появился Telegram-бот
                    «Работа для всех», который помогал людям с инвалидностью
                    искать работу.
                  </p>
                  <p>
                    Тема выросла из моего опыта. Я активно участвую в жизни
                    Всероссийского общества слепых, занимался вопросами
                    квотирования рабочих мест и консультированием по трудовым
                    правам. В проекте соединились знакомая мне проблема,
                    юридические знания и новые возможности разработки.
                  </p>
                  <p>
                    С «Работой для всех» меня стали приглашать на презентации
                    и практические семинары. Проект дал возможность обсуждать
                    свою работу с людьми и показывать её за пределами учебных
                    заданий. Думаю, именно наличие собственного продукта помогло
                    мне найти первую работу в разработке — в компании BIOCARD.
                  </p>
                  <p>
                    Сегодня у меня более двух лет коммерческого опыта.
                    Я развиваю сервисы клиентского обслуживания, интеграции
                    и внутренние инструменты компании. Разбираюсь в потребностях
                    сотрудников, проектирую архитектуру, пишу код, участвую
                    во внедрении и сопровождаю решения после запуска. Обратная
                    связь от людей помогает понять, что действительно работает
                    и какие изменения нужны дальше.
                  </p>
                </div>
              </div>
              <AboutPhoto
                src="/images/about/speaking.jpg"
                alt="Кирилл Барабанщиков выступает с микрофоном перед участниками встречи"
                width={1334}
                height={2000}
                sizes="(min-width: 1280px) 467px, (min-width: 768px) 40vw, calc(100vw - 32px)"
                caption="Делиться своим опытом и обсуждать его с людьми — тоже часть пути."
              />
            </div>
          </section>

          <section aria-labelledby="about-work-for-everyone" className="border-t border-border pt-8 md:pt-10">
            <div className="mx-auto max-w-3xl">
              <h2 id="about-work-for-everyone" className="text-2xl font-semibold tracking-tight md:text-3xl">
                Работа для всех
              </h2>
              <div className="mt-5 space-y-4 text-text-muted">
                <p>
                  <a
                    href="https://work-for-everyone.ru/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent underline underline-offset-4 hover:decoration-2"
                  >
                    «Работа для всех»
                    <span className="sr-only"> (в новой вкладке)</span>
                  </a>{" "}
                  продолжает развиваться. Начавшись
                  с Telegram-бота, проект вырос в платформу с поиском вакансий,
                  помощью в подготовке резюме и сопроводительных писем.
                  Его частью стал ИИ-помощник «Вера», который помогает
                  разобраться в вопросах трудового права. Для него я развиваю
                  юридическую базу знаний, поиск по нормативным документам
                  и контролируемое обновление их редакций.
                </p>
                <p>
                  Доступность в этом проекте связана с моим собственным опытом.
                  Я знаю, насколько возможность пользоваться инструментом влияет
                  на самостоятельность человека. Поэтому уделяю внимание работе
                  с клавиатурой и скринридером, понятным интерфейсам
                  и объяснениям.
                </p>
              </div>
            </div>
            <div className="mt-8 grid items-start gap-8 md:grid-cols-2">
              <AboutPhoto
                src="/images/about/work-for-everyone.jpg"
                alt="Кирилл представляет «Работу для всех»: рядом экран с названием проекта, перед ним аудитория"
                width={2000}
                height={1334}
                sizes="(min-width: 1280px) 560px, (min-width: 768px) 46vw, calc(100vw - 32px)"
                caption="«Работа для всех»: рассказываю о проекте и задачах, которые он помогает решать."
              />
              <AboutPhoto
                src="/images/about/vera.jpg"
                alt="Выступление рядом со слайдом «Информации много. Понять её сложно» о помощнике «Вера»"
                width={2000}
                height={1334}
                sizes="(min-width: 1280px) 560px, (min-width: 768px) 46vw, calc(100vw - 32px)"
                caption="«Вера» — часть «Работы для всех». Её задача — помогать разбираться в правовой информации."
              />
            </div>
          </section>

          <section aria-labelledby="about-ai" className="mx-auto max-w-3xl border-t border-border pt-8 md:pt-10">
            <h2 id="about-ai" className="text-2xl font-semibold tracking-tight md:text-3xl">
              ИИ и вопросы смысла
            </h2>
            <div className="mt-5 space-y-4 text-text-muted">
              <p>
                Развитие ИИ снова заставляет меня задумываться о профессиональном
                пути: куда двигаться дальше, чему учиться и какую пользу
                приносить людям, бизнесу и обществу.
              </p>
              <p>
                Для меня всё большее значение приобретают вопросы: для кого
                мы создаём продукт, какую проблему решаем и как поймём, что
                решение помогло. Чтобы эффективно применять ИИ, нужно разбираться
                в предметной области, понимать человеческие потребности,
                задавать ограничения и проверять результат. В этом я вижу
                продолжение своего опыта — юридического, делового и технического.
              </p>
            </div>
          </section>

          <section aria-labelledby="about-learning" className="border-t border-border pt-8 md:pt-10">
            <div className="grid items-start gap-8 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.9fr)] md:gap-12 desktop:gap-16">
              <div className="min-w-0">
                <h2 id="about-learning" className="text-2xl font-semibold tracking-tight md:text-3xl">
                  Продолжать учиться
                </h2>
                <div className="mt-5 space-y-4 text-text-muted">
                  <p>
                    В 2026 году я прошёл обучение в школе проджект-менеджеров
                    БФ «ДЕЙСТВУЙ», организованной совместно с Нетологией.
                    Особенно ценной для меня оказалась практическая часть курса.
                    Я продолжаю развиваться в управлении IT-проектами
                    и соединять этот опыт с разработкой.
                  </p>
                  <p>
                    Мне по-прежнему интересны философия, литература и история.
                    Вместе с программированием и информатикой они помогают
                    смотреть на задачи с разных сторон, искать причины
                    происходящего и задумываться о последствиях решений.
                  </p>
                </div>
              </div>
              <AboutPhoto
                src="/images/about/learning.jpg"
                alt="Кирилл у экрана со слайдом «Пробовать. Ошибаться. Учиться. Расти.» и схемой пути от учёбы к практике"
                width={2000}
                height={1334}
                sizes="(min-width: 1280px) 467px, (min-width: 768px) 40vw, calc(100vw - 32px)"
                caption="Пробовать, ошибаться, учиться, расти. Этот путь продолжается."
              />
            </div>
          </section>

          <section aria-labelledby="about-writing" className="mx-auto max-w-3xl border-t border-border pt-8 md:pt-10">
            <h2 id="about-writing" className="text-2xl font-semibold tracking-tight md:text-3xl">
              Зачем я веду этот сайт
            </h2>
            <p className="mt-5 text-text-muted">
              Этот сайт я создал, чтобы собирать в одном месте то, что мне
              интересно: разработку, ИИ и изменения, которые технологии приносят
              в нашу жизнь. Здесь я хочу делиться практикой, разбирать события
              через собственный опыт и мировоззрение, обсуждать идеи и проверять
              их в работе.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/projects" className="button-primary">
                Мои проекты
              </Link>
              <Link href="/blog" className="button-secondary">
                Читать блог
              </Link>
            </div>
          </section>

          <section aria-labelledby="about-contacts" className="mx-auto max-w-3xl border-t border-border pt-8 md:pt-10">
            <h2 id="about-contacts" className="text-2xl font-semibold tracking-tight md:text-3xl">
              Будем на связи
            </h2>
            <p className="mt-5 text-text-muted">
              Если хотите обсудить проект, задать вопрос или поделиться идеей —
              напишите мне.
            </p>
            <address className="mt-6 not-italic">
              <ul className="flex flex-wrap gap-x-8 gap-y-3">
                <li className="min-w-0">
                  <a href="tel:+79124646606" className="text-link">
                    <Phone size={20} strokeWidth={1.75} aria-hidden="true" className="shrink-0" />
                    <span>+7 (912) 464-66-06</span>
                  </a>
                </li>
                <li className="min-w-0">
                  <a href="mailto:bks2408@mail.ru" className="text-link">
                    <Mail size={20} strokeWidth={1.75} aria-hidden="true" className="shrink-0" />
                    <span>bks2408@mail.ru</span>
                  </a>
                </li>
              </ul>
              <ul className="mt-6 grid gap-3 md:grid-cols-3">
                {socialLinks.map((social) => (
                  <li key={social.href} className="min-w-0">
                    <a
                      href={social.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex h-full min-h-[88px] items-center justify-between gap-3 rounded-card border border-border bg-surface p-4 hover:border-accent"
                    >
                      <span className="min-w-0">
                        <span className="block font-semibold">{social.title}</span>
                        <span className="mt-1 block text-sm text-text-muted">{social.description}</span>
                        <span className="sr-only"> (в новой вкладке)</span>
                      </span>
                      <ArrowUpRight size={20} strokeWidth={1.75} aria-hidden="true" className="shrink-0 text-accent" />
                    </a>
                  </li>
                ))}
              </ul>
            </address>
          </section>
        </div>
      </article>
    </Container>
  );
}
