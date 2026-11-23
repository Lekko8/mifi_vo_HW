# Task Tracker — CI/CD в GitHub Actions

Учебный проект для домашних заданий по CI/CD: небольшой REST-сервис на Java 21 / Spring Boot,
который собирается, тестируется и упаковывается в Docker-образ автоматически в GitHub Actions,
а образ публикуется в GitHub Container Registry (GHCR).

[![CI/CD](https://github.com/Lekko8/mifi_vo_HW/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Lekko8/mifi_vo_HW/actions/workflows/ci-cd.yml)

## Стек

| Компонент | Версия |
|---|---|
| Java | 21 (Temurin) |
| Spring Boot | 3.3.5 |
| Сборка | Maven (Spring Boot Maven Plugin) |
| Тесты | JUnit 5, AssertJ, MockMvc |
| Контейнеризация | Docker, multistage build |
| CI/CD | GitHub Actions |
| Registry | GitHub Container Registry (`ghcr.io`) |

## REST API

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/` | Веб-страница со списком задач |
| `GET` | `/api/tasks` | Список задач |
| `GET` | `/api/tasks/{id}` | Задача по идентификатору |
| `POST` | `/api/tasks` | Создать задачу `{"title": "..."}` |
| `PATCH` | `/api/tasks/{id}` | Изменить статус `{"done": true}` |
| `DELETE` | `/api/tasks/{id}` | Удалить задачу |
| `GET` | `/api/info` | Версия приложения и версия JVM |
| `GET` | `/actuator/health` | Проверка живости (для контейнера и CI) |

Данные хранятся в памяти — при перезапуске контейнера список задач пустой.
Это осознанное решение: проект демонстрирует CI/CD, а не работу с базой данных.

## Запуск локально

```bash
mvn spring-boot:run
# или
mvn -B verify
java -jar target/task-tracker-1.0.0.jar
```

Приложение: <http://localhost:8080>, проверка: <http://localhost:8080/actuator/health>.

## Docker

Сборка (multistage: `maven:3.9-eclipse-temurin-21` → `eclipse-temurin:21-jre-alpine`):

```bash
docker build -t task-tracker:local .
docker run --rm -p 8080:8080 task-tracker:local
```

## Образ в GHCR

Имя пакета в GHCR — это имя репозитория в нижнем регистре: `ghcr.io/lekko8/mifi_vo_hw`.

```bash
docker pull ghcr.io/lekko8/mifi_vo_hw:latest
docker run -d --rm --name task-tracker -p 8080:8080 ghcr.io/lekko8/mifi_vo_hw:latest

curl http://localhost:8080/actuator/health     # {"status":"UP"}
curl http://localhost:8080/api/info
curl -X POST http://localhost:8080/api/tasks \
     -H 'Content-Type: application/json' -d '{"title":"Проверить образ"}'
```

Если пакет приватный, нужен вход в GHCR с personal access token (scope `read:packages`):

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u lekko8 --password-stdin
```

## Тегирование образа

Теги формируются `docker/metadata-action` из события, которое запустило workflow:

| Событие | Теги образа |
|---|---|
| push в `main` | `latest`, `main`, `sha-<короткий коммит>` |
| push тега `v1.2.3` | `1.2.3`, `1.2`, `sha-<короткий коммит>` |
| push в другую ветку | `<имя-ветки>`, `sha-<короткий коммит>` |

Подробная схема — в разделе «Тегирование» отчёта по ДЗ 2.

## Пайплайн

Файл: [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml)

1. **build-and-test** — `actions/checkout@v4`, `actions/setup-java@v4` (Temurin 21, кэш
   `~/.m2/repository` по хешу `pom.xml`), `mvn -B -ntp verify`, затем
   `actions/upload-artifact@v4` публикует `task-tracker-*.jar` (хранится 14 дней).
2. **docker** — `docker/setup-buildx-action@v3`, `docker/login-action@v3` (GHCR,
   `secrets.GITHUB_TOKEN`), `docker/metadata-action@v5`, `docker/build-push-action@v6`
   с кэшем слоёв `type=gha`. Запускается только на push в `main` / push тега, не на PR.

## Структура

```
├── .github/workflows/ci-cd.yml   # пайплайн: сборка, тесты, артефакт, Docker, GHCR
├── Dockerfile                    # multistage: build -> runtime
├── pom.xml
├── docs/report/                  # PDF-отчёты по ДЗ 1 и ДЗ 2 + скрипт генерации
├── src/main/java/com/example/tasktracker/
│   ├── api/                      # контроллеры и обработчик ошибок
│   ├── model/                    # Task, TaskRequest, TaskNotFoundException
│   └── service/                  # TaskService (in-memory хранилище)
├── src/main/resources/
│   ├── application.properties
│   └── static/index.html         # простой UI для проверки работы образа
└── src/test/java/                # 13 тестов: сервис + MockMvc
```

## Секреты

Никаких дополнительных секретов не требуется: для GHCR используется встроенный
`GITHUB_TOKEN` с правами `packages: write` (объявлены в разделе `permissions`).
