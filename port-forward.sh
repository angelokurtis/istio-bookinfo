#!/usr/bin/env bash

nohup kubectl port-forward svc/grafana -n istio-system 3000:3000 >/dev/null 2>&1 &
echo "Forwarding Grafana - http://localhost:3000"
nohup kubectl port-forward svc/kiali -n istio-system 20001:20001 >/dev/null 2>&1 &
echo "Forwarding Kiali - http://localhost:20001/kiali/"
nohup kubectl port-forward svc/tracing -n istio-system 8080:80 >/dev/null 2>&1 &
echo "Forwarding Jaeger - http://localhost:8080"
