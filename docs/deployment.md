# Deployment Guide

This guide covers deploying Amorce in various environments.

---

## Deployment Options

- **Standalone (Self-Hosted)**: Run on your own infrastructure
- **Amorce Cloud**: Managed service at amorce.io
- **Hybrid**: Self-host orchestrator, use cloud registry

---

## Docker Deployment

### Build Image

```bash
# Clone repository
git clone https://github.com/trebortGolin/amorce.git
cd amorce

# Build Docker image
docker build -t amorce:latest .
```

### Run Standalone Mode

```bash
docker run -d \
  --name amorce-orchestrator \
  -p 8080:8080 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -e AMORCE_MODE=standalone \
  amorce:latest
```

### Run Cloud Mode

```bash
docker run -d \
  --name amorce-orchestrator \
  -p 8080:8080 \
  -e AMORCE_MODE=cloud \
  -e TRUST_DIRECTORY_URL=https://amorce-trust-api.run.app \
  -e AGENT_API_KEY=sk-atp-your-key \
  amorce:latest
```

---

## Google Cloud Run

### Prerequisites
- Google Cloud account
- gcloud CLI installed
- Docker installed

### Deploy

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable services
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Build and deploy
gcloud run deploy amorce-orchestrator \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AMORCE_MODE=standalone \
  --memory 512Mi \
  --cpu 1

# Get service URL
gcloud run services describe amorce-orchestrator \
  --region us-central1 \
  --format 'value(status.url)'
```

### Using Cloud Build

Create `cloudbuild.yaml`:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/amorce:$SHORT_SHA', '.']
  
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/amorce:$SHORT_SHA']
  
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'amorce-orchestrator'
      - '--image=gcr.io/$PROJECT_ID/amorce:$SHORT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
```

Deploy:
```bash
gcloud builds submit
```

---

## AWS ECS

### Fargate Deployment

1. **Create ECR Repository**

```bash
aws ecr create-repository --repository-name amorce
```

2. **Build and Push Image**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t amorce:latest .
docker tag amorce:latest \
  YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/amorce:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/amorce:latest
```

3. **Create Task Definition**

```json
{
  "family": "amorce-orchestrator",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "amorce",
      "image": "YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/amorce:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "AMORCE_MODE",
          "value": "standalone"
        }
      ]
    }
  ]
}
```

4. **Create Service**

```bash
aws ecs create-service \
  --cluster amorce-cluster \
  --service-name amorce-orchestrator \
  --task-definition amorce-orchestrator \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## Azure Container Instances

```bash
# Create resource group
az group create --name amorce-rg --location eastus

# Deploy container
az container create \
  --resource-group amorce-rg \
  --name amorce-orchestrator \
  --image amorce:latest \
  --ports 8080 \
  --environment-variables AMORCE_MODE=standalone \
  --cpu 1 \
  --memory 1
```

---

## Kubernetes

### Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: amorce-orchestrator
spec:
  replicas: 2
  selector:
    matchLabels:
      app: amorce
  template:
    metadata:
      labels:
        app: amorce
    spec:
      containers:
      - name: amorce
        image: amorce:latest
        ports:
        - containerPort: 8080
        env:
        - name: AMORCE_MODE
          value: "standalone"
        volumeMounts:
        - name: config
          mountPath: /app/config
      volumes:
      - name: config
        configMap:
          name: amorce-config
---
apiVersion: v1
kind: Service
metadata:
  name: amorce-service
spec:
  selector:
    app: amorce
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

Deploy:
```bash
kubectl apply -f deployment.yaml
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AMORCE_MODE` | No | `standalone` | Runtime mode: `standalone` or `cloud` |
| `TRUST_DIRECTORY_URL` | Cloud only | - | Trust Directory API endpoint |
| `AGENT_API_KEY` | Cloud only | - | Orchestrator API key |
| `PORT` | No | `8080` | HTTP server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Production Checklist

### Security
- [ ] Use HTTPS/TLS
- [ ] Configure API keys
- [ ] Enable rate limiting
- [ ] Restrict network access
- [ ] Regular security updates

### Monitoring
- [ ] Set up health check endpoint
- [ ] Configure logging (stdout/stderr)
- [ ] Monitor error rates
- [ ] Track response times
- [ ] Alert on failures

### Scalability
- [ ] Configure horizontal scaling
- [ ] Set up load balancer
- [ ] Enable auto-scaling
- [ ] Monitor resource usage
- [ ] Plan for growth

### Backup
- [ ] Backup configuration files
- [ ] Backup transaction logs
- [ ] Test restore process
- [ ] Document recovery procedures

---

## Health Checks

Orchestrator exposes a health endpoint:

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "mode": "standalone",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

Use for:
- Load balancer health checks
- Kubernetes liveness probes
- Monitoring systems

---

## Logging

Amorce logs to stdout/stderr:

```bash
# View logs (Docker)
docker logs amorce-orchestrator

# View logs (Kubernetes)
kubectl logs deployment/amorce-orchestrator

# View logs (Cloud Run)
gcloud run services logs read amorce-orchestrator --region us-central1
```

Configure log level:
```bash
export LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

---

## Scaling

### Horizontal Scaling

Amorce is stateless and scales horizontally:

```bash
# Docker Compose
docker-compose up --scale orchestrator=3

# Kubernetes
kubectl scale deployment amorce-orchestrator --replicas=3

# Cloud Run
gcloud run services update amorce-orchestrator \
  --min-instances 2 \
  --max-instances 10
```

### Vertical Scaling

Increase resources:

```bash
# Cloud Run
gcloud run services update amorce-orchestrator \
  --memory 1Gi \
  --cpu 2
```

---

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Change port
export PORT=8081
python orchestrator.py
```

**Permission denied:**
```bash
# Run with sudo or fix permissions
sudo python orchestrator.py
```

**Module not found:**
```bash
# Install dependencies
pip install -r requirements.txt
```

---

## Next Steps

- Set up monitoring and alerts
- Configure backup strategy
- Review [Security Best Practices](./protocol.md#security-considerations)
- Join community at https://amorce.io

---

**Need help?** Contact support at https://amorce.io/support
