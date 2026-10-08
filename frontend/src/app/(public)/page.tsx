import { HomeContent } from "@/components/content/HomeContent";
import { pageMetadata } from "@/lib/content";

export const revalidate = 300;
export const metadata = {
  ...pageMetadata(
    "Разработка, AI, проекты и идеи",
    "Личный сайт BKS Lab: проекты, статьи и заметки о современной разработке, управлении и искусственном интеллекте.",
    "/",
  ),
  title: { absolute: "BKS Lab — разработка, AI, проекты и идеи" },
};

export default HomeContent;
