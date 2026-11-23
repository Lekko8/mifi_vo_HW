# syntax=docker/dockerfile:1

# ---------- stage 1: build ----------
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

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
