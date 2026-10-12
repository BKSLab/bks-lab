import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { SourceCatalogueEntry } from "@/lib/news-api/catalogue";

export const sourceCatalogue: SourceCatalogueEntry[] = JSON.parse(readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../../backend/src/data/news_source_catalogue.json"), "utf8",
));
