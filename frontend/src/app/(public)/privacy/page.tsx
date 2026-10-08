import Link from "next/link";
import { Breadcrumbs } from "@/components/content/Breadcrumbs";
import { Container } from "@/components/layout/Container";
import { adsConfigured } from "@/lib/ads";
import { contactEmail } from "@/lib/contact";
import { pageMetadata } from "@/lib/content";

export const metadata = pageMetadata(
  "Политика конфиденциальности",
  "Какие данные использует BKS Lab для обратной связи, подписки и статистики и как обратиться по вопросам данных.",
  "/privacy",
);

export default function PrivacyPage() {
  const email = contactEmail();
  return (
    <Container className="pb-20 pt-8">
      <Breadcrumbs items={[{ title: "Политика конфиденциальности" }]} />
      <div className="mx-auto max-w-[72ch]">
        <h1 className="page-title">Политика конфиденциальности</h1>
        <p className="mt-6 text-text-muted">
          BKS Lab — личный сайт с проектами, статьями и заметками. На этой странице
          описано, какие данные сайт использует для своей работы.
        </p>
        <section className="mt-10 space-y-4">
          <h2 className="text-2xl font-semibold">Обратная связь</h2>
          <p>
            Когда вы отправляете форму «Связаться», имя, email и текст сообщения
            передаются автору через почтовую службу. Email нужен для ответа.
            В базе данных сайта обращения не сохраняются; отправленное сообщение
            остаётся в почтовой переписке. Не включайте в сообщение пароли и другие
            сведения, которые не нужны для ответа.
          </p>
        </section>
        <section className="mt-10 space-y-4">
          <h2 className="text-2xl font-semibold">Подписка</h2>
          <p>
            Форма подписки сохраняет email и дату подписки в базе данных сайта.
            Адрес доступен автору и предназначен для уведомлений о новых статьях.
            Рассылка пока не запущена. Повторная отправка того же адреса не создаёт
            ещё одну подписку.
          </p>
          <p>
            Для удаления адреса из списка напишите автору через контакты ниже.
            Укажите email, который использовали для подписки.
          </p>
        </section>
        <section className="mt-10 space-y-4">
          <h2 className="text-2xl font-semibold">Статистика и защита сайта</h2>
          <p>
            Сайт считает просмотры публичных страниц: сохраняет время, путь
            страницы, якорь заметки при его наличии и домен сайта, с которого вы
            пришли. Поисковые параметры и полный адрес источника перехода в
            статистике не сохраняются.
          </p>
          <p>
            Для подсчёта посетителей используется меняющийся каждый день код,
            вычисленный на основе IP-адреса. Исходные IP-адрес и сведения о браузере
            в таблице просмотров не сохраняются. IP также используется для
            ограничения частоты отправки форм и защиты от спама.
          </p>
          <p>
            Технические журналы сервера могут содержать сведения о запросах,
            необходимые для диагностики ошибок и защиты сайта.
          </p>
        </section>
        <section className="mt-10 space-y-4">
          <h2 className="text-2xl font-semibold">Настройки браузера и cookie</h2>
          <p>
            Выбранная вами тема сохраняется локально в браузере, чтобы применить
            её при следующем посещении. Удалить настройку можно, очистив данные
            сайта в браузере. Для входа автора в закрытую админку используется
            сессионная cookie; для чтения публикаций вход не нужен.
          </p>
        </section>
        <section className="mt-10 space-y-4">
          <h2 className="text-2xl font-semibold">Реклама</h2>
          {adsConfigured() ? (
            <p>
              В блоге, в конце статей и в ленте заметок могут загружаться блоки
              Рекламной сети Яндекса. При загрузке рекламного кода браузер
              обращается к серверам Яндекса. Обработку данных этим сервисом
              описывает <a className="text-accent underline underline-offset-4" href="https://yandex.ru/legal/confidential/">политика конфиденциальности Яндекса</a>.
            </p>
          ) : <p>Рекламные блоки отключены. Код Рекламной сети Яндекса не загружается.</p>}
        </section>
        <section className="mt-10 space-y-4">
          <h2 className="text-2xl font-semibold">Вопросы о данных</h2>
          <p>
            Чтобы уточнить использование данных, исправить или удалить переданные
            сведения либо отказаться от подписки, обратитесь к автору{email ? (
              <> по адресу <a className="break-all text-accent underline underline-offset-4" href={`mailto:${email}`}>{email}</a></>
            ) : <> через <Link className="text-accent underline underline-offset-4" href="/contacts">страницу контактов</Link></>}.
            Для поиска обращения укажите использованный email, без паролей и
            документов.
          </p>
        </section>
      </div>
    </Container>
  );
}
