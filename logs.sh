#!/usr/bin/env bash

set -e

function sync {
    echo "$(tput setaf 4)$1$(tput sgr0)"
    eval $1
}

sync "gcloud logging read 'resource.labels.cluster_name=mesh-cluster AND resource.labels.container_name=reviews' --limit 10 --format='table(textPayload)'"
