#!/usr/bin/env bash

set -e

function sync {
    echo "$(tput setaf 4)$1$(tput sgr0)"
    eval $1
}

function async {
    echo "$(tput setaf 4)$1$(tput sgr0)"
    nohup $1 >/dev/null 2>&1 &
}

ps aux | grep '[k]ubectl.*port-forward.*svc/grafana.'| grep -v grep | awk '{print $2}' | xargs -r kill
async "kubectl port-forward svc/grafana -n istio-system 3000:3000"
echo "Forwarding Grafana - http://localhost:3000/"

ps aux | grep '[k]ubectl.*port-forward.*svc/kiali.'| grep -v grep | awk '{print $2}' | xargs -r kill
async "kubectl port-forward svc/kiali -n istio-system 20001:20001"
echo "Forwarding Kiali - http://localhost:20001/kiali/"

ps aux | grep '[k]ubectl.*port-forward.*svc/tracing.'| grep -v grep | awk '{print $2}' | xargs -r kill
async "kubectl port-forward svc/tracing -n istio-system 9411:9411"
echo "Forwarding Jaeger - http://localhost:9411/jaeger/search/"

sync "ps aux | grep '[k]ubectl.'"

