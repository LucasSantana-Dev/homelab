FROM ghcr.io/oraios/serena:v0.1.4

USER root

ARG TERRAFORM_VERSION=1.14.6
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl unzip nodejs npm; \
    if ! getent group 1000 >/dev/null; then groupadd -g 1000 serena; fi; \
    if ! getent passwd 1000 >/dev/null; then useradd -m -u 1000 -g 1000 serena; fi; \
    mkdir -p /solidlsp_tmp; \
    chmod 1777 /solidlsp_tmp; \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip; \
    unzip -o /tmp/terraform.zip -d /usr/local/bin; \
    chmod 0755 /usr/local/bin/terraform; \
    rm -rf /var/lib/apt/lists/* /tmp/terraform.zip
