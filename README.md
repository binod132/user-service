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

- FQDN, service type CLUSTERIP for inter-pod communication
Serive A (user-service) is calling Service B (order-service) on order_service_url = f'https://order-service.default.svc.cluster.local:5000/orders?user_id={user_id}'
    
- TLS for secure communication between pod.
Service A is calling Service B on https
Here Certidicates are self-managed
cert-manager is used to generate certificates
Certs are stored in kubernetes secrets. 
These secrets are used by service for https calls.
```yaml
# cert-issuer.yaml
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: selfsigned-issuer
  namespace: default
spec:
  selfSigned: {}
---
# certificate.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: order-service-tls
  namespace: default
spec:
  dnsNames:
    - order-service.default.svc.cluster.local
  secretName: order-service-tls-secret
  issuerRef:
    name: selfsigned-issuer
    kind: Issuer
  usages:
    - server auth
    - client auth
```
- service account
We can restrics roles and permission of pods using service account. As every pods creates default Service account with higher previllage, we can restrics it by creating service account, cluster role and  role binding.
```yaml
# service-accounts.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: user-service-sa
  namespace: default
```
```yaml
# rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: user-service-role
  namespace: default
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: user-service-rolebinding
  namespace: default
subjects:
  - kind: ServiceAccount
    name: user-service-sa
    namespace: default
roleRef:
  kind: Role
  name: user-service-role
  apiGroup: rbac.authorization.k8s.io
  ```

- networkpolicies
We can restric which pod can accept incoming or outgoing traffic to target pods using networkpolicies.
It can avoid unwanted traffics to pod.
```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-order-to-user
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: user-service
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: order-service
  policyTypes:
    - Ingress
```


SUMMARY
1. Service A - Dynamic Scaling (HPA)
Horizontal Pod Autoscaler (HPA): Configured for order-service, scaling based on CPU utilization.
HPA will scale pods between 1 and 10 based on CPU average utilization threshold of 75%.
2. Service B - Custom Metrics with KEDA
KEDA for Event-Driven Scaling: Configured user-service to scale based on CPU utilization of order-service using KEDA and Prometheus metrics.
Minimum 1 pod, maximum 4 pods.
Scales user-service based on the Prometheus metric container_cpu_usage_seconds_total for order-service.
3. Service C - GPU Scheduling
Node Affinity: payment-service is scheduled to GPU-enabled nodes using node affinity. GPU nodes are labeled gpu=true and requested via the GKE node pool.
4. Inter-Service Communication (A, B, C)
4.1 Service A (user-service) communicates with Service B (order-service) using FQDN (ClusterIP type service).
HTTPS used for secure communication with self-signed certificates.
Certificates are managed via cert-manager, stored in Kubernetes secrets.
4.2 Service Accounts and RBAC: Created a service account with restricted permissions for user-service and applied appropriate roles and bindings.
4.3 Network Policies: Implemented network policies to restrict traffic flow between services (e.g., order-service can only send traffic to user-service).
5. Event-Driven Dynamic Scaling
KEDA Metrics: Utilized Prometheus metrics to scale user-service based on the CPU load of order-service.
Metrics used: container_cpu_usage_seconds_total from Prometheus for event-driven scaling based on traffic or load.
