# Multi-stage build: gradle JDK17 → JRE17 runtime image.
# Use jammy variants (multi-arch incl. arm64); alpine variants are amd64-only
# for these images, which breaks builds on Apple Silicon.
FROM gradle:8.7-jdk17-jammy AS builder
WORKDIR /home/gradle/src
COPY --chown=gradle:gradle . .
RUN gradle bootJar --no-daemon

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
COPY --from=builder /home/gradle/src/build/libs/wcp-java-api.jar /app/app.jar

# Spring Boot 3 expects a non-root user where possible.
RUN groupadd -r wcp && useradd -r -g wcp wcp
USER wcp

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
