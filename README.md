# **Assignment**
# **Kubernetes Lab Question**
1. #**Advanced Multi-Container Orchestration (30 Points):**  
  1.1 **Implement a Kubernetes Deployment for Service A with a horizontal pod
autoscaler (HPA) that dynamically adjusts its replica count based on CPU
utilization.**
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
  1.2 **Deploy Service B with a custom metric monitoring configuration, allowing its
replica count to be dynamically scaled based on the CPU utilization of Service A.**  
    We can use KEDA, event-based scaling, as keda is easy to implement and fast.
a. Installtion

```yaml
    helm install keda kedacore/keda --namespace keda --create-namespace
```
b. To enable scaling of pods of user-service based on order-service with KEDA and Prometheus, create a Prometheus ScaledObject for user-service deployment
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
c. Validation
    - Check hpa created by prometheus-scaledobject: 
```yaml
        kubectl get hpa
```
NAME                               REFERENCE                  TARGETS           MINPODS   MAXPODS   REPLICAS   AGE
keda-hpa-prometheus-scaledobject   Deployment/user-service    17936m/20 (avg)   3         10        4          3d20h
order-service                      Deployment/order-service   cpu: 10%/75%      2         10        2          3d19h
    - Increase load on order-service and check number of pods. (you can use k6 or Jmeter)
```yaml
        kubectl get pod |grep user-service`
```

  1.3 **Ensure that Service C is scheduled only on nodes with GPU resources available.
You may use NodeAffinity or other suitable methods to achieve this.**

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
Add nodeAffinity on Deployment manifest to match above labels. (**Note: use antiaffinity for other non-gpu pods**)

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
1.4 **Implement inter-service communication between A, B, and C within the cluster.
Consider security best practices for communication.**

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
Kubernetes Lab Question
Advanced Multi-Container Orchestration (30 Points):
Tasks:
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

#**Deploying a Multi-Container Application (20 Points)**
Note: user-service as frontend and order-service as backend
Tasks:
1. Create a Kubernetes Deployment for the frontend web server user-service, ensuring it has:
a. Container image: your-frontend-image:latest
b. Desired replicas: 3
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  labels:
    app: user-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
      - name: user-service
        image: us-west1-docker.pkg.dev/brave-smile-424210-m0/microservice/user-service:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
        resources:
          limits:
            memory: "256Mi"
            cpu: "100m"
          requests:
            memory: "128Mi"
            cpu: "50m"
```
Note: user-service scale based on external custom metrics from KEDA, where minimum replica is set 3.
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: prometheus-scaledobject
  namespace: default
spec:
  minReplicaCount: 3
  maxReplicaCount: 10
  scaleTargetRef:
    name: user-service
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090 
      metricName: container_cpu_usage_seconds_total
      threshold: '20'
      query: sum(container_cpu_usage_seconds_total{pod=~"order-service-.*"})
```
2. Create a Kubernetes Deployment for the backend API server with:
a. Container image: your-backend-image:latest
b. Desired replicas: 2
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: gpu
                operator: NotIn
                values:
                - "true"
      containers:
      - name: order-service
        image: us-west1-docker.pkg.dev/brave-smile-424210-m0/microservice/order-service:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
        resources:
          limits:
            memory: "256Mi"
            cpu: "100m"
          requests:
            memory: "128Mi"
            cpu: "10m"
```
Note: order-service scale based on HPA, where minimum replica count is set 2.
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
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 75
```
3. Expose the frontend and backend Deployments via Kubernetes Services,
allowing them to communicate internally within the cluster.

Frontend and Backend Kubernetes Services are expose using service type ClusterIP to communicate internally within the cluster.
For frontend (user-service)
```yaml
apiVersion: v1
kind: Service
metadata:
  name: user-service
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: user-service
```
```yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: default
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9100"
    prometheus.io/path: "/metrics"
spec:
  type: ClusterIP
  selector:
    app: order-service
  ports:
    - name: http  # Name for the HTTP port
      protocol: TCP
      port: 5000  # App port
      targetPort: 5000
    - name: metrics  # Name for the metrics port
      protocol: TCP
      port: 9100  # Prometheus metrics port
      targetPort: 9100
```
4. Verify that the pods are running and the services are accessible within the
cluster.

We can verify pods using: 
```yaml
kubectl get pods
```
user-service-7ccc68f985-bnwsl    1/1     Running   0          27m
user-service-7ccc68f985-htl94    1/1     Running   0          27m
user-service-7ccc68f985-vvwfc    1/1     Running   0          27m
order-service-6b5856f7fd-pc972   1/1     Running   0          14h
order-service-6b5856f7fd-xnnnd   1/1     Running   0          90m

We can verify services using:
```yaml
kubectl get svc
```
user-service         ClusterIP      34.118.236.234   <none>           80/TCP              5d11h
order-service        ClusterIP      34.118.239.147   <none>           5000/TCP,9100/TCP   5d11h

5. Set up an Ingress resource to expose the frontend service to the external world.
For Ingress setup, Ingress Class GCE is used. It expose using external application loadbalancer.
Also, Static IP is assigned. And all unmatched traffics are redirected to default user-service.
We can add GCP managed certificates also for https (need valid domain first) or can add self-generated certificates.
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: public-ingress-prod
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: prod-test-ip-external
    #networking.gke.io/managed-certificates: "managed-certificate"
    networking.gke.io/v1beta1.FrontendConfig: "http-to-https"
    cloud.google.com/health-check-interval-sec: "60"
    cloud.google.com/health-check-timeout-sec: "30"

spec:
  # Add a default backend to catch all unmatched traffic
  defaultBackend:
    service:
      name: user-service
      port:
        number: 80
  rules:
  - host: frontend.khalti.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
```

#**SDLC Automation**
1. #**CICD/Containerization ( 20 Points):**
#**Dockerfile with Multistage Build and Best Layering Technique**
- Multistage build
```Dockerfile 
# Stage 1: Build the image
FROM python:3.9-slim AS builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Run the image
FROM python:3.9-slim

WORKDIR /app

# Copy from builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app.py .

EXPOSE 5000
CMD ["python", "app.py"]
```

Benifites of multi-stage build:
a. Reduce Image size by packaging minimal requried runtime environment to run application on container.
b. Make build fast.
c. Improve security because of minimal requried runtime environment reduces valvulnerabilities.
d. Layering cached intermideate artifacts and increases build speed and security.


#**CI/CD Pipeline Setup with Jenkins or GitHub Actions (4 points):**

Tool: gitaction
Environment Variables: Github Secrets and Variable

```yaml
name: CI/CD for Microservices

on:
  push:
    branches:
      - main  # Trigger on pushes to the main branch

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  GKE_CLUSTER: ${{ secrets.GKE_CLUSTER_NAME }}
  GKE_ZONE: ${{ secrets.GKE_CLUSTER_ZONE }}
  REGION: ${{ secrets.REGION }}

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      # Checkout the repository
      - name: Checkout code
        uses: actions/checkout@v3

      - id: "auth"
        uses: "google-github-actions/auth@v1"
        with:
          credentials_json: ${{ secrets.SA }}

      - name: "Set up Cloud SDK"
        uses: "google-github-actions/setup-gcloud@v1"
      
      # Install gke-gcloud-auth-plugin through gcloud
      - name: Install GKE gcloud Auth Plugin
        run: |
          gcloud components install gke-gcloud-auth-plugin
          gcloud components update

      - name: "Use gcloud CLI"
        run: "gcloud info"

      - name: "Docker auth"
        run: |-
              gcloud auth configure-docker $REGION-docker.pkg.dev --quiet
      # code analysis and vulnerability
      ## Application code analysis and vulnerability
      - name: Check Pylint score
        run: |
          pylint_score=$(grep "rated at" pylint-output.txt | awk '{print $7}' | sed 's/\/10//')
          echo "Pylint score: $pylint_score"
          if (( $(echo "$pylint_score <= 0.01" | bc -l) )); then
            echo "Pylint score is too low. Failing the build."
            exit 1
          fi
          echo "Pylint score is acceptable. Passing the build."

      # Build and push Order Service Docker image
      - name: Build and Push Order Service Docker image
        run: |  
          docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/microservice/user-service:latest .
      
      # code analysis and vulnerability     
     # Run Trivy vulnerability scanner
      - name: Run Trivy vulnerability scanner
        id: trivy
        uses: aquasecurity/trivy-action@0.20.0
        with:
          image-ref: 'us-west1-docker.pkg.dev/brave-smile-424210-m0/microservice/user-service:latest'
          format: 'table'
          exit-code: '0' # Set to 0 to allow subsequent steps
          ignore-unfixed: true
          vuln-type: 'os,library'
          severity: 'CRITICAL,HIGH'
          output: test.txt

      # Check vulnerability counts and fail if thresholds are exceeded
      - name: Check Trivy results
        run: |
          # Capture Trivy scan output from the output file
          TRIVY_OUTPUT=$(cat test.txt)
          
          # Extract the number of vulnerabilities from the Trivy scan output
          HIGH_COUNT=$(echo "$TRIVY_OUTPUT" | grep -oP 'HIGH: \K[0-9]+')
          CRITICAL_COUNT=$(echo "$TRIVY_OUTPUT" | grep -oP 'CRITICAL: \K[0-9]+')

          # Set thresholds
          HIGH_THRESHOLD=10
          CRITICAL_THRESHOLD=10

          # Check counts against thresholds
          if [ "$HIGH_COUNT" -gt "$HIGH_THRESHOLD" ] || [ "$CRITICAL_COUNT" -gt "$CRITICAL_THRESHOLD" ]; then
            echo "Vulnerability threshold exceeded: HIGH: $HIGH_COUNT, CRITICAL: $CRITICAL_COUNT"
            exit 1  # Fail the step
          else
            echo "Vulnerability check passed: HIGH: $HIGH_COUNT, CRITICAL: $CRITICAL_COUNT"
          fi
      # Push Order Service Docker image
      - name: Push Order Service Docker image
        run: |  
          docker push $REGION-docker.pkg.dev/$PROJECT_ID/microservice/user-service:latest

      # Set up kubectl to interact with the GKE cluster
      - name: Set up kubectl
        run: |
          gcloud container clusters get-credentials $GKE_CLUSTER --zone $GKE_ZONE --project $PROJECT_ID
          kubectl version --client

      # Apply Kubernetes manifests for User Service
      - name: Deploy User Service
        run: |
          kubectl apply -f k8s/user-service.yaml
      # Check User Service PODs
      - name: User Service pods
        run: |
          kubectl get pod | grep user
```

#**Code Analysis and Vulnerability Checking (4 points):**
- Code Analysis: Pylint is used as application is written in python. 
CICD step: Check Pylint score. It scan the app.py or any.py file, and gives the score based on Vulnerability, good coding practices and etc.
We can fails the CICD step and stop if set score is below user defined threshold.
- Image Scan
CICD step: Run Trivy vulnerability scanner
It scan the build image and create report of vulnerabilities
CICD step: Check Trivy results
It process Trivy results and stop CICD if number of vulnerabilities's (High, Critical) is above user defined threshold

#**Automation**
2. #**Bash Script (10 Points):**
Scenario:
You have a directory with various text files. Write a Bash script to find all the unique words across all files.
Example of files.txt
File1.txt: It contains some unique words. File2.txt It also contains unique words.
Output : It, contains, some, unique, words, also

2.1 Creat a file: unique.sh
```sh
#!/bin/bash

# Define the directory containing the text files
DIR="/Users/binodadhikari/Downloads/test/"

# Find all text files, extract words, remove punctuation, convert to lowercase, sort, and return unique words
grep -ohE '\b\w+\b' "$DIR"/*.txt | tr '[:upper:]' '[:lower:]' | sort | uniq 
```

2.2 chomod +x unique.sh
2.3 ./unique.sh
```yaml
@Binods-MacBook-Pro-2 test % ./unique_words.sh 
file
is
number
one
this
two
```


#**Logging:**
1. Log Parsing.
  Used python request package.
  ```python 
  @app.route('/users/<int:user_id>/orders', methods=['GET'])
  def get_user_orders(user_id):
      # Call the order-service using HTTPS
      order_service_url = f'https://order-service.default.svc.cluster.local:5000/orders?user_id={user_id}'
      
      # Disable SSL verification for internal communication (only in internal trusted networks)
      response = requests.get(order_service_url, verify=False)

      if response.status_code == 200:
          return jsonify(response.json())
      else:
          return jsonify({'error': 'Failed to retrieve orders'}), response.status_code
  ```