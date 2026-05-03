# Multi-stage build: gradle JDK17 → JRE17 runtime image.
FROM gradle:8.7-jdk17-alpine AS builder
WORKDIR /home/gradle/src
COPY --chown=gradle:gradle . .
RUN gradle bootJar --no-daemon

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=builder /home/gradle/src/build/libs/wcp-java-api.jar /app/app.jar

# Spring Boot 3 expects a non-root user where possible.
RUN addgroup -S wcp && adduser -S wcp -G wcp
USER wcp

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
