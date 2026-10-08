# Локальные шрифты

Variable WOFF2 получены из официальных репозиториев авторов и сокращены
для латиницы и русского текста сайта. Это изменённые наборы символов,
не новые официальные версии шрифтов. `src/app/layout.tsx` подключает их
через `next/font/local` с `display: swap`; сборка не обращается к Google Fonts.

| Файл | Версия исходника | Вес | Исходник → subset | Лицензия |
| --- | --- | --- | --- | --- |
| `InterVariable.woff2` | 4.001; git-9221beed3 | 100–900 | 352 240 → 172 888 байт | [SIL OFL 1.1](Inter-OFL.txt) |
| `JetBrainsMonoVariable.woff2` | 2.305 | 100–800 | 113 672 → 63 700 байт | [SIL OFL 1.1](JetBrainsMono-OFL.txt) |

Оба файла имеют прямое начертание. Inter также сохраняет исходную ось
оптического размера `opsz` 14–32. Семейства, оси, вертикальные метрики,
ширины и контуры оставленных глифов, hinting и применимые OpenType-функции
сохранены. Курсивные файлы раньше не подключались и здесь не добавлены.
Общий размер сокращён с 465 912 до 236 588 байт (49,2%).

Источники, закреплённые на конкретных ревизиях:

- Inter: [файл](https://raw.githubusercontent.com/rsms/inter/353b61b9f4430d5f420d56605a6e7993e0941470/docs/font-files/InterVariable.woff2),
  [лицензия](https://github.com/rsms/inter/blob/353b61b9f4430d5f420d56605a6e7993e0941470/LICENSE.txt).
- JetBrains Mono: [файл](https://raw.githubusercontent.com/JetBrains/JetBrainsMono/19371302b95d218af43299bce79ddbddd0bc364d/fonts/webfonts/JetBrainsMono%5Bwght%5D.woff2),
  [лицензия](https://github.com/JetBrains/JetBrainsMono/blob/19371302b95d218af43299bce79ddbddd0bc364d/OFL.txt).
  Имя локального файла упрощено.

Обе исходные лицензии и уведомления об авторских правах сохранены.
Полученные subset-файлы также распространяются под SIL OFL 1.1.
Названия и авторы указаны для атрибуции исходников, без утверждения,
что авторы выпустили или одобрили эти subset-файлы.

## Набор символов

Базовый набор соответствует назначению прежних `latin` и `cyrillic`
в `next/font/google`: латиница, русские буквы с `Ё/ё`, комбинируемые
знаки, пунктуация, валюты и стрелки. Историческая кириллица и весь
Unicode Math/Dingbats не включаются автоматически.

```text
0000-00FF,0131,0152-0153,02BB-02BC,02C6,02DA,02DC,0300-036F,0400-045F,0490-0491,04B0-04B1,2000-206F,20A0-20CF,2113,2116,2190-21FF,2212,2260,2264-2265,FEFF,FFFD
```

К нему добавляется объединение всех символов из `frontend/src/**/*.tsx`
и `backend/content/**/*.md`. Для текущих файлов это 164 кодовые точки
из 65 TSX и 13 Markdown-файлов; все они уже входят в базовые диапазоны.
Сохраняются только глифы, имевшиеся в оригинале: диапазоны не обещают
поддержку отсутствовавших в исходных шрифтах символов.

## Воспроизведение

Инструменты: Python 3.12.9, FontTools 4.66.1, Brotli 1.2.0, Zopfli 0.4.3.
Это инструменты подготовки ассетов, не зависимости приложения.
Следующие команды PowerShell выполняются из корня репозитория. Исходники
скачиваются по закреплённым выше URL в `$fontWork/originals`; перед
обработкой нужно сверить их SHA-256 с таблицей ниже.

```powershell
$fontWork = Join-Path $env:TEMP 'bks-lab-font-subset'
New-Item -ItemType Directory -Force "$fontWork/originals" | Out-Null
python -m venv "$fontWork/tools"
$fontPython = "$fontWork/tools/Scripts/python.exe"
& $fontPython -m pip install 'fonttools[woff]==4.66.1' 'Brotli==1.2.0' 'zopfli==0.4.3'

@'
from pathlib import Path
import sys
files = sorted(Path("frontend/src").rglob("*.tsx")) + sorted(Path("backend/content").rglob("*.md"))
used = {ord(char) for file in files for char in file.read_text(encoding="utf-8-sig")}
Path(sys.argv[1]).write_text(",".join(f"U+{cp:04X}" for cp in sorted(used)) + "\n", encoding="ascii")
'@ | & $fontPython - "$fontWork/used-codepoints.txt"

$fontArgs = @(
  '--unicodes=0000-00FF,0131,0152-0153,02BB-02BC,02C6,02DA,02DC,0300-036F,0400-045F,0490-0491,04B0-04B1,2000-206F,20A0-20CF,2113,2116,2190-21FF,2212,2260,2264-2265,FEFF,FFFD',
  "--unicodes-file=$fontWork/used-codepoints.txt",
  '--flavor=woff2', '--layout-features=*', '--layout-scripts=*',
  '--glyph-names', '--symbol-cmap', '--legacy-cmap', '--legacy-kern',
  '--notdef-glyph', '--notdef-outline', '--recommended-glyphs',
  '--name-IDs=*', '--name-languages=*', '--name-legacy', '--hinting',
  '--no-recalc-bounds', '--no-recalc-timestamp',
  '--no-recalc-average-width', '--no-harfbuzz-repacker'
)
foreach ($fontName in @('InterVariable.woff2', 'JetBrainsMonoVariable.woff2')) {
  & $fontPython -m fontTools.subset "$fontWork/originals/$fontName" "--output-file=$fontWork/$fontName" @fontArgs
  if ($LASTEXITCODE -ne 0) { throw "Subsetting failed: $fontName" }
}
```

После обработки сверяются оси `fvar/avar/MVAR/STAT`, семейства,
copyright/license-записи, вертикальные метрики, `hmtx`, глобальный и
поглифовый hinting. Проверены ширины и контуры всех 1505 оставленных
глифов Inter в шести сочетаниях `wght/opsz` и 718 глифов JetBrains Mono
в трёх значениях `wght` (минимум, default, максимум). ASCII и русские
буквы сохранены полностью. FontTools удалил только неиспользуемое
название функции Inter `Alternate capital sharp S` (name ID 297).

Новые языки или символы вне набора требуют повторной подготовки ассетов
из полных исходников и проверки покрытия до замены файлов в репозитории.

## SHA-256

Полные исходники:

```text
693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3  InterVariable.woff2
31ec365b93e4bad6f202ce23352a56d01ca4462b2afc782ed2cf6fa42ca9ac0e  JetBrainsMonoVariable.woff2
```

Subset-файлы в этом каталоге:

```text
ca5ca06d4d09f1f3411111cdf94bc6651882fc2f8f25473c94eca1184b380ffb  InterVariable.woff2
535931ea91f3fd2be3be7a728d765d50582c3a1b099356d0c740e68db33a9723  JetBrainsMonoVariable.woff2
```
