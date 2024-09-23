# user-service

1. Implement a Kubernetes Deployment for Service A with a horizontal pod
autoscaler (HPA) that dynamically adjusts its replica count based on CPU
utilization.
```yaml
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
```
2. Deploy Service B with a custom metric monitoring configuration, allowing its
replica count to be dynamically scaled based on the CPU utilization of Service A.
    I am using KEDA, event-based scaling, as keda is easy to implement and fast.
2.1 Installtion

```yaml
    helm install keda kedacore/keda --namespace keda --create-namespace
```
2.2 To enable scaling of pods of user-service based on order-service with KEDA and Prometheus, create a Prometheus ScaledObject for user-service deployment
```yaml
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
```
2.3 Validation
    - Check hpa created by prometheus-scaledobject: 
```yaml
        kubectl get hpa
```
    - Increase load on order-service and check number of pods. (you can use k6 or Jmeter)
```yaml
        kubectl get pod |grep user-service`
```

3. Ensure that Service C is scheduled only on nodes with GPU resources available.
You may use NodeAffinity or other suitable methods to achieve this.

Add node-pool with GPU and add labels
example for GKE cluster

```yaml
gcloud container node-pools create gpu-node-pool \
    --cluster my-standard-cluster \
    --zone us-west1-a \
    --accelerator type=nvidia-tesla-t4,count=1 \
    --num-nodes 1 \
    --machine-type n1-standard-4 \
    --node-labels=gpu=true \
    --metadata=gpu-driver-installation-mode=cos-containerd \
    --scopes=https://www.googleapis.com/auth/cloud-platform

```
Check and Validate the nodes.
```
gcloud container node-pools list --cluster=my-standard-cluster --zone=us-west1-a

NAME           MACHINE_TYPE   DISK_SIZE_GB  NODE_VERSION
cpu-pool       e2-standard-2  100           1.30.3-gke.1639000
gpu-node-pool  n1-standard-4  100           1.30.3-gke.1639000

```
Add nodeAffinity on Deployment manifest to match above labels. (Note: use antiaffinity for other non-gpu pods)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
  labels:
    app: payment-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-service
  template:
    metadata:
      labels:
        app: payment-service
    spec:
      containers:
      - name: payment-service
        image: us-west1-docker.pkg.dev/brave-smile-424210-m0/microservice/payment-service:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
        resources:
          limits:
            nvidia.com/gpu: 1  # Request 1 GPU
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: gpu
                    operator: In
                    values:
                      - "true"  # Only schedule on GPU nodes
```
4. Implement inter-service communication between A, B, and C within the cluster.
Consider security best practices for communication.

- use fdqn, service type clusterip
- TLS
- service account
- networkpolicies
