FROM maven:3.9.9-eclipse-temurin-21 AS maven
FROM docker:29-cli AS docker
FROM jenkins/jenkins:lts-jdk21
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 curl \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory /repo
COPY --from=maven /usr/share/maven /usr/share/maven
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
ENV MAVEN_HOME=/usr/share/maven
ENV PATH=/usr/share/maven/bin:$PATH
USER jenkins
RUN jenkins-plugin-cli --plugins workflow-aggregator git junit
COPY init.groovy /usr/share/jenkins/ref/init.groovy.d/pulsegrid.groovy
USER root
RUN git config --system --add safe.directory /repo/.git
USER jenkins
