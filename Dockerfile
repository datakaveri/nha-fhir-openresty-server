FROM hapiproject/hapi:latest AS base

# Use a JDK image to patch the WAR and replace the logo
FROM eclipse-temurin:21-jdk AS patcher
COPY --from=base /app/main.war /tmp/main.war
COPY nha.png /tmp/nha.png
WORKDIR /tmp/war-extract
RUN jar xf /tmp/main.war && \
    cp /tmp/nha.png img/hapi_fhir_banner.png && \
    cp /tmp/nha.png img/hapi_fhir_banner_narrow.png && \
    cp /tmp/nha.png img/hapi_fhir_banner_right.png && \
    cp /tmp/main.war /tmp/patched-main.war && \
    jar uf /tmp/patched-main.war \
      img/hapi_fhir_banner.png \
      img/hapi_fhir_banner_narrow.png \
      img/hapi_fhir_banner_right.png

# Final image: copy patched WAR back into the original HAPI image
FROM hapiproject/hapi:latest
COPY --from=patcher /tmp/patched-main.war /app/main.war
