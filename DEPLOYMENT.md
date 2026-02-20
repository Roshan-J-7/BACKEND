# Docker Deployment Guide

## 🐳 Quick Start with Docker

### Prerequisites
- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (included with Docker Desktop)
- `.env` file with `CEREBRAS_API_KEY`

### Local Development with Docker

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

2. **Run in detached mode:**
   ```bash
   docker-compose up -d
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f
   ```

4. **Stop containers:**
   ```bash
   docker-compose down
   ```

### Build Docker Image Manually

```bash
# Build image
docker build -t healthcare-chatbot:latest .

# Run container
docker run -d \
  --name healthcare-chatbot \
  -p 8000:8000 \
  -e CEREBRAS_API_KEY=your_api_key_here \
  healthcare-chatbot:latest

# Check logs
docker logs -f healthcare-chatbot

# Stop container
docker stop healthcare-chatbot
docker rm healthcare-chatbot
```

## ☁️ AWS Deployment Options

### Option 1: AWS ECS (Elastic Container Service)

#### Step 1: Push to Amazon ECR

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository
aws ecr create-repository --repository-name healthcare-chatbot --region us-east-1

# Tag image
docker tag healthcare-chatbot:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/healthcare-chatbot:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/healthcare-chatbot:latest
```

#### Step 2: Create ECS Task Definition

Create `task-definition.json`:
```json
{
  "family": "healthcare-chatbot",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "healthcare-chatbot",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/healthcare-chatbot:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "CEREBRAS_API_KEY",
          "value": "your-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/healthcare-chatbot",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Step 3: Deploy to ECS

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create ECS cluster
aws ecs create-cluster --cluster-name healthcare-chatbot-cluster --region us-east-1

# Create ECS service
aws ecs create-service \
  --cluster healthcare-chatbot-cluster \
  --service-name healthcare-chatbot-service \
  --task-definition healthcare-chatbot \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### Option 2: AWS App Runner (Easiest)

```bash
# Create App Runner service (auto-deploys from ECR)
aws apprunner create-service \
  --service-name healthcare-chatbot \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/healthcare-chatbot:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "CEREBRAS_API_KEY": "your-api-key"
        }
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "1024",
    "Memory": "2048"
  }'
```

### Option 3: AWS Lightsail Containers (Budget-Friendly)

```bash
# Push container to Lightsail
aws lightsail push-container-image \
  --service-name healthcare-chatbot \
  --label healthcare-chatbot-latest \
  --image healthcare-chatbot:latest

# Create Lightsail container service
aws lightsail create-container-service \
  --service-name healthcare-chatbot \
  --power small \
  --scale 1

# Deploy container
aws lightsail create-container-service-deployment \
  --service-name healthcare-chatbot \
  --containers '{
    "healthcare-chatbot": {
      "image": ":healthcare-chatbot-latest",
      "ports": {
        "8000": "HTTP"
      },
      "environment": {
        "CEREBRAS_API_KEY": "your-api-key"
      }
    }
  }' \
  --public-endpoint '{
    "containerName": "healthcare-chatbot",
    "containerPort": 8000,
    "healthCheck": {
      "path": "/health"
    }
  }'
```

## 🔒 Environment Variables

For production, use AWS Secrets Manager or Parameter Store instead of hardcoding:

```bash
# Store secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name healthcare-chatbot/cerebras-api-key \
  --secret-string "your-api-key"

# Reference in ECS task definition
{
  "secrets": [
    {
      "name": "CEREBRAS_API_KEY",
      "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:healthcare-chatbot/cerebras-api-key"
    }
  ]
}
```

## 📊 Image Optimization

Current Dockerfile uses multi-stage build for smaller image size:
- Base image: `python:3.11-slim` (~120MB)
- Final image size: ~1.5GB (includes PyTorch & transformers)

To reduce further:
```bash
# Build with specific platform
docker build --platform linux/amd64 -t healthcare-chatbot:latest .

# Check image size
docker images healthcare-chatbot
```

## 🔍 Troubleshooting

### Container won't start
```bash
# Check logs
docker logs healthcare-chatbot

# Inspect container
docker inspect healthcare-chatbot

# Test locally
docker run -it --rm healthcare-chatbot:latest /bin/bash
```

### Health check failing
```bash
# Test health endpoint
curl http://localhost:8000/health

# Check inside container
docker exec -it healthcare-chatbot curl localhost:8000/health
```

### Model download issues
If Hugging Face models fail to download in container:
```bash
# Pre-download models locally, then copy to container
# Add to Dockerfile:
RUN python -c "from transformers import pipeline; pipeline('image-classification', model='microsoft/resnet-50')"
```

## 📦 Production Checklist

- [ ] Environment variables stored in AWS Secrets Manager
- [ ] Health checks configured
- [ ] Auto-scaling enabled (for ECS/App Runner)
- [ ] CloudWatch logging configured
- [ ] SSL/TLS certificate attached (via ALB or CloudFront)
- [ ] CORS configured properly in FastAPI
- [ ] Rate limiting implemented
- [ ] Monitoring and alerts set up

## 💰 Cost Estimates (AWS)

- **App Runner**: ~$25-50/month (1 vCPU, 2GB RAM)
- **ECS Fargate**: ~$30-60/month (1 vCPU, 2GB RAM)
- **Lightsail Containers**: ~$10-40/month (nano to medium)

Choose based on:
- App Runner: Zero-config auto-scaling
- ECS: Full control, VPC integration
- Lightsail: Predictable pricing, simpler

---

**Need help?** Check AWS documentation or open an issue on GitHub.
