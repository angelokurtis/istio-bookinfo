# Consul Adapter for Istio on Docker

Make Istio run in docker environment by integrating Consul as a service registry.

## Design Principle

The key issue is how to implement the ServiceDiscovery interface functions in Istio.
This platform adapter uses Consul Server to help Istio monitor service instances running in the underlying platform.
When a service instance is brought up in docker, the [Registrator](http://gliderlabs.github.io/registrator/latest/)
automatically registers the service in Consul.

Note that Istio pilot is running inside each app container so as to coordinate Envoy and the service mesh.

## Prerequisites

 * Clone Istio Pilot [repo](https://github.com/istio/pilot) (required only if building images locally)

 * Download istioctl from Istio's [releases page](https://github.com/istio/istio/releases) or build from
 source in Istio Pilot repository

## Bookinfo Demo

The ingress controller is still under construction, routing functionalities can be tested by curling a service container directly.

First step is to configure istioctl to use the apiserver created in the steps below:

```
istioctl context-create --api-server http://172.28.0.13:8080
```

To build all images for the bookinfo sample for the consul adapter, run:

  ```
  ./build-docker-services.sh
  ```

To bring up the control plane containers directly, from the `samples/bookinfo/consul` directory run

  ```
  docker-compose -f control-plane.yaml up -d
  ```

This will pull images from docker hub to your local computing space.

Now you can see all the containers in the mesh by running `docker ps -a`.

If the webpage is not displaying properly, you may need to run the previous command once more to resolve a timing issue during start up.

NOTE: If Mac users experience an error starting the consul service in the `docker-compose up -d` command, 
open your `control-plane.yaml` and overwrite the `consul` service with the following and re-run the `up -d` command :
```
  consul:
    image: gliderlabs/consul-server
    networks:
      envoymesh:
        aliases:
          - consul
    ports:
      - "8500:8500"
      - "53:8600/udp"
      - "8400:8400"
    environment:
      - SERVICE_IGNORE=1
    command: ["-bootstrap"]
```

To bring up the app containers, from the `samples/bookinfo/consul` directory run

  ```
  docker-compose -f bookinfo.yaml up -d
  ```


To view the productpage webpage, open a web browser and enter `localhost:9081/productpage`.  

If you refresh the page several times, you should see different versions of reviews shown in productpage presented in a round robin style (red stars, black stars, no stars).

NOTE: Mac users will have to run the following commands first prior to creating a rule:

```
istioctl context-create --context mac --api-server http://localhost:8080
```

You can create basic routing rules using istioctl from the `samples/bookinfo/consul` directory:

```
istioctl create -f route-rule-all-v1.yaml
```

This will set a rule to display no stars by default.

```
istioctl replace -f route-rule-reviews-v3.yaml
```

This will set a rule to display red stars by default.

```
istioctl create -f route-rule-reviews-test-v2.yaml
```

This will display black stars - but only if you login as user `jason` (no password), otherwise only red stars will be shown.

If you are an advanced consul and docker network user, you may choose to configure your own envoymesh network dns and consul port mapping and istio-apiserver ipv4_address in the `docker-compose.yaml` file.
