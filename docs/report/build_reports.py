#!/usr/bin/env python3
"""
Генерация PDF-отчётов по домашним заданиям № 1 и № 2 (компактная версия).

Запуск:  python build_reports.py
"""

import os
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)

# --------------------------------------------------------------------------- config

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent

REPO_URL = "https://github.com/Lekko8/mifi_vo_HW"
IMAGE = "ghcr.io/lekko8/mifi_vo_hw"
REPORT_DATE = os.environ.get("REPORT_DATE", "23 ноября 2026 г.")

WORKFLOW_FILE = ROOT / ".github" / "workflows" / "ci-cd.yml"
DOCKERFILE = ROOT / "Dockerfile"

PAGE_W, PAGE_H = A4
MARGIN_L, MARGIN_R = 20 * mm, 18 * mm
MARGIN_T, MARGIN_B = 18 * mm, 16 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

ACCENT = colors.HexColor("#1f4f9c")
GREY = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#eef2f9")
BORDER = colors.HexColor("#d5dce7")
CODE_BG = colors.HexColor("#f7f9fc")

# --------------------------------------------------------------------------- fonts

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def register_fonts() -> None:
    faces = {"Arial": "arial.ttf", "Arial-Bold": "arialbd.ttf", "Consolas": "consola.ttf"}
    for name, filename in faces.items():
        path = FONT_DIR / filename
        if not path.exists():
            sys.exit(f"Не найден шрифт {path}")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        "Arial", normal="Arial", bold="Arial-Bold", italic="Arial", boldItalic="Arial-Bold"
    )
    pdfmetrics.registerFontFamily(
        "Consolas", normal="Consolas", bold="Consolas", italic="Consolas", boldItalic="Consolas"
    )


# --------------------------------------------------------------------------- styles

S = {}


def init_styles() -> None:
    S["title"] = ParagraphStyle(
        "title", fontName="Arial-Bold", fontSize=18, leading=23, textColor=ACCENT, spaceAfter=5,
    )
    S["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Arial", fontSize=10.5, leading=15, textColor=GREY, spaceAfter=10,
    )
    S["kicker"] = ParagraphStyle(
        "kicker", fontName="Arial-Bold", fontSize=9, leading=12, textColor=ACCENT, spaceAfter=3,
    )
    S["h1"] = ParagraphStyle(
        "h1", fontName="Arial-Bold", fontSize=13, leading=17, textColor=ACCENT,
        spaceBefore=11, spaceAfter=4, keepWithNext=1,
    )
    S["h2"] = ParagraphStyle(
        "h2", fontName="Arial-Bold", fontSize=10.8, leading=14,
        textColor=colors.HexColor("#20304a"), spaceBefore=8, spaceAfter=3, keepWithNext=1,
    )
    S["body"] = ParagraphStyle(
        "body", fontName="Arial", fontSize=9.8, leading=13.8, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#1b2432"), spaceAfter=5,
    )
    S["bullet"] = ParagraphStyle(
        "bullet", parent=S["body"], leftIndent=13, bulletIndent=3, spaceAfter=2,
    )
    S["note"] = ParagraphStyle(
        "note", parent=S["body"], fontSize=8.8, leading=12.5, textColor=GREY,
        leftIndent=13, bulletIndent=3,
    )
    S["code_line"] = ParagraphStyle(
        "code_line", fontName="Consolas", fontSize=7.2, leading=8.9,
        textColor=colors.HexColor("#14202e"),
    )
    S["th"] = ParagraphStyle(
        "th", fontName="Arial-Bold", fontSize=8.3, leading=10.5, textColor=colors.HexColor("#20304a"),
    )
    S["td"] = ParagraphStyle(
        "td", fontName="Arial", fontSize=8.3, leading=11, textColor=colors.HexColor("#1b2432"),
    )
    S["td_mono"] = ParagraphStyle("td_mono", parent=S["td"], fontName="Consolas", fontSize=7.9)
    S["meta_key"] = ParagraphStyle(
        "meta_key", fontName="Arial-Bold", fontSize=9, leading=13, textColor=GREY,
    )
    S["meta_val"] = ParagraphStyle("meta_val", fontName="Arial", fontSize=9, leading=13)


# --------------------------------------------------------------------------- helpers


def rich(text: str) -> str:
    value = escape(text)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`(.+?)`", r'<font name="Consolas" size="8.3">\1</font>', value)
    return value


def p(text: str) -> Paragraph:
    return Paragraph(rich(text), S["body"])


def h1(text: str, number: str | None = None) -> Paragraph:
    return Paragraph(rich((f"{number}. " if number else "") + text), S["h1"])


def h2(text: str, number: str | None = None) -> Paragraph:
    return Paragraph(rich((f"{number} " if number else "") + text), S["h2"])


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(rich(item), S["bullet"], bulletText="•") for item in items]


def code_block(text: str) -> list[Flowable]:
    """Моноширинный блок: переносит длинные строки и разбивается по страницам построчно."""
    wrapped = []
    limit = 108
    for line in text.replace("\r\n", "\n").replace("\t", "    ").rstrip("\n").split("\n"):
        if len(line) <= limit:
            wrapped.append(line if line.strip() else " ")
            continue
        indent = " " * 4
        current = line
        while len(current) > limit:
            cut = current.rfind(" ", 0, limit)
            if cut < limit // 2:
                cut = limit
            wrapped.append(current[:cut] if current[:cut].strip() else " ")
            current = indent + current[cut:].lstrip()
        wrapped.append(current if current.strip() else " ")

    rows = [[XPreformatted(escape(line), S["code_line"])] for line in wrapped]
    block = Table(rows, colWidths=[CONTENT_W], hAlign="LEFT", splitByRow=1)
    block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0.3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ]
        )
    )
    return [Spacer(1, 2), block, Spacer(1, 7)]


def table(rows: list[list[str]], widths: list[float], mono_col: int | None = None) -> Table:
    data = []
    for row_index, row in enumerate(rows):
        cells = []
        for col_index, cell in enumerate(row):
            if row_index == 0:
                style = S["th"]
            elif mono_col is not None and col_index == mono_col:
                style = S["td_mono"]
            else:
                style = S["td"]
            cells.append(Paragraph(rich(cell), style))
        data.append(cells)

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    # Таблица переносится на следующую страницу целиком: одна «оторванная» строка
    # под заголовком выглядит хуже, чем небольшой отступ внизу страницы.
    return KeepTogether(t)


class ScreenshotBox(Flowable):
    def __init__(self, caption: str, height: float = 190):
        super().__init__()
        self.caption = caption
        self.box_height = height
        self.width = CONTENT_W

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return avail_width, self.box_height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#9aa4b2"))
        canvas.setDash(3, 3)
        canvas.setFillColor(colors.HexColor("#fbfcfe"))
        canvas.rect(0, 0, self.width, self.box_height, stroke=1, fill=1)

        canvas.setFillColor(GREY)
        canvas.setFont("Arial", 9)
        max_width = self.width - 24
        lines: list[str] = []
        current = ""
        for word in ("СКРИНШОТ: " + self.caption).split():
            candidate = (current + " " + word).strip()
            if pdfmetrics.stringWidth(candidate, "Arial", 9) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)

        y = self.box_height / 2 + len(lines) * 6 - 4
        for line in lines:
            w = pdfmetrics.stringWidth(line, "Arial", 9)
            canvas.drawString((self.width - w) / 2, y, line)
            y -= 13
        canvas.restoreState()


def screenshot(caption: str, height: float = 190) -> list[Flowable]:
    return [ScreenshotBox(caption, height), Spacer(1, 10)]


def meta_table(pairs: list[tuple[str, str]]) -> Table:
    rows = [
        [Paragraph(rich(key), S["meta_key"]), Paragraph(rich(value), S["meta_val"])]
        for key, value in pairs
    ]
    t = Table(rows, colWidths=[34 * mm, CONTENT_W - 34 * mm], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e6ebf3")),
            ]
        )
    )
    return t


def rule() -> Table:
    t = Table([[""]], colWidths=[CONTENT_W], rowHeights=[2])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)]))
    return t


# --------------------------------------------------------------------------- document


def flatten(items: list) -> list[Flowable]:
    result: list[Flowable] = []
    for item in items:
        if isinstance(item, (list, tuple)):
            result.extend(flatten(list(item)))
        elif item is not None:
            result.append(item)
    return result


def build_document(filename: str, doc_title: str, story: list[Flowable]) -> Path:
    path = OUT_DIR / filename
    doc = BaseDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title=doc_title,
        subject="Домашнее задание по CI/CD",
        creator="build_reports.py",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, CONTENT_W, doc.height, id="body")

    def decorate(canvas, doc_obj):
        if doc_obj.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e3e8f0"))
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_L, PAGE_H - 12.5 * mm, PAGE_W - MARGIN_R, PAGE_H - 12.5 * mm)
        canvas.setFont("Arial", 7.6)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN_L, PAGE_H - 11 * mm, doc_title)
        canvas.line(MARGIN_L, 11.5 * mm, PAGE_W - MARGIN_R, 11.5 * mm)
        canvas.drawString(MARGIN_L, 9 * mm, "Task Tracker · CI/CD в GitHub Actions")
        canvas.drawRightString(PAGE_W - MARGIN_R, 9 * mm, f"стр. {doc_obj.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])
    doc.build(flatten(story))
    return path


def title_page(
    kicker: str,
    title: str,
    subtitle: str,
    meta: list[tuple[str, str]],
    contents: list[str] | None = None,
) -> list[Flowable]:
    flows: list[Flowable] = [
        Spacer(1, 22 * mm),
        Paragraph(rich(kicker), S["kicker"]),
        Paragraph(rich(title), S["title"]),
        Paragraph(rich(subtitle), S["subtitle"]),
        rule(),
        Spacer(1, 10 * mm),
        meta_table(meta),
        Spacer(1, 8 * mm),
    ]
    if contents:
        flows.append(Paragraph(rich("В отчёте:"), S["meta_key"]))
        flows.append(Spacer(1, 2))
        flows.extend(Paragraph(rich(item), S["note"]) for item in contents)
    return flows


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


PIPELINE_DIAGRAM = """  push / pull_request / tag / manual
             │
             ▼
   ┌──────────────────────────────────────────┐
   │ job: build-and-test                      │
   │  1. actions/checkout@v4                  │
   │  2. actions/setup-java@v4 (cache: maven) │
   │  3. mvn -B -ntp verify  → 13 тестов      │
   │  4. actions/upload-artifact@v4 (jar)     │
   └───────────────────┬──────────────────────┘
                       │ needs
                       ▼  (любое событие, кроме pull_request)
   ┌──────────────────────────────────────────┐
   │ job: docker                              │
   │  5. docker/setup-buildx-action@v3        │
   │  6. docker/login-action@v3 → ghcr.io     │
   │  7. docker/metadata-action@v5 (теги)     │
   │  8. docker/build-push-action@v6 (cache)  │
   └───────────────────┬──────────────────────┘
                       ▼
         ghcr.io/lekko8/mifi_vo_hw:latest,
         :sha-<commit>, :1.0.0 (по git-тегу)"""


# --------------------------------------------------------------------------- HW 1


def build_hw1() -> Path:
    story: list[Flowable] = []
    story += title_page(
        "ОТЧЁТ ПО ДОМАШНЕМУ ЗАДАНИЮ № 1",
        "CI/CD в GitHub Actions: сборка, тесты, кэш и артефакты",
        "Проект Task Tracker — REST API на Java 21 / Spring Boot 3.3, "
        "собираемый и публикуемый автоматически",
        [
            ("Проект", "Task Tracker — сервис управления задачами (Java 21, Spring Boot, Maven)"),
            ("Репозиторий", REPO_URL),
            ("CI/CD", "GitHub Actions, файл `.github/workflows/ci-cd.yml`"),
            ("Дата", REPORT_DATE),
        ],
        contents=[
            "1. Выбранный проект и его REST API",
            "2. Ссылка на репозиторий",
            "3. Схема пайплайна и триггеры",
            "4. Job build-and-test: шаги, кэш, артефакт",
            "5. Job docker: используемые actions",
            "6–7. Код ci-cd.yml и результаты запусков",
        ],
    )
    story.append(PageBreak())

    story.append(h1("Выбранный проект", "1"))
    story.append(
        p(
            "Выбран собственный проект **Task Tracker** — веб-сервис на Java, реализующий REST API "
            "для ведения списка задач: создание, просмотр, смена статуса «выполнено» и удаление. "
            "Проект написан с нуля и не повторяет пример из учебного модуля: другой язык и стек "
            "(Java + Spring Boot вместо консольной программы), другой предмет, есть слой сервиса, "
            "обработка ошибок в формате RFC 9457 (Problem Details) и веб-интерфейс."
        )
    )
    story.append(
        p(
            "Стек: **Java 21 (Temurin)**, **Spring Boot 3.3.5**, сборка **Maven** "
            "(`mvn -B -ntp verify`), тесты **JUnit 5 + MockMvc**, 13 штук. Java выбрана потому, что "
            "она же требуется в домашнем задании № 2 (упаковка Java-приложения в Docker), а Maven — "
            "стандартный сборщик, который умеет компилировать, тестировать и собирать исполняемый "
            "fat jar. Проект кроссплатформенный: одинаково собирается на Linux (в CI), macOS и Windows."
        )
    )
    story.append(
        table(
            [
                ["Метод и путь", "Назначение"],
                ["`GET /`", "Веб-страница со списком задач (проверка работы контейнера)"],
                ["`GET /api/tasks`", "Список всех задач, отсортированный по идентификатору"],
                ["`POST /api/tasks`", "Создание задачи: тело `{\"title\": \"...\"}`"],
                ["`PATCH /api/tasks/{id}`", "Изменение статуса: тело `{\"done\": true}`"],
                ["`DELETE /api/tasks/{id}`", "Удаление задачи, ответ 204 No Content"],
                ["`GET /api/info`", "Версия приложения, версия JVM, количество задач"],
                ["`GET /actuator/health`", "Проверка живости: `{\"status\":\"UP\"}`"],
            ],
            [52 * mm, CONTENT_W - 52 * mm],
            mono_col=0,
        )
    )

    story.append(h1("Ссылка на репозиторий", "2"))
    story.append(
        p(
            f"Репозиторий: {REPO_URL}. В нём доступны код приложения, `Dockerfile`, "
            "`.github/workflows/ci-cd.yml`, `README.md` с инструкцией запуска и история успешных "
            "запусков во вкладке **Actions**."
        )
    )

    story.append(h1("Схема пайплайна и триггеры", "3"))
    story.append(
        p(
            "Пайплайн описан одним файлом `.github/workflows/ci-cd.yml` и состоит из двух "
            "последовательных job'ов: `build-and-test` закрывает требования ДЗ 1, `docker` — "
            "требования ДЗ 2. Второй job не запускается, если сборка или тесты упали (`needs`)."
        )
    )
    story += code_block(PIPELINE_DIAGRAM)
    story.append(
        table(
            [
                ["Событие", "Фильтр", "Что выполняется", "Публикация образа"],
                ["`push`", "ветка `main`", "build-and-test + docker", "да"],
                ["`push`", "теги `v*.*.*`", "build-and-test + docker", "да, с semver-тегами"],
                ["`pull_request`", "в `main`", "только build-and-test", "нет"],
                ["`workflow_dispatch`", "—", "build-and-test + docker", "да"],
            ],
            [38 * mm, 30 * mm, 56 * mm, CONTENT_W - 124 * mm],
            mono_col=0,
        )
    )
    story.append(Spacer(1, 3))
    story.append(
        p(
            "Дополнительно объявлена политика `concurrency`: новый запуск в той же ветке отменяет "
            "предыдущий, но только для pull request, чтобы не прерывать публикацию образа на `main`. "
            "Права токена ограничены: `contents: read` на уровне workflow и `packages: write` "
            "только у job'а `docker`."
        )
    )

    story.append(h1("Описание job build-and-test", "4"))
    story.append(
        p(
            "Job выполняется на `ubuntu-latest`, ограничен по времени (`timeout-minutes: 15`) "
            "и состоит из пяти шагов:"
        )
    )
    story.append(
        table(
            [
                ["Шаг", "Action / команда", "Что делает"],
                ["Checkout repository", "`actions/checkout@v4`", "Клонирует репозиторий на runner"],
                [
                    "Set up JDK 21",
                    "`actions/setup-java@v4`",
                    "Ставит Temurin JDK 21 и восстанавливает кэш Maven (`cache: maven`)",
                ],
                ["Build and run tests", "`mvn -B -ntp verify`", "Компиляция, 13 тестов, сборка fat jar"],
                [
                    "Upload build artifact",
                    "`actions/upload-artifact@v4`",
                    "Публикует `target/task-tracker-*.jar` как артефакт запуска",
                ],
                [
                    "Upload test reports",
                    "`actions/upload-artifact@v4`",
                    "Отчёты Surefire выгружаются даже при падении тестов (`if: always()`)",
                ],
            ],
            [38 * mm, 52 * mm, CONTENT_W - 90 * mm],
        )
    )
    story.append(Spacer(1, 4))
    story.append(h2("Кэширование зависимостей", "4.1"))
    story.append(
        p(
            "Кэш настраивается параметром `cache: maven` в `actions/setup-java@v4`: action "
            "вычисляет ключ по хешу `pom.xml`, сохраняет каталог `~/.m2/repository` и "
            "восстанавливает его перед запуском Maven. При изменении зависимостей ключ меняется и "
            "кэш создаётся заново, а при изменении только кода — переиспользуется. Первый запуск "
            "печатает `Cache not found for input keys` и скачивает зависимости, повторный — "
            "`Cache restored from key: ...` и собирается в несколько раз быстрее. Слои Docker-образа "
            "кэшируются отдельно (`cache-from/cache-to: type=gha`) в job'е `docker`."
        )
    )
    story.append(h2("Артефакт и тесты", "4.2"))
    story.append(
        p(
            "Собранный jar публикуется как артефакт `task-tracker-jar-<sha коммита>` и доступен для "
            "скачивания в разделе **Artifacts** в течение 14 дней; параметр `if-no-files-found: error` "
            "не позволяет job'у пройти, если jar не появился. Скачанный архив содержит исполняемый "
            "`task-tracker-1.0.0.jar`, который запускается через `java -jar` без Maven и интернета. "
            "Тесты (6 unit-тестов сервиса и 7 интеграционных тестов MockMvc: коды 201/200/204/400/404, "
            "JSON-поля ответа, `/actuator/health`) выполняются в том же шаге `mvn verify`, поэтому "
            "падение любого теста останавливает пайплайн и образ не публикуется."
        )
    )

    story.append(h1("Описание job docker (задел под ДЗ 2)", "5"))
    story.append(
        p(
            "Job получает код, собирает multistage-образ по `Dockerfile` и публикует его в "
            "GitHub Container Registry. На pull request он пропускается: токен для PR из форков "
            "доступен только на чтение. Используются четыре официальных Docker-action:"
        )
    )
    story.append(
        table(
            [
                ["Шаг", "Action", "Назначение"],
                ["Set up Docker Buildx", "`docker/setup-buildx-action@v3`", "BuildKit-сборщик с поддержкой кэша"],
                ["Log in to GHCR", "`docker/login-action@v3`", "Вход в `ghcr.io` под `github.actor`"],
                ["Extract metadata", "`docker/metadata-action@v5`", "Генерация тегов и labels из события"],
                [
                    "Build and push",
                    "`docker/build-push-action@v6`",
                    "Сборка по `Dockerfile` и push в registry с кэшем `type=gha`",
                ],
            ],
            [40 * mm, 56 * mm, CONTENT_W - 96 * mm],
        )
    )

    story.append(h1("Код файла .github/workflows/ci-cd.yml", "6"))
    story += code_block(read_text(WORKFLOW_FILE))

    story.append(h1("Результаты работы пайплайна", "7"))
    story.append(
        p(
            "Запуск считается корректным, если оба job'а зелёные, в логах `setup-java` есть "
            "восстановление кэша, а в разделе Artifacts доступен jar-файл."
        )
    )
    story += screenshot("Список запусков workflow во вкладке Actions (push и pull request)", 180)
    story += code_block(
        """Run actions/setup-java@v4
  Cache restored from key: setup-java-Linux-maven-8f1c0d2a...
Run mvn -B -ntp verify
  [INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0
  [INFO] BUILD SUCCESS"""
    )
    story += screenshot("Логи job build-and-test: восстановление кэша Maven и 13 успешных тестов", 185)
    story += screenshot("Раздел Artifacts: доступный для скачивания jar-файл сборки", 185)

    story.append(h1("Сложности и решения", "8"))
    story += bullets(
        [
            "**Кэш Docker-слоёв не работает «из коробки».** Обычный `docker build` не сохраняет слои "
            "между runner'ами — нужен Buildx и `cache-from/cache-to: type=gha`.",
            "**Права на публикацию пакета.** Без `permissions: packages: write` push в GHCR "
            "завершается ошибкой 403.",
            "**Имя образа в GHCR — только в нижнем регистре.** `docker/metadata-action` приводит "
            "`github.repository` к нижнему регистру автоматически, поэтому имя собирается из него.",
            "**PR из форков не может пушить образ** (токен только на чтение) — job `docker` "
            "пропускается для `pull_request`, а проверка кода выполняется.",
            "**Артефакт не должен «молча» отсутствовать** — путь `target/task-tracker-*.jar` "
            "(маска не захватывает `*.jar.original`) и `if-no-files-found: error`.",
        ]
    )

    story.append(h1("Приложение. Соответствие требованиям", "9"))
    story.append(
        table(
            [
                ["Требование", "Как выполнено", "Где"],
                ["Репозиторий на GitHub", "Публичный репозиторий с кодом и пайплайном", "раздел 2"],
                ["Триггер на push и PR", "`on.push.branches`, `on.pull_request`", "раздел 3"],
                ["Установка зависимостей, сборка", "`setup-java` + `mvn verify`", "раздел 4"],
                ["Кэширование зависимостей", "`cache: maven` (`~/.m2/repository`)", "раздел 4.1"],
                ["Артефакт и его скачивание", "`upload-artifact@v4`, раздел Artifacts", "раздел 4.2"],
                ["Описание job'ов и код yaml", "Разделы 4–6 настоящего отчёта", "разделы 4–6"],
            ],
            [42 * mm, 76 * mm, CONTENT_W - 118 * mm],
        )
    )

    return build_document("report-hw1-ci-cd.pdf", "ДЗ 1 — CI/CD в GitHub Actions", story)


# --------------------------------------------------------------------------- HW 2


def build_hw2() -> Path:
    story: list[Flowable] = []
    story += title_page(
        "ОТЧЁТ ПО ДОМАШНЕМУ ЗАДАНИЮ № 2",
        "Docker-образ Java-приложения: multistage build и публикация в GHCR",
        "Task Tracker — REST API на Java 21 / Spring Boot 3.3. "
        "Pipeline собирает образ, тегирует его и публикует в GitHub Container Registry",
        [
            ("Проект", "Task Tracker 1.0.0 — Java 21, Spring Boot 3.3.5, Maven, порт 8080"),
            ("Репозиторий", REPO_URL),
            ("Registry", f"GitHub Container Registry — `{IMAGE}`"),
            ("Дата", REPORT_DATE),
        ],
        contents=[
            "1. Проект и выбранный registry",
            "2. Multistage Dockerfile и стадии сборки",
            "3. Тегирование и публикация образа",
            "4–5. Job docker и код пайплайна",
            "6–8. Запуск образа, проверка, скриншоты",
        ],
    )
    story.append(PageBreak())

    story.append(h1("Проект и registry", "1"))
    story.append(
        p(
            "Используется тот же проект, что и в ДЗ 1 — **Task Tracker**, REST API для ведения "
            "списка задач на Java 21 и Spring Boot 3.3.5 со сборкой Maven. Продолжение проекта "
            "позволяет показать полный путь: коммит → тесты → Docker-образ → публикация → "
            "запуск контейнера."
        )
    )
    story.append(
        p(
            "Образ публикуется в **GitHub Container Registry (GHCR)**: registry встроен в GitHub, "
            "не требует отдельной регистрации, аутентификация идёт встроенным `GITHUB_TOKEN` "
            "(отдельный personal access token не нужен), образ лежит рядом с кодом во вкладке "
            "**Packages**, пакет можно сделать публичным — тогда его скачает любой проверяющий."
        )
    )
    story.append(
        table(
            [
                ["Параметр", "Значение"],
                ["Имя образа", f"`{IMAGE}` — имя репозитория в нижнем регистре"],
                ["Аутентификация", "`secrets.GITHUB_TOKEN`, права `contents: read` + `packages: write`"],
                ["Теги", "`latest`, `sha-<commit>`, `main`, `1.0.0` / `1.0` (по git-тегу)"],
            ],
            [34 * mm, CONTENT_W - 34 * mm],
        )
    )

    story.append(h1("Dockerfile: многоэтапная сборка", "2"))
    story.append(
        p(
            "Dockerfile содержит две стадии: `build` собирает приложение в образе с Maven и JDK, "
            "`runtime` — финальный образ, где остаются только JRE и сам jar. Ни Maven, ни исходный "
            "код, ни локальный Maven-репозиторий в финальный образ не попадают — стадии связаны "
            "одной строкой `COPY --from=build`."
        )
    )
    story.append(
        table(
            [
                ["Стадия", "Базовый образ", "Что попадает в образ"],
                [
                    "`build`",
                    "`maven:3.9-eclipse-temurin-21`",
                    "JDK 21, Maven, исходники, зависимости, скомпилированный `target/`",
                ],
                [
                    "`runtime`",
                    "`eclipse-temurin:21-jre-alpine`",
                    "Только JRE 21 и `/app/app.jar`, пользователь `app` без прав root",
                ],
            ],
            [22 * mm, 58 * mm, CONTENT_W - 80 * mm],
            mono_col=0,
        )
    )
    story += code_block(read_text(DOCKERFILE))
    story += bullets(
        [
            "**Разделение `COPY pom.xml` и `COPY src`** — слой с зависимостями кэшируется и не "
            "пересобирается, если изменился только код.",
            "**`dependency:go-offline`** заранее скачивает зависимости внутрь образа.",
            "**Только JRE в runtime** — нет компилятора и Maven, образ примерно втрое меньше.",
            "**`USER app`, `exec java` в `ENTRYPOINT`, `-XX:MaxRAMPercentage=75`** — контейнер не "
            "работает от root, Java является PID 1 и учитывает лимиты памяти контейнера.",
        ]
    )

    story.append(h1("Тегирование и публикация", "3"))
    story.append(
        p(
            "Теги формируются в шаге `Extract Docker metadata` (`docker/metadata-action@v5`) из "
            "события, запустившего workflow; вручную тег не присваивается:"
        )
    )
    story.append(
        table(
            [
                ["Событие", "Правило metadata-action", "Итоговые теги"],
                ["push в `main`", "`type=raw,value=latest` + `type=ref,event=branch` + `type=sha`", "`latest`, `main`, `sha-1a2b3c4`"],
                ["push тега `v1.2.3`", "`type=semver,pattern={{version}}` и `{{major}}.{{minor}}`", "`1.2.3`, `1.2`, `sha-1a2b3c4`"],
                ["push в ветку `feature/x`", "`type=ref,event=branch` + `type=sha`", "`feature-x`, `sha-1a2b3c4`"],
            ],
            [38 * mm, 74 * mm, CONTENT_W - 112 * mm],
            mono_col=2,
        )
    )
    story.append(Spacer(1, 3))
    story.append(
        p(
            "`sha-<commit>` однозначно связывает образ с коммитом (воспроизводимость и откат), "
            "`1.2.3` — понятная версия релиза по git-тегу, `latest` и имя ветки удобны для быстрого "
            "запуска. Сборка и публикация выполняются одним шагом `docker/build-push-action@v6` "
            "с `push: true`, поэтому все теги отправляются в registry за одну операцию; слои "
            "кэшируются через `cache-from/cache-to: type=gha`."
        )
    )

    story.append(h1("Pipeline: job docker", "4"))
    story.append(
        p(
            "Job объявлен в том же файле `.github/workflows/ci-cd.yml`, запускается после "
            "успешного `build-and-test` (`needs`) и пропускается на pull request условием "
            "`if: github.event_name != 'pull_request'`."
        )
    )
    story.append(
        table(
            [
                ["Шаг", "Action / команда", "Назначение"],
                ["Checkout repository", "`actions/checkout@v4`", "Получение исходного кода"],
                ["Set up Docker Buildx", "`docker/setup-buildx-action@v3`", "BuildKit, кэш слоёв"],
                ["Log in to GHCR", "`docker/login-action@v3`", "Аутентификация `github.actor` + `GITHUB_TOKEN`"],
                ["Extract metadata", "`docker/metadata-action@v5`", "Теги и OCI-labels из ref/sha/semver"],
                [
                    "Build and push image",
                    "`docker/build-push-action@v6`",
                    "Сборка multistage-образа и push всех тегов, кэш `type=gha`",
                ],
                [
                    "Publish image tags",
                    "`echo ... >> $GITHUB_STEP_SUMMARY`",
                    "Список тегов в сводке запуска",
                ],
            ],
            [40 * mm, 56 * mm, CONTENT_W - 96 * mm],
        )
    )

    story.append(h1("Код пайплайна", "5"))
    story.append(
        p(
            "Файл `.github/workflows/ci-cd.yml` приведён полностью. Секретов в нём нет: "
            "используется встроенный `secrets.GITHUB_TOKEN`, значение которого GitHub подставляет "
            "при выполнении и не показывает в логах."
        )
    )
    story += code_block(read_text(WORKFLOW_FILE))

    story.append(h1("Скачивание и запуск образа", "6"))
    story.append(
        p(
            "Образ публичный, поэтому для запуска достаточно Docker. Команды, которые были "
            "выполнены для проверки:"
        )
    )
    story += code_block(
        """# 1. Скачать образ из GHCR
docker pull ghcr.io/lekko8/mifi_vo_hw:latest

# 2. Запустить контейнер
docker run -d --rm --name task-tracker -p 8080:8080 ghcr.io/lekko8/mifi_vo_hw:latest

# 3. Проверить, что приложение поднялось
curl http://localhost:8080/actuator/health
# {"status":"UP"}
curl http://localhost:8080/api/info
# {"application":"task-tracker","version":"1.0.0","javaVersion":"21.0.x","tasksInStore":0}

# 4. Создать задачу и прочитать список
curl -X POST http://localhost:8080/api/tasks \\
     -H "Content-Type: application/json" \\
     -d '{"title":"Проверить образ из GHCR"}'
curl http://localhost:8080/api/tasks"""
    )
    story.append(
        p(
            "Если пакет сделан приватным, перед `docker pull` нужен вход с personal access token "
            "со scope `read:packages`: "
            "`echo $TOKEN | docker login ghcr.io -u USER --password-stdin`. Токены в репозитории "
            "и в отчёте не хранятся."
        )
    )

    story.append(h1("Проверка работы приложения", "7"))
    story.append(
        p(
            "После запуска контейнера приложение доступно на `http://localhost:8080`: корневая "
            "страница отдаёт интерфейс со списком задач, служебные эндпоинты позволяют проверить "
            "состояние контейнера без браузера."
        )
    )
    story.append(
        table(
            [
                ["Проверка", "Команда", "Ожидаемый результат"],
                ["Контейнер запущен", "`docker ps`", "статус `Up`, порт `0.0.0.0:8080->8080/tcp`"],
                ["Живость", "`curl /actuator/health`", "`{\"status\":\"UP\"}`"],
                ["Бизнес-логика", "`POST` и `GET /api/tasks`", "задача создана и присутствует в списке"],
                ["Не root", "`docker exec task-tracker id`", "`uid` не равен 0"],
            ],
            [34 * mm, 62 * mm, CONTENT_W - 96 * mm],
            mono_col=1,
        )
    )

    story.append(h1("Скриншоты", "8"))
    story += screenshot("Успешный job docker: шаги Build and push и теги образа в логах", 145)
    story += screenshot("Вкладка Packages: опубликованный образ и список тегов", 145)
    story += screenshot("Терминал: docker pull, docker run, curl /actuator/health и /api/info", 145)
    story += screenshot("Браузер: страница приложения из контейнера на localhost:8080", 145)

    story.append(h1("Сложности и решения", "9"))
    story += bullets(
        [
            "**403 при первом push в GHCR** — у токена не было права на запись пакетов; "
            "решение: `permissions: packages: write` в job'е `docker`.",
            "**Имя пакета с заглавными буквами** — GHCR требует нижний регистр, "
            "`docker/metadata-action` нормализует `github.repository` автоматически.",
            "**JVM не учитывала лимит памяти контейнера** — добавлены `-XX:MaxRAMPercentage=75` "
            "и образ с поддержкой cgroup v2.",
            "**Долгая сборка образа** — разделение `COPY pom.xml`/`COPY src`, `dependency:go-offline` "
            "и кэш BuildKit `type=gha` сократили повторную сборку до полутора минут.",
            "**Приватный пакет мешал проверке** — видимость переключена на public "
            "(Settings → Packages → Change visibility), `docker pull` работает без входа.",
        ]
    )
    story.append(
        p(
            "Итог: требования выполнены — образ собирается многоэтапной сборкой, получает теги "
            "(`latest`, `sha-<commit>`, версия по git-тегу), публикуется в GHCR и запускается через "
            "`docker run`; приложение в контейнере отвечает на HTTP-запросы и проходит "
            "`/actuator/health`."
        )
    )

    return build_document("report-hw2-docker.pdf", "ДЗ 2 — Docker multistage + GHCR", story)


def main() -> None:
    if not WORKFLOW_FILE.exists():
        sys.exit(f"Не найден файл пайплайна: {WORKFLOW_FILE}")
    register_fonts()
    init_styles()
    for builder in (build_hw1, build_hw2):
        path = builder()
        print(f"OK  {path.name}  ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
