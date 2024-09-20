# user-service

1. Implement a Kubernetes Deployment for Service A with a horizontal pod
autoscaler (HPA) that dynamically adjusts its replica count based on CPU
utilization.
----------
    apiVersion: autoscaling/v2
    kind: HorizontalPodAutoscaler
    metadata:
    name: order-service
    spec:
    scaleTargetRef:
        apiVersion: apps/v1
        kind: Deployment
        name: order-service
    minReplicas: 1
    maxReplicas: 10
    metrics:
    - type: Resource
        resource:
        name: cpu
        target:
            type: Utilization
            averageUtilization: 75

2. Deploy Service B with a custom metric monitoring configuration, allowing its
replica count to be dynamically scaled based on the CPU utilization of Service A.
    
    I am using KEDA, event-based scaling, as keda is easy to implement and fast.
    2.1 Installtion
    --------
    helm install keda kedacore/keda --namespace keda --create-namespace

    2.2 To enable scaling of pods of user-service based on order-service with KEDA and Prometheus, create a Prometheus ScaledObject for user-service deployment

    apiVersion: keda.sh/v1alpha1
    kind: ScaledObject
    metadata:
    name: prometheus-scaledobject
    namespace: default
    spec:
    minReplicaCount: 1
    maxReplicaCount: 4
    scaleTargetRef:
        name: user-service
    triggers:
    - type: prometheus
        metadata:
        serverAddress: http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090 
        metricName: container_cpu_usage_seconds_total
        threshold: '1000'
        query: sum(container_cpu_usage_seconds_total{pod=~"order-service-.*"})
    2.3 Validation
    - Check hpa created by prometheus-scaledobject: 
        '''kubectl get hpa'''
    - Increase load on order-service and check number of pods. (you can use k6 or Jmeter)
        `kubectl get pod |grep user-service`