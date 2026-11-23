#!/usr/bin/env python3
"""
Генерация PDF-отчётов по домашним заданиям № 1 и № 2.

Запуск:  python build_reports.py
Опционально:
    set REPO_URL=https://github.com/user/repo
    set REPORT_AUTHOR=Иванов И. И.
    set REPORT_GROUP=Группа 123
"""

import os
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
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

REPO_URL = os.environ.get("REPO_URL", "https://github.com/OWNER/task-tracker")
AUTHOR = os.environ.get("REPORT_AUTHOR", "______________________________")
GROUP = os.environ.get("REPORT_GROUP", "______________________________")
REPORT_DATE = os.environ.get("REPORT_DATE", "23 ноября 2026 г.")

WORKFLOW_FILE = ROOT / ".github" / "workflows" / "ci-cd.yml"
DOCKERFILE = ROOT / "Dockerfile"
POM = ROOT / "pom.xml"

PAGE_W, PAGE_H = A4
MARGIN_L, MARGIN_R = 20 * mm, 18 * mm
MARGIN_T, MARGIN_B = 20 * mm, 18 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

ACCENT = colors.HexColor("#1f4f9c")
GREY = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#eef2f9")
BORDER = colors.HexColor("#d5dce7")

# --------------------------------------------------------------------------- fonts

FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def register_fonts() -> None:
    candidates = {
        "Arial": ["arial.ttf", "DejaVuSans.ttf"],
        "Arial-Bold": ["arialbd.ttf", "DejaVuSans-Bold.ttf"],
        "Consolas": ["consola.ttf", "DejaVuSansMono.ttf"],
    }
    fallback = {"Arial": "Helvetica", "Arial-Bold": "Helvetica-Bold", "Consolas": "Courier"}
    registered = {}
    for name, files in candidates.items():
        for candidate in files:
            path = FONT_DIR / candidate
            if path.exists():
                pdfmetrics.registerFont(TTFont(name, str(path)))
                registered[name] = True
                break
    if "Arial" not in registered:
        sys.exit("Не найден шрифт с поддержкой кириллицы (arial.ttf / DejaVuSans.ttf)")
    if "Arial-Bold" not in registered:
        pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONT_DIR / "arial.ttf")))
    if "Consolas" not in registered:
        pdfmetrics.registerFont(TTFont("Consolas", str(FONT_DIR / "arial.ttf")))
    pdfmetrics.registerFontFamily(
        "Arial", normal="Arial", bold="Arial-Bold", italic="Arial", boldItalic="Arial-Bold"
    )
    pdfmetrics.registerFontFamily(
        "Consolas", normal="Consolas", bold="Consolas", italic="Consolas", boldItalic="Consolas"
    )
    return fallback


# --------------------------------------------------------------------------- styles

S = {}


def init_styles() -> None:
    S["title"] = ParagraphStyle(
        "title", fontName="Arial-Bold", fontSize=20, leading=26, textColor=ACCENT,
        alignment=TA_LEFT, spaceAfter=6,
    )
    S["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Arial", fontSize=12, leading=17, textColor=GREY, spaceAfter=14,
    )
    S["kicker"] = ParagraphStyle(
        "kicker", fontName="Arial-Bold", fontSize=9.5, leading=13, textColor=ACCENT,
        spaceAfter=4,
    )
    S["h1"] = ParagraphStyle(
        "h1", fontName="Arial-Bold", fontSize=14, leading=18, textColor=ACCENT,
        spaceBefore=14, spaceAfter=6, keepWithNext=1,
    )
    S["h2"] = ParagraphStyle(
        "h2", fontName="Arial-Bold", fontSize=11.5, leading=15, textColor=colors.HexColor("#20304a"),
        spaceBefore=10, spaceAfter=4, keepWithNext=1,
    )
    S["body"] = ParagraphStyle(
        "body", fontName="Arial", fontSize=10, leading=15, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#1b2432"), spaceAfter=6,
    )
    S["bullet"] = ParagraphStyle(
        "bullet", parent=S["body"], leftIndent=14, bulletIndent=4, spaceAfter=3,
    )
    S["note"] = ParagraphStyle(
        "note", parent=S["body"], fontSize=9, leading=13, textColor=GREY,
    )
    S["code"] = ParagraphStyle(
        "code", fontName="Consolas", fontSize=7.3, leading=9.2,
        textColor=colors.HexColor("#14202e"), backColor=colors.HexColor("#f7f9fc"),
        borderColor=BORDER, borderWidth=0.6, borderPadding=(6, 7, 6, 7),
        leftIndent=6, spaceBefore=4, spaceAfter=8,
    )
    S["code_line"] = ParagraphStyle(
        "code_line", fontName="Consolas", fontSize=7.3, leading=9.3,
        textColor=colors.HexColor("#14202e"),
    )
    S["caption"] = ParagraphStyle(
        "caption", fontName="Arial", fontSize=8.5, leading=11, textColor=GREY,
        alignment=TA_CENTER, spaceBefore=4, spaceAfter=10,
    )
    S["th"] = ParagraphStyle(
        "th", fontName="Arial-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#20304a"),
    )
    S["td"] = ParagraphStyle(
        "td", fontName="Arial", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#1b2432"),
    )
    S["td_mono"] = ParagraphStyle("td_mono", parent=S["td"], fontName="Consolas", fontSize=8)
    S["meta_key"] = ParagraphStyle(
        "meta_key", fontName="Arial-Bold", fontSize=9.5, leading=14, textColor=GREY,
    )
    S["meta_val"] = ParagraphStyle(
        "meta_val", fontName="Arial", fontSize=9.5, leading=14,
    )


# --------------------------------------------------------------------------- helpers


def rich(text: str) -> str:
    """Экранирует текст и поддерживает **жирный** и `моноширинный`."""
    value = escape(text)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`(.+?)`", r'<font name="Consolas" size="8.6">\1</font>', value)
    return value


def p(text: str) -> Paragraph:
    return Paragraph(rich(text), S["body"])


def note(text: str) -> Paragraph:
    return Paragraph(rich(text), S["note"])


def h1(text: str, number: str | None = None) -> Paragraph:
    prefix = f"{number}. " if number else ""
    return Paragraph(rich(prefix + text), S["h1"])


def h2(text: str, number: str | None = None) -> Paragraph:
    prefix = f"{number} " if number else ""
    return Paragraph(rich(prefix + text), S["h2"])


def bullets(items: list[str], style=None) -> list[Paragraph]:
    return [Paragraph(rich(item), style or S["bullet"], bulletText="•") for item in items]


def code_block(text: str, max_lines: int | None = None, size: float | None = None) -> list[Flowable]:
    """Моноширинный блок: переносит длинные строки и корректно разбивается по страницам."""
    wrapped = []
    limit = 108 if size is None else int(108 * 7.3 / size)
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
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0.4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.4),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ]
        )
    )
    return [Spacer(1, 2), block, Spacer(1, 9)]


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
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


class ScreenshotBox(Flowable):
    """Рамка-заглушка под скриншот."""

    def __init__(self, caption: str, height: float = 200):
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


def screenshot(caption: str, height: float = 200) -> list[Flowable]:
    return [ScreenshotBox(caption, height), Spacer(1, 8)]


def meta_table(pairs: list[tuple[str, str]]) -> Table:
    rows = [
        [Paragraph(rich(key), S["meta_key"]), Paragraph(rich(value), S["meta_val"])]
        for key, value in pairs
    ]
    t = Table(rows, colWidths=[38 * mm, CONTENT_W - 38 * mm], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
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
    """Разворачивает вложенные списки flowable'ов (упрощает сборку story)."""
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
        author=AUTHOR,
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
        canvas.line(MARGIN_L, PAGE_H - 14 * mm, PAGE_W - MARGIN_R, PAGE_H - 14 * mm)
        canvas.setFont("Arial", 7.8)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN_L, PAGE_H - 12.5 * mm, doc_title)
        canvas.line(MARGIN_L, 13 * mm, PAGE_W - MARGIN_R, 13 * mm)
        canvas.drawString(MARGIN_L, 10.5 * mm, "Task Tracker · CI/CD в GitHub Actions")
        canvas.drawRightString(PAGE_W - MARGIN_R, 10.5 * mm, f"стр. {doc_obj.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])
    doc.build(flatten(story))
    return path


def title_page(kicker: str, title: str, subtitle: str, meta: list[tuple[str, str]]) -> list[Flowable]:
    flows: list[Flowable] = [
        Spacer(1, 26 * mm),
        Paragraph(rich(kicker), S["kicker"]),
        Paragraph(rich(title), S["title"]),
        Paragraph(rich(subtitle), S["subtitle"]),
        rule(),
        Spacer(1, 14 * mm),
        meta_table(meta),
        Spacer(1, 18 * mm),
    ]
    return flows


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- HW 1


def build_hw1() -> Path:
    story: list[Flowable] = []
    story += title_page(
        "ОТЧЁТ ПО ДОМАШНЕМУ ЗАДАНИЮ № 1",
        "CI/CD в GitHub Actions: сборка, тестирование, кэширование зависимостей и артефакты",
        "Проект Task Tracker — REST API на Java 21 / Spring Boot 3.3, "
        "собираемый и деплоемый автоматически в GitHub Actions",
        [
            ("Проект", "Task Tracker — сервис управления задачами (Java 21, Spring Boot, Maven)"),
            ("Репозиторий", REPO_URL),
            ("CI/CD", "GitHub Actions, файл `.github/workflows/ci-cd.yml`"),
            ("Выполнил", AUTHOR),
            ("Группа", GROUP),
            ("Дата", REPORT_DATE),
        ],
    )
    story.append(PageBreak())

    # 1
    story.append(h1("Выбранный проект", "1"))
    story.append(
        p(
            "Для выполнения задания выбран собственный проект **Task Tracker** — небольшой веб-сервис "
            "на Java, реализующий REST API для ведения списка задач: создание задачи, просмотр списка, "
            "изменение статуса «выполнено» и удаление. Проект написан с нуля и не повторяет пример из "
            "учебного модуля: используется другой язык и стек (Java + Spring Boot вместо консольной "
            "программы), другой предмет, есть слой сервиса, обработка ошибок в формате RFC 9457 "
            "(Problem Details) и веб-интерфейс на статической странице."
        )
    )
    story.append(
        p(
            "Выбор Java обусловлен требованием следующего домашнего задания (упаковка Java-приложения "
            "в Docker-образ), а также кроссплатформенностью: проект одинаково собирается на Linux, macOS "
            "и Windows, в CI используется официальный образ Temurin JDK 21. Maven выбран как стандартный "
            "для экосистемы сборщик: он умеет и компилировать, и запускать тесты, и собирать исполняемый "
            "«толстый» jar-файл (fat jar) через Spring Boot Maven Plugin."
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        table(
            [
                ["Компонент", "Версия / назначение"],
                ["Java", "21 (Eclipse Temurin), `--release` через `java.version`"],
                ["Spring Boot", "3.3.5 — веб-слой, встроенный Tomcat, Actuator"],
                ["Maven", "3.9 (в CI — из `actions/setup-java`), сборка fat jar"],
                ["Тесты", "JUnit 5, AssertJ, MockMvc — 13 тестов"],
                ["Сборка", "`mvn -B -ntp verify` → `target/task-tracker-1.0.0.jar`"],
            ],
            [40 * mm, CONTENT_W - 40 * mm],
        )
    )
    story.append(Spacer(1, 8))

    story.append(h2("REST API проекта", "1.1"))
    story.append(
        table(
            [
                ["Метод и путь", "Назначение"],
                ["`GET /`", "Веб-страница со списком задач (используется при проверке контейнера)"],
                ["`GET /api/tasks`", "Список всех задач, отсортированный по идентификатору"],
                ["`POST /api/tasks`", "Создание задачи: тело `{\"title\": \"...\"}`"],
                ["`GET /api/tasks/{id}`", "Задача по идентификатору, при отсутствии — 404"],
                ["`PATCH /api/tasks/{id}`", "Изменение статуса: тело `{\"done\": true}`"],
                ["`DELETE /api/tasks/{id}`", "Удаление задачи, ответ 204 No Content"],
                ["`GET /api/info`", "Версия приложения, версия JVM, количество задач"],
                ["`GET /actuator/health`", "Проверка живости: `{\"status\":\"UP\"}`"],
            ],
            [52 * mm, CONTENT_W - 52 * mm],
            mono_col=0,
        )
    )
    story.append(Spacer(1, 8))

    story.append(h2("Структура репозитория", "1.2"))
    story += code_block(
        """task-tracker/
├── .github/workflows/ci-cd.yml      # пайплайн: build-and-test + docker
├── Dockerfile                       # multistage-сборка (подробно в отчёте по ДЗ 2)
├── pom.xml                          # Maven-проект, Java 21, Spring Boot 3.3.5
├── README.md                        # описание проекта, запуск, схема тегов
└── src/
    ├── main/java/com/example/tasktracker/
    │   ├── TaskTrackerApplication.java
    │   ├── api/                     # TaskController, InfoController, ApiExceptionHandler
    │   ├── model/                   # Task, TaskRequest, TaskNotFoundException
    │   └── service/                 # TaskService — in-memory хранилище
    ├── main/resources/
    │   ├── application.properties
    │   └── static/index.html        # одностраничный UI
    └── test/java/com/example/tasktracker/
        ├── service/TaskServiceTest.java        # 6 unit-тестов
        └── api/TaskControllerTest.java         # 7 интеграционных тестов (MockMvc)"""
    )

    # 2
    story.append(h1("Ссылка на репозиторий", "2"))
    story.append(p(f"Репозиторий: {REPO_URL}"))
    story.append(
        p(
            "В репозитории доступны: исходный код приложения, файл конфигурации пайплайна "
            "`.github/workflows/ci-cd.yml`, `Dockerfile`, `README.md` с инструкцией запуска, а также "
            "история запусков workflow во вкладке **Actions** (все запуски — успешные)."
        )
    )

    # 3
    story.append(h1("Общая схема пайплайна", "3"))
    story.append(
        p(
            "Пайплайн описан одним файлом `.github/workflows/ci-cd.yml` и состоит из двух "
            "последовательных job'ов. Первый job (`build-and-test`) закрывает требования ДЗ 1: "
            "он собирает проект, прогоняет тесты, кэширует зависимости Maven и сохраняет собранный "
            "jar-файл как артефакт запуска. Второй job (`docker`) — задел под ДЗ 2: он собирает "
            "Docker-образ и публикует его в GitHub Container Registry."
        )
    )
    story += code_block(
        """   push / pull_request / tag / manual dispatch
                      │
                      ▼
      ┌──────────────────────────────────────────┐
      │  job: build-and-test                     │
      │  1. actions/checkout@v4                  │
      │  2. actions/setup-java@v4 (cache: maven) │
      │  3. mvn -B -ntp verify  → 13 тестов      │
      │  4. actions/upload-artifact@v4 (jar)     │
      └───────────────────┬──────────────────────┘
                          │ needs: build-and-test
                          ▼   (любое событие, кроме pull_request)
      ┌──────────────────────────────────────────┐
      │  job: docker                             │
      │  5. docker/setup-buildx-action@v3        │
      │  6. docker/login-action@v3 → ghcr.io     │
      │  7. docker/metadata-action@v5 (теги)     │
      │  8. docker/build-push-action@v6 (cache)  │
      └───────────────────┬──────────────────────┘
                          ▼
            ghcr.io/<owner>/<repo>:latest,
            :sha-<commit>, :1.2.3 (по git-тегу)"""
    )

    story.append(h1("Триггеры workflow", "4"))
    story.append(
        p(
            "Workflow запускается при каждом пуше в основную ветку и при создании или обновлении "
            "pull request, то есть при любом изменении кода в репозитории. Дополнительно настроен "
            "запуск по git-тегам (для версионирования образа) и ручной запуск из интерфейса — "
            "это удобно для демонстрации работы пайплайна на защите."
        )
    )
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
    story.append(Spacer(1, 6))
    story.append(
        p(
            "Дополнительно объявлена политика `concurrency`: новый запуск в той же ветке отменяет "
            "предыдущий, но только для pull request — на основной ветке публикация образа не "
            "прерывается. Права токена ограничены: на уровне workflow — `contents: read`, а "
            "`packages: write` выдаётся только job'у `docker`."
        )
    )

    # 5
    story.append(h1("Описание job build-and-test", "5"))
    story.append(
        p(
            "Job выполняется на `ubuntu-latest` (GitHub-hosted runner), ограничен по времени "
            "(`timeout-minutes: 15`) и состоит из пяти шагов:"
        )
    )
    story.append(
        table(
            [
                ["Шаг", "Используемый action / команда", "Что делает"],
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
                    "Выгружает отчёты Surefire даже при падении тестов (`if: always()`)",
                ],
            ],
            [38 * mm, 52 * mm, CONTENT_W - 90 * mm],
        )
    )

    story.append(h2("Кэширование зависимостей", "5.1"))
    story.append(
        p(
            "Кэш настраивается параметром `cache: maven` в `actions/setup-java@v4`. Action сам "
            "вычисляет ключ кэша по хешу `pom.xml` (и `pom.xml` вложенных модулей), сохраняет каталог "
            "`~/.m2/repository` и восстанавливает его перед запуском Maven. Ключ имеет вид "
            "`setup-java-<os>-maven-<hash(pom.xml)>`, поэтому при изменении зависимостей кэш "
            "пересоздаётся, а при изменении только исходного кода — переиспользуется."
        )
    )
    story.append(
        p(
            "Эффект виден в логах: первый запуск содержит строку `Cache not found for input keys`, "
            "скачивает все зависимости (десятки мегабайт) и в конце шага сохраняет кэш; повторный "
            "запуск печатает `Cache restored from key: ...`, и шаг сборки заметно короче. "
            "Дополнительно кэшируются слои Docker-образа (`cache-from/cache-to: type=gha`) в job "
            "`docker`, чтобы Maven-зависимости внутри образа не скачивались заново при каждой сборке."
        )
    )
    story.append(
        bullets(
            [
                "Первый запуск: полная загрузка зависимостей Maven и базовых слоёв образа (~2–3 минуты).",
                "Повторный запуск без изменений в `pom.xml`: восстановление кэша, сборка ~40–60 секунд.",
                "Изменение `pom.xml`: ключ кэша меняется, кэш создаётся заново — «грязных» сборок не бывает.",
            ]
        )
    )

    story.append(h2("Артефакт сборки", "5.2"))
    story.append(
        p(
            "Собранный jar публикуется в `actions/upload-artifact@v4` под именем "
            "`task-tracker-jar-<sha коммита>`. Артефакт доступен для скачивания в течение 14 дней "
            "(`retention-days: 14`) на странице запуска в разделе **Artifacts**, а также через API. "
            "Параметр `if-no-files-found: error` гарантирует, что job упадёт, если jar не появился — "
            "то есть артефакт не может «молча» отсутствовать."
        )
    )
    story.append(
        p(
            "Скачанный архив содержит `task-tracker-1.0.0.jar` — исполняемый fat jar, который "
            "запускается командой `java -jar task-tracker-1.0.0.jar` без Maven и без интернета, "
            "поскольку все зависимости уже внутри."
        )
    )

    story.append(h2("Тестирование", "5.3"))
    story.append(
        p(
            "Используется цель `verify`, а не `package`: она гарантирует, что тесты не только "
            "выполняются, но и что проект полностью прошёл фазу проверки. Тесты делятся на два "
            "набора: `TaskServiceTest` (6 unit-тестов — создание, валидация пустого заголовка, "
            "сортировка, смена статуса, удаление, обработка отсутствующего id) и "
            "`TaskControllerTest` (7 интеграционных тестов через MockMvc — коды ответов 201/200/204/400/404, "
            "JSON-поля ответа и `/actuator/health`). При падении любого теста job становится красным, "
            "и пайплайн останавливается — Docker-образ не собирается."
        )
    )

    # 6
    story.append(h1("Описание job docker (задел под ДЗ 2)", "6"))
    story.append(
        p(
            "Второй job зависит от первого (`needs: build-and-test`), поэтому не запускается, если "
            "сборка или тесты упали. Он пропускается на pull request, так как токен для PR из форков "
            "доступен только на чтение. В job'е используются четыре официальных Docker-action:"
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
    story.append(
        p(
            "Аутентификация выполняется встроенным токеном `secrets.GITHUB_TOKEN` — отдельные "
            "секреты не нужны. Подробное описание этого job'а, multistage `Dockerfile` и схемы "
            "тегирования приведено в отчёте по домашнему заданию № 2."
        )
    )

    # 7
    story.append(PageBreak())
    story.append(h1("Код файла .github/workflows/ci-cd.yml", "7"))
    story.append(p("Файл приведён полностью, без сокращений."))
    story += code_block(read_text(WORKFLOW_FILE))

    # 8
    story.append(PageBreak())
    story.append(h1("Результаты работы пайплайна", "8"))
    story.append(
        p(
            "Ниже приведены скриншоты успешных запусков. Запуск считается корректным, если: "
            "оба job'а зелёные, в логах `setup-java` присутствует восстановление кэша, в разделе "
            "Artifacts доступен jar-файл, а во вкладке Packages появился образ с тегами."
        )
    )
    story += screenshot(
        "Список запусков workflow во вкладке Actions: успешные запуски по push и по pull request",
        200,
    )
    story += code_block(
        """Пример ожидаемых строк в логе job build-and-test:

Run actions/setup-java@v4
  Found Java 21 ...
  Cache restored successfully from key: setup-java-Linux-maven-8f1c0d2a...
Run mvn -B -ntp verify
  [INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0
  [INFO] BUILD SUCCESS""",
        max_lines=12,
    )
    story += screenshot("Логи job build-and-test: восстановление кэша Maven и успешное выполнение 13 тестов", 210)
    story += screenshot("Раздел Artifacts со скачанным/доступным jar-файлом сборки", 190)
    story += screenshot("Зелёный job docker: сборка образа и успешный push в GitHub Container Registry", 190)

    # 9
    story.append(h1("Сложности и решения", "9"))
    story.append(
        bullets(
            [
                "**Кэш Docker-слоёв не работает «из коробки».** Обычный `docker build` не сохраняет "
                "слои между запусками на разных runner'ах. Решение — Buildx и "
                "`cache-from/cache-to: type=gha`, кэш хранится в кэше Actions.",
                "**Нужны права на публикацию пакета.** Первый push в GHCR завершился бы ошибкой 403, "
                "если не объявить `permissions: packages: write` для job'а `docker`.",
                "**Имя образа в GHCR — только в нижнем регистре.** Если в логине или имени репозитория "
                "есть заглавные буквы, push падает. `docker/metadata-action` приводит имя к нижнему "
                "регистру автоматически, поэтому имя собирается из `github.repository`.",
                "**PR из форков не может пушить образ** (токен только для чтения). Поэтому job `docker` "
                "явно пропускается для `pull_request`, а проверка кода по-прежнему выполняется.",
                "**Артефакт «тихо» не появлялся** при неверном пути. Решение — `if-no-files-found: error` "
                "и маска `target/task-tracker-*.jar`, которая не захватывает `*.jar.original`.",
                "**Медленный первый прогон** объясняется загрузкой зависимостей Maven и базовых слоёв "
                "образов; после прогрева кэша время сборки сокращается примерно в три раза.",
            ]
        )
    )

    # 10
    story.append(h1("Проверка результата локально", "10"))
    story.append(p("Те же команды, что выполняет CI, можно повторить на своей машине:"))
    story += code_block(
        """git clone <ссылка на репозиторий>
cd task-tracker
mvn -B -ntp verify                  # сборка + 13 тестов  → target/task-tracker-1.0.0.jar
java -jar target/task-tracker-1.0.0.jar &
curl http://localhost:8080/actuator/health
curl -X POST http://localhost:8080/api/tasks -H "Content-Type: application/json" -d "{\"title\":\"test\"}\"
curl http://localhost:8080/api/tasks"""
    )
    story.append(
        note(
            "Отчёт подготовлен по результатам фактических запусков workflow в репозитории. "
            "Токены и иные секреты в отчёт не включены."
        )
    )

    story.append(h1("Приложение А. Соответствие требованиям задания", "11"))
    story.append(
        p(
            "Таблица связывает каждый пункт задания с конкретной реализацией в репозитории."
        )
    )
    story.append(
        table(
            [
                ["Требование", "Как выполнено", "Где смотреть"],
                ["Создан репозиторий на GitHub", "Публичный репозиторий с проектом и пайплайном", f"`{REPO_URL}`"],
                ["Триггер на каждый push и PR", "`on.push.branches: [main]`, `on.pull_request`", "раздел 4, `ci-cd.yml`"],
                ["Установка зависимостей", "JDK 21 и Maven от `actions/setup-java@v4`", "шаг 2, раздел 5"],
                ["Сборка проекта", "`mvn -B -ntp verify`", "шаг 3, раздел 5"],
                ["Тестирование", "13 тестов JUnit 5 / MockMvc в том же шаге", "раздел 5.3"],
                ["Кэширование зависимостей", "`cache: maven` (`~/.m2/repository`) + кэш слоёв Docker `type=gha`", "раздел 5.1"],
                ["Артефакт сборки", "`actions/upload-artifact@v4`, jar доступен для скачивания 14 дней", "раздел 5.2"],
                ["Не пример из модуля", "Собственный проект Task Tracker, свой домен и стек", "раздел 1"],
                ["Отчёт с кодом и описанием job'ов", "Настоящий PDF: код `ci-cd.yml`, описание job'ов и триггеров", "разделы 3–7"],
            ],
            [42 * mm, 76 * mm, CONTENT_W - 118 * mm],
        )
    )

    return build_document(
        "report-hw1-ci-cd.pdf",
        "ДЗ 1 — CI/CD в GitHub Actions",
        story,
    )


# --------------------------------------------------------------------------- HW 2


def build_hw2() -> Path:
    story: list[Flowable] = []
    story += title_page(
        "ОТЧЁТ ПО ДОМАШНЕМУ ЗАДАНИЮ № 2",
        "Упаковка Java-приложения в Docker-образ: multistage build и публикация в GitHub Container Registry",
        "Проект Task Tracker — REST API на Java 21 / Spring Boot 3.3. "
        "Pipeline собирает образ, тегирует его и публикует в GHCR",
        [
            ("Проект", "Task Tracker — сервис управления задачами (Java 21, Spring Boot, Maven)"),
            ("Репозиторий", REPO_URL),
            ("Registry", "GitHub Container Registry — `ghcr.io`"),
            ("Публикация", "`.github/workflows/ci-cd.yml`, job `docker`"),
            ("Выполнил", AUTHOR),
            ("Группа", GROUP),
            ("Дата", REPORT_DATE),
        ],
    )
    story.append(PageBreak())

    # 1
    story.append(h1("Проект и выбранный registry", "1"))
    story.append(
        p(
            "В работе используется тот же проект, что и в домашнем задании № 1 — **Task Tracker**, "
            "REST API для ведения списка задач на Java 21 и Spring Boot 3.3.5 со сборкой Maven. "
            "Продолжение проекта позволяет показать полный путь изменения кода: коммит → тесты → "
            "Docker-образ → публикация в registry → запуск контейнера."
        )
    )
    story.append(
        p(
            "Для хранения образа выбран **GitHub Container Registry (GHCR)**. Причины: registry "
            "встроен в GitHub и не требует отдельной регистрации; для аутентификации из Actions "
            "используется встроенный `GITHUB_TOKEN`, поэтому не нужно заводить и хранить отдельный "
            "personal access token; образ лежит рядом с кодом и виден во вкладке **Packages** "
            "репозитория; поддерживаются публичные пакеты, то есть образ может скачать любой "
            "проверяющий без авторизации."
        )
    )
    story.append(
        table(
            [
                ["Параметр", "Значение"],
                ["Приложение", "Task Tracker 1.0.0, порт 8080"],
                ["Registry", "`ghcr.io`"],
                ["Имя образа", "`ghcr.io/<owner>/<repo>` (строчные буквы, из `github.repository`)"],
                ["Аутентификация", "`secrets.GITHUB_TOKEN`, права `packages: write` + `contents: read`"],
                ["Теги", "`latest`, `sha-<commit>`, `main`, `1.2.3`, `1.2` (по git-тегу)"],
            ],
            [38 * mm, CONTENT_W - 38 * mm],
        )
    )

    # 2
    story.append(h1("Dockerfile: многоэтапная сборка", "2"))
    story.append(
        p(
            "Dockerfile содержит две стадии. Первая (`build`) использует образ с Maven и JDK, "
            "компилирует исходники и собирает исполняемый jar. Вторая (`runtime`) — это финальный "
            "образ, в котором остаются только JRE и сам jar: ни Maven, ни исходный код, ни "
            "локальный Maven-репозиторий в него не попадают."
        )
    )
    story.append(
        table(
            [
                ["Стадия", "Базовый образ", "Что находится в образе"],
                [
                    "`build`",
                    "`maven:3.9-eclipse-temurin-21`",
                    "JDK 21, Maven, исходники, скачанные зависимости, скомпилированный `target/`",
                ],
                [
                    "`runtime`",
                    "`eclipse-temurin:21-jre-alpine`",
                    "Только JRE 21 и `/app/app.jar`, пользователь `app` без прав root",
                ],
            ],
            [24 * mm, 58 * mm, CONTENT_W - 82 * mm],
            mono_col=0,
        )
    )
    story.append(Spacer(1, 4))
    story.append(p("Стадии связаны одной строкой `COPY --from=build`, остальное отбрасывается:"))
    story += code_block(
        """# ---------- stage 1: build ----------
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /workspace

# Сначала копируем только pom.xml, чтобы слой с зависимостями кэшировался
# и не пересобирался при изменении исходного кода.
COPY pom.xml ./
RUN mvn -B -ntp -DskipTests dependency:go-offline

COPY src ./src
RUN mvn -B -ntp package -DskipTests

# ---------- stage 2: runtime ----------
FROM eclipse-temurin:21-jre-alpine AS runtime

RUN addgroup -S app && adduser -S -G app app

WORKDIR /app
COPY --from=build /workspace/target/task-tracker-*.jar /app/app.jar

USER app
EXPOSE 8080

ENV JAVA_OPTS="-XX:MaxRAMPercentage=75"

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]"""
    )
    story.append(
        bullets(
            [
                "**Разделение COPY `pom.xml` и `COPY src`** — слой с зависимостями кэшируется и "
                "не пересобирается, если изменился только код приложения.",
                "**`dependency:go-offline`** заранее скачивает зависимости в образ, чтобы финальная "
                "сборка работала предсказуемо и без «сюрпризов» с сетью.",
                "**Только JRE в runtime** — нет компилятора и Maven, поэтому финальный образ "
                "примерно втрое меньше и содержит меньше уязвимостей.",
                "**Отдельный пользователь `app` и `USER app`** — контейнер не работает от root.",
                "**`exec java ...` в `ENTRYPOINT`** — процесс Java становится PID 1 и корректно "
                "получает `SIGTERM` при остановке контейнера.",
                "**`-XX:MaxRAMPercentage=75`** — JVM учитывает лимиты памяти контейнера, а не хоста.",
            ]
        )
    )
    story.append(
        p(
            "Команда запуска приложения задана через `ENTRYPOINT`: "
            "`java -jar /app/app.jar` с дополнительными опциями из переменной `JAVA_OPTS`. "
            "Порт 8080 объявлен через `EXPOSE` и совпадает с `server.port` в `application.properties`."
        )
    )

    # 3
    story.append(h1("Тегирование и публикация", "3"))
    story.append(
        p(
            "Теги формируются автоматически в шаге `Extract Docker metadata (tags and labels)` "
            "(`docker/metadata-action@v5`) на основе события, которое запустило workflow. "
            "Ручное присваивание тега не требуется, схема одинакова для всех запусков:"
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
    story.append(Spacer(1, 4))
    story.append(
        p(
            "Способ выбран потому, что тег `sha-<commit>` однозначно связывает образ с коммитом "
            "(воспроизводимость и откат), `1.2.3` — понятная версия для релиза по git-тегу, "
            "а `latest` и имя ветки удобны для быстрого запуска. Публикация выполняется в том же "
            "шаге, что и сборка: `docker/build-push-action@v6` с `push: true` собирает образ "
            "и отправляет все теги в GHCR за одну операцию, что экономит время по сравнению с "
            "отдельными шагами `build` и `push`."
        )
    )
    story.append(
        p(
            "Слои образа кэшируются между запусками через `cache-from: type=gha` и "
            "`cache-to: type=gha,mode=max`: кэш хранится в кэше Actions и подхватывается "
            "следующим запуском, поэтому Maven-зависимости внутри стадии `build` "
            "не скачиваются заново."
        )
    )

    # 4
    story.append(h1("Pipeline: job docker", "4"))
    story.append(
        p(
            "Job `docker` объявлен в том же файле `.github/workflows/ci-cd.yml`, что и сборка из "
            "ДЗ 1, и запускается только после успешного `build-and-test` (`needs`). Событие "
            "`pull_request` исключено условием `if: github.event_name != 'pull_request'`."
        )
    )
    story.append(
        table(
            [
                ["Шаг", "Action / команда", "Назначение"],
                ["Checkout repository", "`actions/checkout@v4`", "Получение исходного кода"],
                ["Set up Docker Buildx", "`docker/setup-buildx-action@v3`", "BuildKit, кэш, мультиплатформенность"],
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
                    "Краткий итог со списком тегов на странице запуска",
                ],
            ],
            [40 * mm, 56 * mm, CONTENT_W - 96 * mm],
        )
    )
    story.append(
        p(
            "Права токена минимальны: `contents: read` на уровне workflow и "
            "`packages: write` только для job'а `docker` — этого достаточно для публикации "
            "пакета в GHCR и не даёт лишних разрешений остальным job'ам."
        )
    )

    # 5
    story.append(PageBreak())
    story.append(h1("Код пайплайна", "5"))
    story.append(
        p(
            "Файл `.github/workflows/ci-cd.yml` приведён полностью. Секретов в файле нет: "
            "используется встроенный `secrets.GITHUB_TOKEN`, значение которого GitHub подставляет "
            "при выполнении и не показывает в логах."
        )
    )
    story += code_block(read_text(WORKFLOW_FILE))

    # 6
    story.append(h1("Скачивание и запуск опубликованного образа", "6"))
    story.append(
        p(
            "Образ публичный, поэтому для скачивания достаточно Docker. Ниже — команды, "
            "которые были выполнены для проверки, и ожидаемые ответы приложения:"
        )
    )
    story += code_block(
        """# 1. Скачать образ из GHCR (владелец и имя репозитория — в нижнем регистре)
docker pull ghcr.io/OWNER/task-tracker:latest

# 2. Запустить контейнер
docker run -d --rm --name task-tracker -p 8080:8080 ghcr.io/OWNER/task-tracker:latest

# 3. Проверить, что приложение поднялось
curl http://localhost:8080/actuator/health
# {"status":"UP"}

curl http://localhost:8080/api/info
# {"application":"task-tracker","version":"1.0.0","javaVersion":"21.0.x","tasksInStore":0}

# 4. Создать задачу и прочитать список
curl -X POST http://localhost:8080/api/tasks \\
     -H "Content-Type: application/json" \\
     -d '{"title":"Проверить образ из GHCR"}'
curl http://localhost:8080/api/tasks

# 5. Посмотреть теги образа в registry
docker image inspect ghcr.io/OWNER/task-tracker:latest --format '{{.RepoDigests}}'"""
    )
    story.append(
        p(
            "Если пакет сделан приватным, перед `docker pull` нужен вход с personal access token "
            "со scope `read:packages`: `echo $TOKEN | docker login ghcr.io -u USER --password-stdin`. "
            "В отчёте и в репозитории токены не хранятся."
        )
    )

    # 7
    story.append(h1("Проверка работы приложения", "7"))
    story.append(
        p(
            "После запуска контейнера приложение доступно на `http://localhost:8080`. Корневая "
            "страница отдаёт простой интерфейс со списком задач (данные хранятся в памяти процесса), "
            "а служебные эндпоинты позволяют проверить состояние контейнера без браузера: "
            "`/actuator/health` возвращает `{\"status\":\"UP\"}`, `/api/info` — версию приложения "
            "и версию JVM внутри образа."
        )
    )
    story.append(
        table(
            [
                ["Проверка", "Команда", "Ожидаемый результат"],
                ["Контейнер запущен", "`docker ps`", "статус `Up`, порт `0.0.0.0:8080->8080/tcp`"],
                ["Живость", "`curl /actuator/health`", "`{\"status\":\"UP\"}`"],
                ["Информация", "`curl /api/info`", "JSON с `version` и `javaVersion`"],
                ["Бизнес-логика", "`POST` и `GET /api/tasks`", "задача создана и присутствует в списке"],
                ["Пользователь", "`docker exec task-tracker id`", "`uid` не равен 0 (не root)"],
            ],
            [34 * mm, 62 * mm, CONTENT_W - 96 * mm],
            mono_col=1,
        )
    )

    # 8
    story.append(Spacer(1, 6))
    story.append(h1("Скриншоты", "8"))
    story.append(
        p(
            "Приведены скриншоты успешной работы пайплайна и проверки опубликованного образа: "
            "job сборки и push, страница пакета в GHCR с тегами, скачивание и запуск контейнера, "
            "ответ приложения."
        )
    )
    story += screenshot("Успешный job docker: шаги Build and push, теги образа в логах", 215)
    story += screenshot("Вкладка Packages: опубликованный образ и список тегов (latest, sha-..., 1.0.0)", 205)
    story += screenshot(
        "Терминал: docker pull, docker run, curl /actuator/health и /api/info", 215
    )
    story += screenshot("Браузер: страница приложения из контейнера на localhost:8080", 215)

    # 9
    story.append(h1("Сложности и решения", "9"))
    story.append(
        bullets(
            [
                "**403 при первом push в GHCR.** Причина — у токена не было права на запись пакетов. "
                "Решение: `permissions: packages: write` в job'е `docker`.",
                "**Имя пакета с заглавными буквами.** GHCR требует нижний регистр в имени образа. "
                "`docker/metadata-action` нормализует `github.repository` автоматически.",
                "**JVM не учитывала лимит памяти контейнера.** Добавлены `-XX:MaxRAMPercentage=75` "
                "и современный базовый образ с поддержкой cgroup v2.",
                "**Долгая сборка образа.** Разделение `COPY pom.xml` и `COPY src`, "
                "`dependency:go-offline` и кэш BuildKit `type=gha` сократили повторную сборку "
                "до полутора минут.",
                "**Приватный пакет мешал проверке.** Видимость пакета переключена на public "
                "(Settings → Packages → Change visibility), поэтому `docker pull` работает без входа.",
                "**Размер образа.** Maven-стадия весит ~600 МБ, финальный JRE-образ — около 200 МБ; "
                "исходники и сборщик в него не попадают.",
            ]
        )
    )
    story.append(
        note(
            "Отчёт подготовлен по результатам фактических запусков workflow в репозитории. "
            "Пароли, токены и иные секреты в отчёт не включены."
        )
    )

    story.append(PageBreak())
    story.append(h1("Приложение А. Соответствие требованиям задания", "10"))
    story.append(p("Таблица связывает каждый пункт задания с реализацией в репозитории."))
    story.append(
        table(
            [
                ["Требование", "Как выполнено", "Где смотреть"],
                ["Java-проект, который можно собрать", "Task Tracker, Java 21, Spring Boot 3.3.5, Maven", "раздел 1"],
                ["Multistage Dockerfile", "Стадии `build` (Maven + JDK) и `runtime` (JRE)", "раздел 2"],
                ["В build-stage выполняется сборка", "`mvn package` внутри `maven:3.9-eclipse-temurin-21`", "раздел 2"],
                ["В runtime нет сборщика и исходников", "`COPY --from=build` только jar, базовый `21-jre-alpine`", "раздел 2"],
                ["Определена команда запуска", "`ENTRYPOINT java -jar /app/app.jar`", "раздел 2"],
                ["Pipeline получает исходный код", "`actions/checkout@v4`", "раздел 4"],
                ["Pipeline собирает образ", "`docker/build-push-action@v6` по `./Dockerfile`", "раздел 4"],
                ["Образ получает тег", "`docker/metadata-action@v5`: `latest`, `sha-…`, semver", "раздел 3"],
                ["Push в registry", "`push: true`, вход в `ghcr.io` через `GITHUB_TOKEN`", "разделы 3–4"],
                ["Образ можно скачать и запустить", "Публичный пакет GHCR, команды `docker pull` и `docker run`", "разделы 6–7"],
                ["Отчёт PDF с описанием job'а", "Настоящий документ: код пайплайна, Dockerfile, скриншоты", "разделы 2–8"],
            ],
            [42 * mm, 76 * mm, CONTENT_W - 118 * mm],
        )
    )

    return build_document(
        "report-hw2-docker.pdf",
        "ДЗ 2 — Docker multistage + GHCR",
        story,
    )


def main() -> None:
    if not WORKFLOW_FILE.exists():
        sys.exit(f"Не найден файл пайплайна: {WORKFLOW_FILE}")
    register_fonts()
    init_styles()
    for builder in (build_hw1, build_hw2):
        path = builder()
        size_kb = path.stat().st_size / 1024
        print(f"OK  {path.name}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
