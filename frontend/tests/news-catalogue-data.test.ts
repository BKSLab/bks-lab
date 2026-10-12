import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { sourceGroups, type SourceCatalogueEntry, type SourceCatalogueGroup } from "@/lib/news-api/catalogue";
import { sourceCatalogue } from "./news-catalogue-fixtures";

const sectionGroups: Record<number, SourceCatalogueGroup> = {
  1: "labs", 2: "engineering", 3: "business", 4: "society", 5: "authors", 6: "russian", 7: "tools",
};
const expectedCounts = { labs: 15, engineering: 15, business: 11, society: 16, authors: 16, russian: 15, tools: 10 };

interface ReferenceRow {
  group: SourceCatalogueGroup;
  name: string;
  url: string;
  urls: string[];
  connection: string;
  description: string;
  priority: "A" | "B" | "C" | null;
}

function urlsIn(value: string): string[] {
  return [...value.matchAll(/https?:\/\/[^\s`|<>]+/g)].map(match => match[0]);
}

function readResearchTables() {
  const markdown = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../../search_news/BKS_Lab_AI_Sources_Research.md"), "utf8");
  const groups: typeof sourceGroups = [];
  const rows: ReferenceRow[] = [];
  let group: SourceCatalogueGroup | undefined;
  for (const line of markdown.split(/\r?\n/)) {
    const section = line.match(/^## (\d+)\. (.+)$/);
    if (section) {
      group = sectionGroups[Number(section[1])];
      if (group) groups.push({ id: group, title: section[2] });
      continue;
    }
    if (!group || !line.startsWith("|") || !line.includes("http")) continue;
    const cells = line.slice(1, line.lastIndexOf("|")).split("|").map(cell => cell.trim());
    if (group === "authors" || group === "tools") {
      expect(cells).toHaveLength(4);
      const connection = cells[group === "authors" ? 3 : 2];
      const priority = group === "authors" ? connection.match(/(?:^|,\s*)([ABC])$/)?.[1] ?? null : null;
      rows.push({ group, name: cells[0], url: cells[1], urls: urlsIn(line), connection, description: cells[group === "authors" ? 2 : 3], priority: priority as ReferenceRow["priority"] });
    } else {
      expect(cells).toHaveLength(5);
      rows.push({ group, name: cells[1], url: cells[2], urls: urlsIn(line), connection: cells[3], description: cells[4], priority: cells[0] as ReferenceRow["priority"] });
    }
  }
  return { groups, rows };
}

const reference = readResearchTables();
const key = (entry: { group: SourceCatalogueGroup; name: string }) => `${entry.group}/${entry.name}`;
const entryUrls = (entry: SourceCatalogueEntry) => [...new Set([entry.url, ...(entry.feedUrl ? [entry.feedUrl] : []), ...entry.extraUrls])];

describe("research source catalogue data", () => {
  it("contains exactly one entry for every table row in all seven original groups", () => {
    expect(reference.rows).toHaveLength(98);
    expect(sourceCatalogue).toHaveLength(98);
    expect(sourceGroups).toEqual(reference.groups);
    expect(sourceCatalogue.map(key).sort()).toEqual(reference.rows.map(key).sort());
    for (const [group, count] of Object.entries(expectedCounts)) {
      expect(sourceCatalogue.filter(entry => entry.group === group), group).toHaveLength(count);
    }
    expect(sourceCatalogue.filter(entry => entry.name === "Simon Willison").map(entry => entry.group)).toEqual(["engineering", "authors"]);
  });

  it("preserves every name, primary URL, description, connection note and explicit priority", () => {
    for (const row of reference.rows) {
      const entries = sourceCatalogue.filter(entry => key(entry) === key(row));
      expect(entries, key(row)).toHaveLength(1);
      expect(entries[0], key(row)).toMatchObject({ group: row.group, name: row.name, url: row.url, connection: row.connection, description: row.description, priority: row.priority });
    }
    expect(sourceCatalogue.find(entry => entry.group === "authors" && entry.name === "Andrej Karpathy")?.priority).toBeNull();
    expect(sourceCatalogue.filter(entry => entry.group === "tools").every(entry => entry.priority === null)).toBe(true);
  });

  it("retains every documented URL without adding guessed endpoints", () => {
    const simonFeed = urlsIn(reference.rows.find(row => row.group === "engineering" && row.name === "Simon Willison")!.connection)[0];
    for (const row of reference.rows) {
      const entry = sourceCatalogue.find(value => key(value) === key(row))!;
      const allowed = new Set(row.urls);
      if (row.group === "authors" && row.name === "Simon Willison") allowed.add(simonFeed);
      const actual = entryUrls(entry);
      expect(actual, key(row)).toEqual(expect.arrayContaining([...new Set(row.urls)]));
      expect(actual.every(url => allowed.has(url)), key(row)).toBe(true);
      expect(new Set(entry.extraUrls).size, key(row)).toBe(entry.extraUrls.length);
      for (const url of actual) {
        const parsed = new URL(url);
        expect(["http:", "https:"]).toContain(parsed.protocol);
        expect(parsed.hostname).not.toBe("");
        expect(parsed.username + parsed.password).toBe("");
      }
    }
    expect(sourceCatalogue.find(entry => entry.id === "eng-simon")?.extraUrls).toContain("https://simonwillison.net/atom/everything/");
    expect(sourceCatalogue.find(entry => entry.id === "tools-hn-algolia")?.extraUrls).toContain("https://hn.algolia.com/api/v1/search_by_date?query=LLM&tags=story");
  });

  it("uses unique stable ASCII IDs across repeated authors and source groups", () => {
    const ids = sourceCatalogue.map(entry => entry.id);
    expect(new Set(ids).size).toBe(98);
    for (const id of ids) {
      expect(id).toMatch(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/);
      expect(id.length).toBeLessThanOrEqual(40);
    }
    expect(sourceCatalogue.find(entry => entry.group === "engineering" && entry.name === "Simon Willison")?.id).toBe("eng-simon");
    expect(sourceCatalogue.find(entry => entry.group === "authors" && entry.name === "Simon Willison")?.id).toBe("authors-simon");
  });

  it("marks RSS only for documented feed addresses and the allowed Simon duplicate", () => {
    const knownFeeds = [
      "labs/Hugging Face Blog", "engineering/Simon Willison", "engineering/arXiv cs.AI", "engineering/arXiv cs.CL",
      "engineering/arXiv cs.LG", "engineering/Martin Fowler", "authors/Simon Willison", "tools/arXiv RSS",
    ];
    expect(sourceCatalogue.filter(entry => entry.mode === "rss").map(key).sort()).toEqual(knownFeeds.sort());
    for (const entry of sourceCatalogue) {
      if (entry.mode === "rss") {
        expect(entry.feedUrl, key(entry)).toBeTruthy();
        expect(new URL(entry.feedUrl!).protocol).toBe("https:");
        expect(new URL(entry.feedUrl!).hash).toBe("");
        const row = reference.rows.find(value => key(value) === key(entry))!;
        if (entry.group === "tools") expect(entry.feedUrl).toBe(row.url);
        else if (entry.group !== "authors") expect(urlsIn(row.connection)).toContain(entry.feedUrl);
      } else {
        expect(entry.feedUrl, key(entry)).toBeUndefined();
      }
    }
    expect(sourceCatalogue.find(entry => entry.id === "labs-openai")?.mode).toBe("auto");
    expect(sourceCatalogue.find(entry => entry.id === "labs-mistral")?.mode).toBe("auto");
  });

  it("keeps API tools and archival reading separate from connectable RSS feeds", () => {
    const tools = sourceCatalogue.filter(entry => entry.group === "tools");
    expect(tools.filter(entry => entry.mode === "api")).toHaveLength(8);
    expect(tools.find(entry => entry.name === "HN RSS")).toMatchObject({ mode: "read", url: "https://hnrss.org/", extraUrls: [] });
    expect(tools.find(entry => entry.name === "arXiv RSS")).toMatchObject({ mode: "rss", feedUrl: "https://rss.arxiv.org/rss/cs.AI" });
    const archivedAuthors = ["Geoffrey Hinton", "Yann LeCun", "Richard Sutton", "Jürgen Schmidhuber"];
    for (const name of archivedAuthors) expect(sourceCatalogue.find(entry => entry.group === "authors" && entry.name === name)?.mode, name).toBe("read");
    for (const entry of sourceCatalogue.filter(entry => entry.mode === "api" || entry.mode === "read")) expect(entry.feedUrl, key(entry)).toBeUndefined();
    expect(sourceCatalogue.find(entry => entry.id === "authors-karpathy")?.mode).toBe("auto");
  });

  it("identifies explicit commercial suppliers without treating personal authors as vendor channels", () => {
    expect(sourceCatalogue.filter(entry => entry.group === "labs").every(entry => entry.vendor)).toBe(true);
    for (const id of ["eng-langchain", "eng-llamaindex", "eng-github", "biz-ms-worklab", "biz-ibm", "ru-sber", "ru-yandex", "ru-tbank"]) {
      expect(sourceCatalogue.find(entry => entry.id === id)?.vendor, id).toBe(true);
    }
    expect(sourceCatalogue.filter(entry => entry.group === "authors").every(entry => !entry.vendor)).toBe(true);
  });
});
