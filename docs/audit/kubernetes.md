# Kubernetes / Helm Audit

> **Historical snapshot (2026-04-14)** — This is part of the homelab audit series. Some services listed here have since been retired. Refer to the audit README for current status.

## Cluster state
      1 observability promtail-promtail-k5j8d Evicted 0
      1 observability prometheus-prometheus-7d867d959b-v48ml Completed 9
      1 observability prometheus-prometheus-7d867d959b-gwnsn Pending 0
      1 observability loki-loki-5b5957944c-s8z85 Completed 14
      1 observability loki-loki-5b5957944c-f5kbz Pending 0
      1 observability grafana-grafana-869d78f8f4-jqp6h ContainerStatusUnknown 15
      1 observability grafana-grafana-869d78f8f4-cfmnx Pending 0
      1 observability blackbox-exporter-blackbox-exporter-8454f8bd4d-smwvb Pending 0
      1 observability blackbox-exporter-blackbox-exporter-8454f8bd4d-r7t2s ContainerStatusUnknown 11
      1 observability alertmanager-alertmanager-5c7d498f56-99p6j Pending 0
      1 observability alertmanager-alertmanager-5c7d498f56-4fnk7 ContainerStatusUnknown 15
      1 kube-system traefik-788bc4688c-ns2qc Running 10
      1 kube-system metrics-server-c8774f4f4-rxcfh Running 24
      1 kube-system local-path-provisioner-546dfc6456-49v6h Running 18
      1 kube-system helm-install-traefik-czhf5 Completed 2
      1 kube-system helm-install-traefik-crd-x8jpp Completed 0
      1 kube-system coredns-695cbbfcb9-ldpm8 Running 15
      1 apps vaultwarden-vaultwarden-8594bc8b99-x8n6f ContainerStatusUnknown 9
      1 apps vaultwarden-vaultwarden-8594bc8b99-tb7ml Pending 0
      1 apps uptime-kuma-uptime-kuma-6d685fc898-p2h6r Error 12
      1 apps uptime-kuma-uptime-kuma-6d685fc898-ljctf Pending 0
      1 apps pihole-pihole-7f7c6f8975-s9fxb Error 12
      1 apps pihole-pihole-7f7c6f8975-bjftw Pending 0
      1 apps nextcloud-redis-7fbc6b9858-hz44x Completed 5
      1 apps nextcloud-redis-7fbc6b9858-dxrbx Pending 0
      1 apps nextcloud-nextcloud-8588f5b448-jz4l9 Completed 5
      1 apps nextcloud-nextcloud-8588f5b448-5rqj2 Pending 0
      1 apps nextcloud-mariadb-bbfcd4dc8-lvzcl ContainerStatusUnknown 5
      1 apps nextcloud-mariadb-bbfcd4dc8-224cj Pending 0
      1 apps jellyfin-jellyfin-d74c8bb4d-qtxnb Completed 7

## Zombie pods (not Running/Completed OR restart>3)
apps            authentik-authentik-server-d5f75cc8-rzsrn              0/1   Pending                  0             23h
apps            authentik-authentik-worker-7bc9dc678b-5p2wq            0/1   Error                    3             17d
apps            authentik-authentik-worker-7bc9dc678b-ldg8s            0/1   Pending                  0             23h
apps            authentik-postgresql-597597b794-j65wq                  0/1   Completed                6 (5d ago)    29d
apps            authentik-postgresql-597597b794-j7ckl                  0/1   Pending                  0             23h
apps            authentik-redis-7d6dbf5ddb-mjmvg                       0/1   Completed                5 (5d ago)    29d
apps            authentik-redis-7d6dbf5ddb-ssgnc                       0/1   Pending                  0             23h
apps            filebrowser-filebrowser-584fd8c96b-jkmk7               0/1   Pending                  0             23h
apps            filebrowser-filebrowser-584fd8c96b-wdz84               0/1   Completed                8 (5d ago)    30d
apps            homeassistant-homeassistant-5dcf975755-msh5h           0/1   Pending                  0             23h
apps            homeassistant-homeassistant-5dcf975755-r4p89           0/1   ContainerStatusUnknown   8 (5d ago)    29d
apps            homepage-homepage-58999cf88-hfqch                      0/1   Pending                  0             23h
apps            homepage-homepage-58999cf88-md44k                      0/1   Completed                12 (5d ago)   30d
apps            jellyfin-jellyfin-d74c8bb4d-gzmnz                      0/1   Pending                  0             23h
apps            jellyfin-jellyfin-d74c8bb4d-qtxnb                      0/1   Completed                7 (5d ago)    29d
apps            nextcloud-mariadb-bbfcd4dc8-224cj                      0/1   Pending                  0             23h
apps            nextcloud-mariadb-bbfcd4dc8-lvzcl                      0/1   ContainerStatusUnknown   5 (5d ago)    29d
apps            nextcloud-nextcloud-8588f5b448-5rqj2                   0/1   Pending                  0             23h
apps            nextcloud-nextcloud-8588f5b448-jz4l9                   0/1   Completed                5 (5d ago)    29d
apps            nextcloud-redis-7fbc6b9858-dxrbx                       0/1   Pending                  0             23h
apps            nextcloud-redis-7fbc6b9858-hz44x                       0/1   Completed                5 (5d ago)    29d
apps            pihole-pihole-7f7c6f8975-bjftw                         0/1   Pending                  0             23h
apps            pihole-pihole-7f7c6f8975-s9fxb                         0/1   Error                    12            30d
apps            uptime-kuma-uptime-kuma-6d685fc898-ljctf               0/1   Pending                  0             23h
apps            uptime-kuma-uptime-kuma-6d685fc898-p2h6r               0/1   Error                    12            30d
apps            vaultwarden-vaultwarden-8594bc8b99-tb7ml               0/1   Pending                  0             23h
apps            vaultwarden-vaultwarden-8594bc8b99-x8n6f               0/1   ContainerStatusUnknown   9 (5d ago)    30d
kube-system     coredns-695cbbfcb9-ldpm8                               1/1   Running                  15 (5d ago)   34d
kube-system     local-path-provisioner-546dfc6456-49v6h                1/1   Running                  18 (5d ago)   34d
kube-system     metrics-server-c8774f4f4-rxcfh                         0/1   Running                  24 (5d ago)   34d

## PVCs
NAMESPACE       NAME                                 STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
apps            authentik-authentik-media            Bound    pvc-7a183d54-d9fc-4f46-9aac-b222531d6936   1Gi        RWO            local-path     <unset>                 29d
apps            authentik-postgresql-data            Bound    pvc-f4abddd5-fade-4a2a-8ddf-37213359072b   5Gi        RWO            local-path     <unset>                 29d
apps            filebrowser-filebrowser-db           Bound    pvc-2252d02a-1ab6-451b-b535-7be8f049f9e1   100Mi      RWO            local-path     <unset>                 30d
apps            homeassistant-homeassistant-config   Bound    pvc-04cee79e-0225-4e5e-a2be-851ebb5e53bd   5Gi        RWO            local-path     <unset>                 29d
apps            homepage-homepage                    Bound    pvc-362ac2b4-cf62-437a-8a7d-7b07493e11ea   1Gi        RWO            local-path     <unset>                 30d
apps            jellyfin-jellyfin-cache              Bound    pvc-53162ed1-5159-4425-8821-6234ffe3b4f7   10Gi       RWO            local-path     <unset>                 29d
apps            jellyfin-jellyfin-config             Bound    pvc-8ff516dd-628b-4f5a-b657-9d56a2438f8d   5Gi        RWO            local-path     <unset>                 29d
apps            n8n-n8n-data                         Bound    pvc-02b43dd0-2c03-4061-9fcc-b30c5d7bc0a6   2Gi        RWO            local-path     <unset>                 30d
apps            nextcloud-mariadb-data               Bound    pvc-d7c19e35-9a96-41ee-bcdd-6a3bc30e2121   5Gi        RWO            local-path     <unset>                 29d

## Services exposed
apps            filebrowser-filebrowser               NodePort    10.43.181.131   <none>        80:30080/TCP             30d

## Helm charts inventory
=== k8s/helm/alertmanager/Chart.yaml ===
name: alertmanager
version: 0.1.0
appVersion: "latest"
=== k8s/helm/authentik/Chart.yaml ===
name: authentik
version: 0.1.0
appVersion: "2025.2.4"
=== k8s/helm/blackbox-exporter/Chart.yaml ===
name: blackbox-exporter
version: 0.1.0
appVersion: "latest"
=== k8s/helm/filebrowser/Chart.yaml ===
name: filebrowser
version: 0.1.0
appVersion: "latest"
=== k8s/helm/grafana/Chart.yaml ===
name: grafana
version: 0.1.0
appVersion: "latest"
=== k8s/helm/homeassistant/Chart.yaml ===
name: homeassistant
version: 0.1.0
appVersion: "stable"
=== k8s/helm/homepage/Chart.yaml ===
name: homepage
version: 0.1.0
appVersion: "latest"
=== k8s/helm/jellyfin/Chart.yaml ===
name: jellyfin
version: 0.1.0
appVersion: "latest"
=== k8s/helm/loki/Chart.yaml ===
name: loki
version: 0.1.0
appVersion: "latest"
=== k8s/helm/n8n/Chart.yaml ===
name: n8n
version: 0.1.0
appVersion: "latest"
=== k8s/helm/nextcloud/Chart.yaml ===
name: nextcloud
version: 0.1.0
appVersion: "latest"
=== k8s/helm/paperless/Chart.yaml ===
name: paperless
version: 0.1.0
appVersion: "latest"
=== k8s/helm/pihole/Chart.yaml ===
name: pihole
version: 0.1.0
appVersion: "latest"
=== k8s/helm/prometheus/Chart.yaml ===
name: prometheus
version: 0.1.0
appVersion: "latest"
=== k8s/helm/promtail/Chart.yaml ===
name: promtail
version: 0.1.0
appVersion: "latest"
=== k8s/helm/uptime-kuma/Chart.yaml ===
name: uptime-kuma
version: 0.1.0
appVersion: "1"
=== k8s/helm/vaultwarden/Chart.yaml ===
name: vaultwarden
version: 0.1.0
appVersion: "latest"

## NetworkPolicies present
default-deny.yaml
limit-ranges.yaml
resource-quotas.yaml

## Apps duplicated (compose AND helm)
homeassistant
n8n
nextcloud
